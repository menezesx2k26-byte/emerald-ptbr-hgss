from __future__ import annotations

import argparse
import json
import re
import subprocess
import textwrap
from collections import Counter
from pathlib import Path

import translate_ptbr as base

PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
BROKEN_PLACEHOLDER_RE = re.compile(r"\{[^{}]*(?:\\n|\\l|\\p)[^{}]*\}")

MANUAL_C_TRANSLATIONS = {
    "Wild POKéMON will be lured": (
        "{JOGADOR} usou o {STR_VAR_2}.\\p"
        "POKéMON selvagens serão atraídos.{PAUSE_UNTIL_PRESS}"
    ),
}


def normalize_placeholder_controls(raw: str) -> str:
    def repair(match: re.Match[str]) -> str:
        placeholder = re.sub(r"\\(?:n|l|p)", " ", match.group(0))
        placeholder = re.sub(r"\s+", " ", placeholder)
        return placeholder

    return PLACEHOLDER_RE.sub(repair, raw)


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
            value = line.replace('"', '\\"') + control
            output.append(f'\t.string "{value}"\n' if assembly else value)
    return "".join(output)


def safe_reflow(raw: str, assembly: bool) -> str:
    raw = normalize_placeholder_controls(raw)
    paragraphs, terminal = base.split_raw(raw)
    return safe_encode(paragraphs, terminal, assembly)


