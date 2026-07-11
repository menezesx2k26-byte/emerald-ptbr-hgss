from __future__ import annotations

import argparse
import json
from pathlib import Path

REPLACEMENTS = {
    "ã": "ä",
    "õ": "ö",
    "Ã": "Ä",
    "Õ": "Ö",
}


def normalize_file(path: Path) -> dict[str, int]:
    original = path.read_text(encoding="utf-8")
    updated = original
    counts: dict[str, int] = {}
    for source, target in REPLACEMENTS.items():
        count = updated.count(source)
        if count:
            counts[f"{source}->{target}"] = count
            updated = updated.replace(source, target)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
    return counts


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

    remaining: list[dict[str, str]] = []
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for character in REPLACEMENTS:
            if character in text:
                remaining.append(
                    {
                        "file": path.relative_to(project).as_posix(),
                        "character": character,
                    }
                )

    report = {
        "version": "1.3",
        "total_replacements": total,
        "files_changed": len(changed),
        "changes": changed,
        "remaining_unsupported_tildes": remaining,
        "valid": not remaining,
        "rule": "The Emerald PT-BR charmap represents ã/õ as ä/ö.",
    }
    report_path = args.report or project / "charmap_normalization_v1.3.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if remaining:
        raise RuntimeError("Unsupported tilde characters remain")


if __name__ == "__main__":
    main()
