from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPLACEMENTS = {
    "ã": "ä",
    "õ": "ö",
    "Ã": "Ä",
    "Õ": "Ö",
    "‡": "-",
    "°": "º",
    "ї": "-",
    "Ş": "-",
    "—": "-",
    "–": "-",
    "•": "·",
    "\u00a0": " ",
}

BLOCK_RE = re.compile(
    r'(?ms)^(?P<label>[A-Za-z_][A-Za-z0-9_]*::?\n)'
    r'(?P<body>(?:[ \t]*\.string[ \t]+"(?:\\.|[^"\\])*"[ \t]*\n)+)'
)
LINE_RE = re.compile(r'\.string\s+"((?:\\.|[^"\\])*)"')
C_RE = re.compile(r'_\("((?:\\.|[^"\\])*)"\)')
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
CONTROL_RE = re.compile(r'\\(?:n|l|p|"|\\)')
CHARMAP_CHAR_RE = re.compile(r"^'((?:\\.|[^'])*)'\s*=", re.MULTILINE)


def normalize_file(path: Path) -> dict[str, int]:
    original = path.read_text(encoding="utf-8")
    updated = original
    counts: dict[str, int] = {}
    for source, target in REPLACEMENTS.items():
        count = updated.count(source)
        if count:
            counts[f"U+{ord(source):04X}->{target}"] = count
            updated = updated.replace(source, target)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
    return counts


def parse_charmap(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    allowed: set[str] = set()
    for match in CHARMAP_CHAR_RE.finditer(text):
        raw = match.group(1)
        if raw == r"\'":
            allowed.add("'")
        elif raw.startswith("\\") and len(raw) == 2:
            allowed.add(raw[1])
        else:
            allowed.update(raw)
    return allowed


def encoded_strings(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".inc":
        return [
            value
            for block in BLOCK_RE.finditer(text)
            for value in LINE_RE.findall(block.group("body"))
        ]
    return C_RE.findall(text)


def unsupported_characters(path: Path, allowed: set[str]) -> list[dict[str, object]]:
    problems: list[dict[str, object]] = []
    for string_index, raw in enumerate(encoded_strings(path)):
        visible = PLACEHOLDER_RE.sub("", raw)
        visible = CONTROL_RE.sub("", visible)
        visible = visible.removesuffix("$")
        for character in visible:
            if character in allowed or character in "\n\r\t":
                continue
            problems.append(
                {
                    "string_index": string_index,
                    "character": character,
                    "codepoint": f"U+{ord(character):04X}",
                    "preview": raw[:160],
                }
            )
            if len(problems) >= 20:
                return problems
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()

    files = sorted((project / "data/maps").rglob("scripts.inc"))
    files += sorted((project / "data/text").glob("*.inc"))
    files += sorted((project / "data/scripts").glob("*.inc"))
    files += [
        project / "src/strings.c",
        project / "src/battle_message.c",
        project / "src/berry.c",
        project / "src/berry_blender.c",
        project / "src/mystery_event_msg.c",
        project / "src/data/union_room.h",
        project / "src/data/text/match_call_messages.h",
    ]

    changed: list[dict[str, object]] = []
    total = 0
    for path in files:
        if not path.exists():
            continue
        counts = normalize_file(path)
        if counts:
            replacements = sum(counts.values())
            total += replacements
            changed.append(
                {
                    "file": path.relative_to(project).as_posix(),
                    "replacements": replacements,
                    "details": counts,
                }
            )

    allowed = parse_charmap(project / "charmap.txt")
    unsupported: list[dict[str, object]] = []
    for path in files:
        if not path.exists():
            continue
        problems = unsupported_characters(path, allowed)
        if problems:
            unsupported.append(
                {
                    "file": path.relative_to(project).as_posix(),
                    "problems": problems,
                }
            )
            if sum(len(item["problems"]) for item in unsupported) >= 20:
                break

    report = {
        "version": "1.3.1",
        "total_replacements": total,
        "files_changed": len(changed),
        "changes": changed,
        "unsupported_encoded_characters": unsupported,
        "valid": not unsupported,
        "rules": [
            "The Emerald PT-BR charmap represents ã/õ as ä/ö.",
            "All visible characters in encoded strings must exist in charmap.txt.",
        ],
    }
    report_path = args.report or project / "charmap_normalization_v1.3.1.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if unsupported:
        raise RuntimeError("Unsupported encoded characters remain")


if __name__ == "__main__":
    main()