def repair_assembly_placeholders(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    replacements: list[tuple[int, int, str]] = []
    for match in base.BLOCK_RE.finditer(original):
        raw = "".join(base.LINE_RE.findall(match.group("body")))
        if not BROKEN_PLACEHOLDER_RE.search(raw):
            continue
        replacements.append(
            (
                match.start("body"),
                match.end("body"),
                safe_reflow(raw, True),
            )
        )
    if not replacements:
        return 0
    updated = original
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    path.write_text(updated, encoding="utf-8")
    return len(replacements)


def repair_c_placeholders(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    replacements: list[tuple[int, int, str]] = []
    for match in base.C_RE.finditer(original):
        raw = match.group(1)
        if not BROKEN_PLACEHOLDER_RE.search(raw):
            continue
        replacements.append(
            (
                match.start(1),
                match.end(1),
                safe_reflow(raw, False),
            )
        )
    if not replacements:
        return 0
    updated = original
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    path.write_text(updated, encoding="utf-8")
    return len(replacements)


def git_original(project: Path, path: Path) -> str:
    relative = path.relative_to(project).as_posix()
    return subprocess.check_output(
        ["git", "-C", str(project), "show", f"HEAD:{relative}"],
        text=True,
        encoding="utf-8",
    )


def looks_runaway(current: str, original: str) -> bool:
    if len(current.encode("utf-8")) > 1000:
        return True
    if len(current) > max(384, len(original) * 5):
        return True
    words = re.findall(r"[A-Za-zÀ-ÿ]+", current.lower())
    if len(current) > 220 and len(words) >= 24:
        _, frequency = Counter(words).most_common(1)[0]
        if frequency / len(words) >= 0.28:
            return True
    return False


def manual_or_original(original_raw: str) -> tuple[str, str]:
    for marker, translation in MANUAL_C_TRANSLATIONS.items():
        if marker in original_raw:
            return safe_reflow(translation, False), "manual_ptbr"
    return original_raw, "original_fallback"


def repair_c_runaways(project: Path, path: Path) -> list[dict[str, object]]:
    current_text = path.read_text(encoding="utf-8")
    original_text = git_original(project, path)
    current_matches = list(base.C_RE.finditer(current_text))
    original_matches = list(base.C_RE.finditer(original_text))
    if len(current_matches) != len(original_matches):
        raise RuntimeError(
            f"C string count changed in {path.relative_to(project)}: "
            f"{len(current_matches)} != {len(original_matches)}"
        )

    replacements: list[tuple[int, int, str]] = []
    repaired: list[dict[str, object]] = []
    for index, (current_match, original_match) in enumerate(zip(current_matches, original_matches)):
        current_raw = current_match.group(1)
        original_raw = original_match.group(1)
        if not looks_runaway(current_raw, original_raw):
            continue
        replacement, strategy = manual_or_original(original_raw)
        replacements.append((current_match.start(1), current_match.end(1), replacement))
        repaired.append(
            {
                "index": index,
                "strategy": strategy,
                "translated_bytes": len(current_raw.encode("utf-8")),
                "original_bytes": len(original_raw.encode("utf-8")),
                "original_preview": original_raw[:120],
            }
        )

    updated = current_text
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    if replacements:
        path.write_text(updated, encoding="utf-8")
    return repaired


def repair_assembly_runaways(project: Path, path: Path) -> list[dict[str, object]]:
    current_text = path.read_text(encoding="utf-8")
    original_text = git_original(project, path)
    original_by_label = {
        match.group("label").strip(): match
        for match in base.BLOCK_RE.finditer(original_text)
    }
    replacements: list[tuple[int, int, str]] = []
    repaired: list[dict[str, object]] = []

    for current_match in base.BLOCK_RE.finditer(current_text):
        label = current_match.group("label").strip()
        original_match = original_by_label.get(label)
        if original_match is None:
            continue
        current_raw = "".join(base.LINE_RE.findall(current_match.group("body")))
        original_raw = "".join(base.LINE_RE.findall(original_match.group("body")))
        if not looks_runaway(current_raw, original_raw):
            continue
        replacements.append(
            (
                current_match.start("body"),
                current_match.end("body"),
                original_match.group("body"),
            )
        )
        repaired.append(
            {
                "label": label,
                "strategy": "original_fallback",
                "translated_bytes": len(current_raw.encode("utf-8")),
                "original_bytes": len(original_raw.encode("utf-8")),
            }
        )

    updated = current_text
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    if replacements:
        path.write_text(updated, encoding="utf-8")
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()

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

    repaired_files: set[str] = set()
    repaired_placeholders = 0
    for path in assembly_files:
        count = repair_assembly_placeholders(path)
        if count:
            repaired_placeholders += count
            repaired_files.add(path.relative_to(project).as_posix())
    for path in c_files:
        if not path.exists():
            continue
        count = repair_c_placeholders(path)
        if count:
            repaired_placeholders += count
            repaired_files.add(path.relative_to(project).as_posix())

    runaway_repairs: list[dict[str, object]] = []
    for path in assembly_files:
        repairs = repair_assembly_runaways(project, path)
        if repairs:
            repaired_files.add(path.relative_to(project).as_posix())
            runaway_repairs.append(
                {"file": path.relative_to(project).as_posix(), "repairs": repairs}
            )
    for path in c_files:
        if not path.exists():
            continue
        repairs = repair_c_runaways(project, path)
        if repairs:
            repaired_files.add(path.relative_to(project).as_posix())
            runaway_repairs.append(
                {"file": path.relative_to(project).as_posix(), "repairs": repairs}
            )

    remaining_placeholders: list[dict[str, str]] = []
    for path in [*assembly_files, *[item for item in c_files if item.exists()]]:
        text = path.read_text(encoding="utf-8")
        for match in BROKEN_PLACEHOLDER_RE.finditer(text):
            remaining_placeholders.append(
                {
                    "file": path.relative_to(project).as_posix(),
                    "fragment": match.group(0),
                }
            )
            if len(remaining_placeholders) >= 20:
                break
        if len(remaining_placeholders) >= 20:
            break

    report = {
        "version": "1.3",
        "repaired_placeholders": repaired_placeholders,
        "runaway_translations_repaired": sum(
            len(item["repairs"]) for item in runaway_repairs
        ),
        "runaway_repairs": runaway_repairs,
        "files_changed": len(repaired_files),
        "repaired_files": sorted(repaired_files),
        "remaining_broken_placeholders": remaining_placeholders,
        "valid": not remaining_placeholders,
        "rules": [
            "Control codes may not occur inside {...} placeholders",
            "Mapped strings may not exceed 1000 UTF-8 bytes",
            "Grossly expanded or repetitive machine translations fall back safely",
        ],
    }
    report_path = args.report or project / "sanitization_v1.3.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if remaining_placeholders:
        raise RuntimeError("Broken placeholders remain after sanitization")


if __name__ == "__main__":
    main()
