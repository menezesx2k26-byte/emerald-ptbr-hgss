from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import MarianMTModel, MarianTokenizer

import translate_ptbr as base

MODEL = "Helsinki-NLP/opus-mt-tc-big-en-pt"
TARGET_PREFIX = ">>pob<<"
BATCH_SIZE = 64

PROTECTED_RE = re.compile(
    r"(\{[^{}]+\}|\\[A-Za-z][A-Za-z0-9_ ]*|"
    r"POKéMON|POKéDEX|POKéNAV|POKéBLOCK|"
    r"[A-Z][A-Z0-9_.-]{2,})"
)


@dataclass
class Part:
    literal: str | None = None
    translation_index: int | None = None
    leading: str = ""
    trailing: str = ""


@dataclass
class Record:
    path: Path
    kind: str
    start: int
    end: int
    terminal: bool
    paragraphs: list[list[Part]]


@dataclass(frozen=True)
class SourceFile:
    path: Path
    kind: str
    weight: int


def segment_paragraph(paragraph: str, flat: list[str]) -> list[Part]:
    parts: list[Part] = []
    position = 0
    for match in PROTECTED_RE.finditer(paragraph):
        plain = paragraph[position : match.start()]
        add_plain_part(plain, flat, parts)
        parts.append(Part(literal=match.group(0)))
        position = match.end()
    add_plain_part(paragraph[position:], flat, parts)
    return parts


def add_plain_part(text: str, flat: list[str], parts: list[Part]) -> None:
    if not text:
        return
    if not re.search(r"[A-Za-zÀ-ÿ]", text):
        parts.append(Part(literal=text))
        return
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    core = text.strip()
    if not core:
        parts.append(Part(literal=text))
        return
    index = len(flat)
    flat.append(core)
    parts.append(
        Part(
            translation_index=index,
            leading=leading,
            trailing=trailing,
        )
    )


def piece_weight(paragraph: str) -> int:
    count = 0
    position = 0
    for match in PROTECTED_RE.finditer(paragraph):
        if re.search(r"[A-Za-zÀ-ÿ]", paragraph[position : match.start()]):
            count += 1
        position = match.end()
    if re.search(r"[A-Za-zÀ-ÿ]", paragraph[position:]):
        count += 1
    return count


def assembly_weight(path: Path) -> int:
    total = 0
    text = path.read_text(encoding="utf-8")
    for match in base.BLOCK_RE.finditer(text):
        raw = "".join(base.LINE_RE.findall(match.group("body")))
        paragraphs, _ = base.split_raw(raw)
        if paragraphs and base.looks_english(" ".join(paragraphs)):
            total += sum(piece_weight(paragraph) for paragraph in paragraphs)
    return total


def c_weight(path: Path) -> int:
    total = 0
    text = path.read_text(encoding="utf-8")
    for match in base.C_RE.finditer(text):
        paragraphs, _ = base.split_raw(match.group(1))
        if paragraphs and base.looks_english(" ".join(paragraphs)):
            total += sum(piece_weight(paragraph) for paragraph in paragraphs)
    return total


def build_file_plan(project: Path, shard_count: int) -> tuple[list[list[SourceFile]], list[int]]:
    assembly_files = sorted((project / "data/maps").rglob("scripts.inc"))
    assembly_files += sorted((project / "data/text").glob("*.inc"))
    assembly_files += sorted((project / "data/scripts").glob("*.inc"))
    c_files = [
        project / "src/strings.c",
        project / "src/battle_message.c",
        project / "src/berry.c",
        project / "src/berry_blender.c",
        project / "src/mystery_event_msg.c",
        project / "src/data/union_room.h",
        project / "src/data/text/match_call_messages.h",
    ]

    # Deliberately excluded:
    #   src/data/text/move_names.h
    #   src/data/text/move_descriptions.h
    sources: list[SourceFile] = []
    for path in assembly_files:
        weight = assembly_weight(path)
        if weight:
            sources.append(SourceFile(path, "assembly", weight))
    for path in c_files:
        if path.exists():
            weight = c_weight(path)
            if weight:
                sources.append(SourceFile(path, "c", weight))

    shards: list[list[SourceFile]] = [[] for _ in range(shard_count)]
    totals = [0 for _ in range(shard_count)]
    for source in sorted(sources, key=lambda item: (-item.weight, item.path.as_posix())):
        target = min(range(shard_count), key=lambda index: (totals[index], index))
        shards[target].append(source)
        totals[target] += source.weight
    return shards, totals


def collect_assembly(path: Path, flat: list[str], records: list[Record], stats: base.Stats) -> None:
    text = path.read_text(encoding="utf-8")
    for match in base.BLOCK_RE.finditer(text):
        stats.assembly_seen += 1
        raw = "".join(base.LINE_RE.findall(match.group("body")))
        paragraphs, terminal = base.split_raw(raw)
        if not paragraphs or not base.looks_english(" ".join(paragraphs)):
            continue
        records.append(
            Record(
                path=path,
                kind="assembly",
                start=match.start("body"),
                end=match.end("body"),
                terminal=terminal,
                paragraphs=[segment_paragraph(paragraph, flat) for paragraph in paragraphs],
            )
        )
        stats.assembly_translated += 1


