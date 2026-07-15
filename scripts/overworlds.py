from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image


def import_overworld_sprites(project: Path, assets_root: Path) -> dict[str, object]:
    destination_root = project / "graphics/object_events/pics/people"
    if not destination_root.exists():
        raise FileNotFoundError(destination_root)
    if not assets_root.exists():
        raise FileNotFoundError(assets_root)

    copied: list[str] = []
    skipped_missing_destination: list[str] = []
    skipped_dimension_mismatch: list[dict[str, object]] = []

    for source in sorted(assets_root.rglob("*.png")):
        relative = source.relative_to(assets_root)
        if relative.name == "og_underwater.png":
            continue
        destination = destination_root / relative
        if not destination.exists():
            skipped_missing_destination.append(relative.as_posix())
            continue

        source_size = Image.open(source).size
        destination_size = Image.open(destination).size
        if source_size != destination_size:
            skipped_dimension_mismatch.append(
                {
                    "path": relative.as_posix(),
                    "source_size": list(source_size),
                    "destination_size": list(destination_size),
                }
            )
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative.as_posix())

    field_effect = project / "src/field_effect.c"
    text = field_effect.read_text(encoding="utf-8")
    first_old = "sprite->x = 0x76;"
    first_new = "sprite->x = 0x80;"
    second_old = "sprite->x2 = Cos(sprite->data[1], 0x20);"
    second_new = "sprite->x2 = Cos(sprite->data[1], 0x40);"

    if first_old in text:
        text = text.replace(first_old, first_new, 1)
    elif first_new not in text:
        raise RuntimeError("Fly animation alignment point was not found")

    if second_old in text:
        text = text.replace(second_old, second_new, 1)
    elif second_new not in text:
        raise RuntimeError("Fly return alignment point was not found")

    field_effect.write_text(text, encoding="utf-8")

    report: dict[str, object] = {
        "version": "1.3.1",
        "source": "Team Aqua Asset Repo / RavePossum / Poffin-Case-Overworlds-Converted",
        "copied_count": len(copied),
        "copied": copied,
        "skipped_missing_destination_count": len(skipped_missing_destination),
        "skipped_missing_destination": skipped_missing_destination,
        "skipped_dimension_mismatch_count": len(skipped_dimension_mismatch),
        "skipped_dimension_mismatch": skipped_dimension_mismatch,
        "fly_animation_alignment_patched": True,
        "palette_strategy": "vanilla shared palettes preserved",
    }
    (project / "overworld_import_v1.3.1.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Overworld sprites copied: {len(copied)}")
    return report
