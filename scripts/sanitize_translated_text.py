from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from release import release_tag, release_version

BLOCK_RE = re.compile(
    r"(?ms)^(?P<label>[A-Za-z_][A-Za-z0-9_]*::?\n)"
    r"(?P<body>(?:[ \t]*\.string[ \t]+\"(?:\\.|[^\"\\])*\"[ \t]*\n)+)"
)
LINE_RE = re.compile(r'\.string\s+"((?:\\.|[^"\\])*)"')
C_RE = re.compile(r'_\("((?:\\.|[^"\\])*)"\)')
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
CONTROL_INSIDE_RE = re.compile(r"\\[nlp]")


def original_text(project: Path, path: Path) -> str:
    relative = path.relative_to(project).as_posix()
    result = subprocess.run(
        ["git", "-C", str(project), "show", f"HEAD:{relative}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def repair_control_spaces(raw: str) -> tuple[str, int]:
    repairs = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal repairs
        value = match.group(0)
        fixed, count = CONTROL_INSIDE_RE.subn(" ", value)
        repairs += count
        return fixed

    return PLACEHOLDER_RE.sub(repl, raw), repairs


def placeholder_multiset(raw: str) -> Counter[str]:
    return Counter(PLACEHOLDER_RE.findall(raw))


def visible_words(raw: str) -> list[str]:
    value = PLACEHOLDER_RE.sub(" ", raw)
    value = re.sub(r"\\[nlp]", " ", value)
    value = value.replace("$", " ")
    return re.findall(r"[A-Za-zÀ-ÿ']+", value.lower())


def repeated_trigram(words: list[str]) -> int:
    if len(words) < 12:
        return 0
    trigrams = Counter(tuple(words[index:index + 3]) for index in range(len(words) - 2))
    return trigrams.most_common(1)[0][1] if trigrams else 0


def pathological(current: str, original: str) -> bool:
    current_words = visible_words(current)
    original_words = visible_words(original)
    if len(current) > max(len(original) * 3, len(original) + 280):
        return True
    if len(current_words) > max(len(original_words) * 3, len(original_words) + 80):
        return True
    if len(current_words) >= 30 and repeated_trigram(current_words) >= 4:
        return True
    if "ZXQ" in current or "QXZ" in current:
        return True
    return False


def unsafe(current: str, original: str) -> str | None:
    if placeholder_multiset(current) != placeholder_multiset(original):
        return "placeholder_mismatch"
    if current.endswith("$") != original.endswith("$"):
        return "terminator_mismatch"
    if pathological(current, original):
        return "pathological_translation"
    return None


def sanitize_c(path: Path, project: Path, report: dict[str, object]) -> None:
    current_text = path.read_text(encoding="utf-8")
    original = original_text(project, path)
    current_matches = list(C_RE.finditer(current_text))
    original_matches = list(C_RE.finditer(original))
    if len(current_matches) != len(original_matches):
        raise RuntimeError(
            f"C string count changed in {path.relative_to(project)}: "
            f"{len(current_matches)} != {len(original_matches)}"
        )

    replacements: list[tuple[int, int, str]] = []
    for current_match, original_match in zip(current_matches, original_matches):
        raw = current_match.group(1)
        original_raw = original_match.group(1)
        fixed, repairs = repair_control_spaces(raw)
        reason = unsafe(fixed, original_raw)
        if reason:
            fixed = original_raw
            report["reverted"][reason] = report["reverted"].get(reason, 0) + 1
        elif repairs:
            report["control_repairs"] += repairs
        if fixed != raw:
            replacements.append((current_match.start(1), current_match.end(1), fixed))

    updated = current_text
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    if updated != current_text:
        path.write_text(updated, encoding="utf-8")
        report["files_changed"].append(path.relative_to(project).as_posix())


def assembly_raw(match: re.Match[str]) -> str:
    return "".join(LINE_RE.findall(match.group("body")))


def sanitize_assembly(path: Path, project: Path, report: dict[str, object]) -> None:
    current_text = path.read_text(encoding="utf-8")
    original = original_text(project, path)
    original_by_label = {
        match.group("label").strip(): match
        for match in BLOCK_RE.finditer(original)
    }
    replacements: list[tuple[int, int, str]] = []

    for current_match in BLOCK_RE.finditer(current_text):
        label = current_match.group("label").strip()
        original_match = original_by_label.get(label)
        if original_match is None:
            continue
        raw = assembly_raw(current_match)
        original_raw = assembly_raw(original_match)
        fixed, repairs = repair_control_spaces(raw)
        reason = unsafe(fixed, original_raw)
        if reason:
            body = original_match.group("body")
            report["reverted"][reason] = report["reverted"].get(reason, 0) + 1
        elif repairs:
            body = f'\t.string "{fixed}"\n'
            report["control_repairs"] += repairs
        else:
            continue
        replacements.append((current_match.start("body"), current_match.end("body"), body))

    updated = current_text
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    if updated != current_text:
        path.write_text(updated, encoding="utf-8")
        report["files_changed"].append(path.relative_to(project).as_posix())


def validate(project: Path, files: list[Path]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in PLACEHOLDER_RE.finditer(text):
            if CONTROL_INSIDE_RE.search(match.group(0)):
                problems.append(
                    {
                        "file": path.relative_to(project).as_posix(),
                        "placeholder": match.group(0),
                    }
                )
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
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
    c_files = [path for path in c_files if path.exists()]

    report: dict[str, object] = {
        "version": release_version(),
        "control_repairs": 0,
        "reverted": {},
        "files_changed": [],
        "validation_problems": [],
    }
    for path in assembly_files:
        sanitize_assembly(path, project, report)
    for path in c_files:
        sanitize_c(path, project, report)

    problems = validate(project, assembly_files + c_files)
    report["validation_problems"] = problems
    report_path = args.report or project / f"translation_sanitizer_{release_tag()}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if problems:
        raise SystemExit("Broken control placeholders remain after sanitization")


if __name__ == "__main__":
    main()
