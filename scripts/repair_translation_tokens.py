from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import translate_ptbr as base

TOKEN_ARTIFACT_RE = re.compile(
    r"(?:ZXQ|ZXXQ|ZQ\d{1,3}QXZ|QXZ|QXQ|QX(?:\s+QX){2,})",
    flags=re.IGNORECASE,
)


def git_original(project: Path, path: Path) -> str:
    relative = path.relative_to(project).as_posix()
    return subprocess.check_output(
        ["git", "-C", str(project), "show", f"HEAD:{relative}"],
        text=True,
        encoding="utf-8",
    )


def repair_assembly(project: Path, path: Path) -> list[dict[str, object]]:
    current = path.read_text(encoding="utf-8")
    original = git_original(project, path)
    original_by_label = {
        match.group("label").strip(): match
        for match in base.BLOCK_RE.finditer(original)
    }

    replacements: list[tuple[int, int, str]] = []
    repairs: list[dict[str, object]] = []
    for match in base.BLOCK_RE.finditer(current):
        raw = "".join(base.LINE_RE.findall(match.group("body")))
        artifacts = sorted(set(TOKEN_ARTIFACT_RE.findall(raw)))
        if not artifacts:
            continue
        label = match.group("label").strip()
        original_match = original_by_label.get(label)
        if original_match is None:
            raise RuntimeError(f"No original block found for {label} in {path}")
        replacements.append(
            (
                match.start("body"),
                match.end("body"),
                original_match.group("body"),
            )
        )
        repairs.append(
            {
                "label": label,
                "artifacts": artifacts[:10],
                "strategy": "restore_original_block",
            }
        )

    updated = current
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    if replacements:
        path.write_text(updated, encoding="utf-8")
    return repairs


def repair_c(project: Path, path: Path) -> list[dict[str, object]]:
    current = path.read_text(encoding="utf-8")
    original = git_original(project, path)
    current_matches = list(base.C_RE.finditer(current))
    original_matches = list(base.C_RE.finditer(original))
    if len(current_matches) != len(original_matches):
        raise RuntimeError(
            f"String count mismatch in {path.relative_to(project)}: "
            f"{len(current_matches)} != {len(original_matches)}"
        )

    replacements: list[tuple[int, int, str]] = []
    repairs: list[dict[str, object]] = []
    for index, (translated, source) in enumerate(zip(current_matches, original_matches)):
        raw = translated.group(1)
        artifacts = sorted(set(TOKEN_ARTIFACT_RE.findall(raw)))
        if not artifacts:
            continue
        replacements.append((translated.start(1), translated.end(1), source.group(1)))
        repairs.append(
            {
                "string_index": index,
                "artifacts": artifacts[:10],
                "strategy": "restore_original_string",
                "original_preview": source.group(1)[:120],
            }
        )

    updated = current
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    if replacements:
        path.write_text(updated, encoding="utf-8")
    return repairs


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

    changed: list[dict[str, object]] = []
    for path in assembly_files:
        repairs = repair_assembly(project, path)
        if repairs:
            changed.append(
                {
                    "file": path.relative_to(project).as_posix(),
                    "repairs": repairs,
                }
            )
    for path in c_files:
        if not path.exists():
            continue
        repairs = repair_c(project, path)
        if repairs:
            changed.append(
                {
                    "file": path.relative_to(project).as_posix(),
                    "repairs": repairs,
                }
            )

    remaining: list[dict[str, str]] = []
    for path in [*assembly_files, *[item for item in c_files if item.exists()]]:
        text = path.read_text(encoding="utf-8")
        for match in TOKEN_ARTIFACT_RE.finditer(text):
            remaining.append(
                {
                    "file": path.relative_to(project).as_posix(),
                    "artifact": match.group(0),
                }
            )
            if len(remaining) >= 20:
                break
        if len(remaining) >= 20:
            break

    report = {
        "version": "1.3.1",
        "blocks_or_strings_restored": sum(len(item["repairs"]) for item in changed),
        "files_changed": len(changed),
        "changes": changed,
        "remaining_token_artifacts": remaining,
        "valid": not remaining,
        "policy": "Corrupted placeholder tokens fall back to the original source text.",
    }
    report_path = args.report or project / "translation_token_repair_v1.3.1.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if remaining:
        raise RuntimeError("Translation placeholder artifacts remain")


if __name__ == "__main__":
    main()
