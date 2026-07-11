from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path

import translate_ptbr as base

BROKEN_PLACEHOLDER_RE = re.compile(r"\{[^{}]*(?:\\n|\\l|\\p)[^{}]*\}")


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


def repair_assembly(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    replacements: list[tuple[int, int, str]] = []
    for match in base.BLOCK_RE.finditer(original):
        raw = "".join(base.LINE_RE.findall(match.group("body")))
        if not BROKEN_PLACEHOLDER_RE.search(raw):
            continue
        paragraphs, terminal = base.split_raw(raw)
        replacements.append(
            (
                match.start("body"),
                match.end("body"),
                safe_encode(paragraphs, terminal, True),
            )
        )
    if not replacements:
        return 0
    updated = original
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    path.write_text(updated, encoding="utf-8")
    return len(replacements)


def repair_c(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    replacements: list[tuple[int, int, str]] = []
    for match in base.C_RE.finditer(original):
        raw = match.group(1)
        if not BROKEN_PLACEHOLDER_RE.search(raw):
            continue
        paragraphs, terminal = base.split_raw(raw)
        replacements.append(
            (
                match.start(1),
                match.end(1),
                safe_encode(paragraphs, terminal, False),
            )
        )
    if not replacements:
        return 0
    updated = original
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    path.write_text(updated, encoding="utf-8")
    return len(replacements)


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

    repaired_files: list[str] = []
    repaired_placeholders = 0
    for path in assembly_files:
        count = repair_assembly(path)
        if count:
            repaired_placeholders += count
            repaired_files.append(path.relative_to(project).as_posix())
    for path in c_files:
        if not path.exists():
            continue
        count = repair_c(path)
        if count:
            repaired_placeholders += count
            repaired_files.append(path.relative_to(project).as_posix())

    remaining: list[dict[str, str]] = []
    for path in [*assembly_files, *[item for item in c_files if item.exists()]]:
        text = path.read_text(encoding="utf-8")
        for match in BROKEN_PLACEHOLDER_RE.finditer(text):
            remaining.append(
                {
                    "file": path.relative_to(project).as_posix(),
                    "fragment": match.group(0),
                }
            )
            if len(remaining) >= 20:
                break
        if len(remaining) >= 20:
            break

    report = {
        "version": "1.3",
        "repaired_placeholders": repaired_placeholders,
        "files_changed": len(repaired_files),
        "repaired_files": repaired_files,
        "remaining_broken_placeholders": remaining,
        "valid": not remaining,
        "rule": "Control codes may not occur inside {...} placeholders",
    }
    report_path = args.report or project / "sanitization_v1.3.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if remaining:
        raise RuntimeError("Broken placeholders remain after sanitization")


if __name__ == "__main__":
    main()
