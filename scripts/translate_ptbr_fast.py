from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import MarianMTModel, MarianTokenizer

import translate_ptbr as base

MODEL = "Helsinki-NLP/opus-mt-en-ROMANCE"
BATCH_SIZE = 48


@dataclass
class Record:
    path: Path
    kind: str
    start: int
    end: int
    terminal: bool
    mappings: list[dict[str, str]]
    indices: list[int]


def collect_assembly(path: Path, flat: list[str], records: list[Record], stats: base.Stats) -> None:
    text = path.read_text(encoding="utf-8")
    for match in base.BLOCK_RE.finditer(text):
        stats.assembly_seen += 1
        raw = "".join(base.LINE_RE.findall(match.group("body")))
        paragraphs, terminal = base.split_raw(raw)
        if not paragraphs or not base.looks_english(" ".join(paragraphs)):
            continue
        mappings: list[dict[str, str]] = []
        indices: list[int] = []
        for paragraph in paragraphs:
            protected, mapping = base.protect(paragraph)
            indices.append(len(flat))
            flat.append(protected)
            mappings.append(mapping)
        records.append(
            Record(
                path=path,
                kind="assembly",
                start=match.start("body"),
                end=match.end("body"),
                terminal=terminal,
                mappings=mappings,
                indices=indices,
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
        mappings: list[dict[str, str]] = []
        indices: list[int] = []
        for paragraph in paragraphs:
            protected, mapping = base.protect(paragraph)
            indices.append(len(flat))
            flat.append(protected)
            mappings.append(mapping)
        records.append(
            Record(
                path=path,
                kind="c",
                start=match.start(1),
                end=match.end(1),
                terminal=terminal,
                mappings=mappings,
                indices=indices,
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
            batch = [f">>pt<< {text}" for text in texts[start : start + BATCH_SIZE]]
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
            )
            output.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
            print(f"Translated {min(start + BATCH_SIZE, len(texts))}/{len(texts)}", flush=True)
    return output


def apply_records(records: list[Record], translated: list[str], stats: base.Stats) -> None:
    grouped: dict[Path, list[Record]] = defaultdict(list)
    for record in records:
        grouped[record.path].append(record)
    for path, path_records in grouped.items():
        original = path.read_text(encoding="utf-8")
        updated = original
        replacements: list[tuple[int, int, str]] = []
        for record in path_records:
            paragraphs = [
                base.normalize(base.restore(translated[index], mapping))
                for index, mapping in zip(record.indices, record.mappings)
            ]
            replacements.append(
                (
                    record.start,
                    record.end,
                    base.encode(paragraphs, record.terminal, record.kind == "assembly"),
                )
            )
        for start, end, value in sorted(replacements, reverse=True):
            updated = updated[:start] + value + updated[end:]
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            stats.files_changed += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    stats = base.Stats()
    flat: list[str] = []
    records: list[Record] = []

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

    for path in assembly_files:
        collect_assembly(path, flat, records, stats)
    for path in c_files:
        if path.exists():
            collect_c(path, flat, records, stats)

    print(f"English text segments queued: {len(flat)}", flush=True)
    translated = translate_all(flat)
    if len(translated) != len(flat):
        raise RuntimeError(f"Translation count mismatch: {len(translated)} != {len(flat)}")
    apply_records(records, translated, stats)

    report = {
        "assembly_blocks_seen": stats.assembly_seen,
        "assembly_blocks_translated": stats.assembly_translated,
        "c_strings_seen": stats.c_seen,
        "c_strings_translated": stats.c_translated,
        "text_segments_translated": len(flat),
        "files_changed": stats.files_changed,
        "model": MODEL,
        "batch_size": BATCH_SIZE,
        "note": "Machine translation consistency pass; manual in-game proofreading remains recommended.",
    }
    report_path = args.report or project / "translation_consistency_v1.3.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
