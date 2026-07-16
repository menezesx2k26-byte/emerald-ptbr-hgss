from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from release import release_tag, release_version


PLAYER_ACTIONS = (
    "acro_bike.png",
    "decorating.png",
    "field_move.png",
    "fishing.png",
    "mach_bike.png",
    "running.png",
    "surfing.png",
    "underwater.png",
    "walking.png",
    "watering.png",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _palette_colors(image: Image.Image) -> list[tuple[int, int, int]]:
    palette = image.getpalette()
    if palette is None:
        raise ValueError("Player overworld must use an indexed palette")
    return [tuple(palette[index:index + 3]) for index in range(0, len(palette), 3)]


def _find_palette_index(
    colors: list[tuple[int, int, int]],
    candidates: tuple[tuple[int, int, int], ...],
    *,
    maximum_distance: int = 18,
) -> int:
    best_index = -1
    best_distance = 1 << 30
    for index, color in enumerate(colors[:16]):
        for candidate in candidates:
            distance = sum((left - right) ** 2 for left, right in zip(color, candidate))
            if distance < best_distance:
                best_distance = distance
                best_index = index
    if best_index < 0 or best_distance > maximum_distance ** 2:
        raise ValueError(f"Required palette role was not found: {candidates}")
    return best_index


def _set_palette_color(palette: list[int], index: int, color: tuple[int, int, int]) -> None:
    palette[index * 3:index * 3 + 3] = color


def _pixel_data(image: Image.Image) -> list[int]:
    if hasattr(image, "get_flattened_data"):
        return list(image.get_flattened_data())
    return list(image.getdata())


def _redesign_brendan(image: Image.Image) -> int:
    colors = _palette_colors(image)
    white = _find_palette_index(colors, ((255, 255, 255), (255, 253, 253)))
    gray = _find_palette_index(colors, ((222, 230, 238), (192, 200, 216)))
    green_dark = _find_palette_index(colors, ((74, 148, 82), (78, 157, 95)))
    green_light = _find_palette_index(colors, ((115, 205, 115), (103, 203, 124)))
    red_dark = _find_palette_index(colors, ((123, 65, 65), (120, 64, 64), (144, 64, 40)))
    red_light = _find_palette_index(colors, ((255, 98, 90), (224, 112, 80)))

    source = _pixel_data(image)
    output = source.copy()
    for offset, index in enumerate(source):
        y = offset // image.width
        if index == white:
            if y <= 14:
                output[offset] = white
            else:
                output[offset] = green_dark
        elif index == gray:
            if y <= 14:
                output[offset] = gray
            else:
                output[offset] = green_light
        elif index == green_dark:
            output[offset] = red_dark
        elif index == green_light:
            output[offset] = red_light

    palette = image.getpalette()
    if palette is None:
        raise ValueError("Player overworld must use an indexed palette")
    _set_palette_color(palette, white, (255, 197, 49))
    _set_palette_color(palette, gray, (213, 139, 32))
    _set_palette_color(palette, green_dark, (255, 255, 255))
    _set_palette_color(palette, green_light, (222, 230, 238))
    _set_palette_color(palette, red_dark, (197, 65, 65))
    image.putdata(output)
    image.putpalette(palette)
    return sum(left != right for left, right in zip(source, output))


def _redesign_may(image: Image.Image) -> int:
    colors = _palette_colors(image)
    green_light = _find_palette_index(colors, ((106, 213, 65),))
    green_dark = _find_palette_index(colors, ((65, 172, 32),))
    white = _find_palette_index(colors, ((255, 255, 255),))
    gray = _find_palette_index(colors, ((205, 205, 222),))
    red_dark = _find_palette_index(colors, ((197, 65, 65),))
    red_light = _find_palette_index(colors, ((255, 98, 90),))
    navy = _find_palette_index(colors, ((41, 57, 65),))

    source = _pixel_data(image)
    output = source.copy()
    for offset, index in enumerate(source):
        y = offset // image.width
        if index == green_light:
            output[offset] = white if y <= 16 else red_light
        elif index == green_dark:
            output[offset] = gray if y <= 16 else red_dark
        elif index in (red_dark, red_light):
            output[offset] = navy
    image.putdata(output)
    return sum(left != right for left, right in zip(source, output))


def apply_player_redesign(destination_root: Path) -> dict[str, object]:
    records: list[dict[str, object]] = []
    total_changed_pixels = 0

    for player, redesign in (("brendan", _redesign_brendan), ("may", _redesign_may)):
        for action in PLAYER_ACTIONS:
            path = destination_root / player / action
            if not path.exists():
                raise FileNotFoundError(path)
            before_sha256 = _sha256(path)
            with Image.open(path) as source:
                image = source.copy()
            if image.mode != "P":
                raise ValueError(f"Player overworld is not indexed: {path}")

            # Diving uses the engine's shared blue silhouette and has no visible
            # clothing palette. The other nine sheets carry the v1.4 uniform.
            changed_pixels = 0 if action == "underwater.png" else redesign(image)
            used_colors = image.getcolors(maxcolors=17)
            if used_colors is None or len(used_colors) > 16:
                raise ValueError(f"Player overworld exceeds 16 colors: {path}")
            image.save(path)
            after_sha256 = _sha256(path)
            if action != "underwater.png" and (changed_pixels == 0 or before_sha256 == after_sha256):
                raise ValueError(f"Player redesign did not change {path}")

            total_changed_pixels += changed_pixels
            records.append(
                {
                    "player": player,
                    "action": action,
                    "path": path.relative_to(destination_root).as_posix(),
                    "changed_pixels": changed_pixels,
                    "source_sha256": before_sha256,
                    "output_sha256": after_sha256,
                }
            )

    return {
        "style": "v1.4 Hoenn field uniforms: gold/red Brendan and white/red/blue May",
        "identity_policy": "Brendan and May identities and all native Emerald action sheets are preserved.",
        "underwater_policy": "The native shared blue diving silhouette is preserved.",
        "files_checked": len(records),
        "files_changed": sum(record["changed_pixels"] > 0 for record in records),
        "total_changed_pixels": total_changed_pixels,
        "records": records,
    }


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

    player_redesign = apply_player_redesign(destination_root)

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
        "version": release_version(),
        "source": "Team Aqua Asset Repo / RavePossum / Poffin-Case-Overworlds-Converted",
        "copied_count": len(copied),
        "copied": copied,
        "skipped_missing_destination_count": len(skipped_missing_destination),
        "skipped_missing_destination": skipped_missing_destination,
        "skipped_dimension_mismatch_count": len(skipped_dimension_mismatch),
        "skipped_dimension_mismatch": skipped_dimension_mismatch,
        "fly_animation_alignment_patched": True,
        "palette_strategy": "Shared GBA palettes preserved; player clothing receives a deterministic v1.4 redesign.",
        "player_redesign": player_redesign,
    }
    (project / f"overworld_import_{release_tag()}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Overworld sprites copied: {len(copied)}")
    return report