def collect_c(path: Path, flat: list[str], records: list[Record], stats: base.Stats) -> None:
    text = path.read_text(encoding="utf-8")
    for match in base.C_RE.finditer(text):
        stats.c_seen += 1
        paragraphs, terminal = base.split_raw(match.group(1))
        if not paragraphs or not base.looks_english(" ".join(paragraphs)):
            continue
        records.append(
            Record(
                path=path,
                kind="c",
                start=match.start(1),
                end=match.end(1),
                terminal=terminal,
                paragraphs=[segment_paragraph(paragraph, flat) for paragraph in paragraphs],
            )
        )
        stats.c_translated += 1


def translate_all(texts: list[str]) -> list[str]:
    torch.set_num_threads(max(1, os.cpu_count() or 2))
    tokenizer = MarianTokenizer.from_pretrained(MODEL)
    model = MarianMTModel.from_pretrained(MODEL)
    model.eval()
    output: list[str] = []
    with torch.inference_mode():
        for start in range(0, len(texts), BATCH_SIZE):
            batch = [f"{TARGET_PREFIX} {text}" for text in texts[start : start + BATCH_SIZE]]
            encoded = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=256,
            )
            generated = model.generate(
                **encoded,
                max_new_tokens=256,
                num_beams=1,
                do_sample=False,
                repetition_penalty=1.08,
            )
            output.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
            print(f"Translated {min(start + BATCH_SIZE, len(texts))}/{len(texts)}", flush=True)
    return output


def rebuild_paragraph(parts: list[Part], translated: list[str]) -> str:
    output: list[str] = []
    for part in parts:
        if part.literal is not None:
            output.append(part.literal)
        elif part.translation_index is not None:
            value = base.normalize(translated[part.translation_index])
            output.append(part.leading + value + part.trailing)
        else:
            raise RuntimeError("Invalid translation part")
    return "".join(output)


def safe_pages(paragraphs: list[str], width: int = 29) -> list[list[str]]:
    result: list[list[str]] = []
    for paragraph in paragraphs:
        protected, mapping = base.protect(paragraph)
        wrapped = textwrap.wrap(
            protected,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        restored = [base.restore(line, mapping) for line in wrapped]
        result.extend(restored[index : index + 3] for index in range(0, len(restored), 3))
    return result


def safe_encode(paragraphs: list[str], terminal: bool, assembly: bool) -> str:
    output: list[str] = []
    all_pages = safe_pages(paragraphs)
    for page_index, page in enumerate(all_pages):
        last_page = page_index == len(all_pages) - 1
        for line_index, line in enumerate(page):
            last_line = line_index == len(page) - 1
            if not last_line:
                control = "\\n" if line_index == 0 else "\\l"
            elif not last_page:
                control = "\\p"
            else:
                control = "$" if terminal else ""
            value = line.replace('"', "'") + control
            output.append(f'\t.string "{value}"\n' if assembly else value)
    return "".join(output)


def apply_records(records: list[Record], translated: list[str], stats: base.Stats) -> None:
    grouped: dict[Path, list[Record]] = defaultdict(list)
    for record in records:
        grouped[record.path].append(record)
    for path, path_records in grouped.items():
        original = path.read_text(encoding="utf-8")
        replacements: list[tuple[int, int, str]] = []
        for record in path_records:
            paragraphs = [
                rebuild_paragraph(parts, translated)
                for parts in record.paragraphs
            ]
            replacements.append(
                (
                    record.start,
                    record.end,
                    safe_encode(paragraphs, record.terminal, record.kind == "assembly"),
                )
            )
        updated = original
        for start, end, value in sorted(replacements, reverse=True):
            updated = updated[:start] + value + updated[end:]
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            stats.files_changed += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    args = parser.parse_args()

    if args.shard_count < 1:
        raise ValueError("--shard-count must be at least 1")
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError("--shard-index must be within the shard range")

    project = args.project.resolve()
    shards, totals = build_file_plan(project, args.shard_count)
    selected = shards[args.shard_index]
    stats = base.Stats()
    flat: list[str] = []
    records: list[Record] = []

    for source in selected:
        if source.kind == "assembly":
            collect_assembly(source.path, flat, records, stats)
        else:
            collect_c(source.path, flat, records, stats)

    print(
        f"Shard {args.shard_index + 1}/{args.shard_count}: "
        f"{len(selected)} files, {len(flat)} protected text spans queued",
        flush=True,
    )
    translated = translate_all(flat)
    if len(translated) != len(flat):
        raise RuntimeError(f"Translation count mismatch: {len(translated)} != {len(flat)}")
    apply_records(records, translated, stats)

    report = {
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "estimated_shard_totals": totals,
        "selected_files": [source.path.relative_to(project).as_posix() for source in selected],
        "assembly_blocks_seen": stats.assembly_seen,
        "assembly_blocks_translated": stats.assembly_translated,
        "c_strings_seen": stats.c_seen,
        "c_strings_translated": stats.c_translated,
        "text_spans_translated": len(flat),
        "text_segments_translated": len(flat),
        "files_changed": stats.files_changed,
        "model": MODEL,
        "target_language_token": TARGET_PREFIX,
        "batch_size": BATCH_SIZE,
        "placeholder_strategy": "Translate plain spans only; placeholders never enter the model",
        "move_names_policy": "English move names and move descriptions preserved",
        "excluded_move_files": [
            "src/data/text/move_names.h",
            "src/data/text/move_descriptions.h",
        ],
        "note": "Automated translation consistency pass; in-game proofreading remains recommended.",
    }
    report_path = args.report or project / f"translation_consistency_v1.3_shard_{args.shard_index}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
