from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from common import read_jasc
from release import release_tag, release_version
from sprites import destination, national_dex_symbols


EXPECTED_LAYOUTS = {
    "LittlerootTown_Layout": ("gTileset_HGSSGeneralTown", "gTileset_HGSSSmallTown"),
    "OldaleTown_Layout": ("gTileset_HGSSGeneralTown", "gTileset_HGSSSmallTown"),
    "Route101_Layout": ("gTileset_HGSSGeneralTown", "gTileset_HGSSSmallTown"),
    "PetalburgWoods_Layout": ("gTileset_HGSSGeneralForest", "gTileset_HGSSForest"),
}


def inspect_indexed_image(path: Path, expected_size: tuple[int, int]) -> list[str]:
    problems: list[str] = []
    if not path.exists():
        return [f"missing: {path}"]
    with Image.open(path) as image:
        if image.size != expected_size:
            problems.append(f"wrong size {image.size}, expected {expected_size}: {path}")
        if image.mode != "P":
            problems.append(f"wrong mode {image.mode}, expected P: {path}")
        else:
            minimum, maximum = image.getextrema()
            if minimum < 0 or maximum > 15:
                problems.append(f"palette index outside 0..15 ({minimum}..{maximum}): {path}")
    return problems


def audit_pokemon(project: Path) -> dict[str, object]:
    problems: list[str] = []
    invalid_symbols: list[str] = []
    duplicate_second_frame: list[str] = []
    first_frame_mismatch: list[str] = []
    changed_pixels: list[int] = []
    symbols = national_dex_symbols(project)
    for symbol in symbols:
        problem_count_before = len(problems)
        root = destination(project, symbol)
        front = root / "front.png"
        back = root / "back.png"
        animation = root / "anim_front.png"
        problems.extend(inspect_indexed_image(front, (64, 64)))
        problems.extend(inspect_indexed_image(back, (64, 64)))
        problems.extend(inspect_indexed_image(animation, (64, 128)))
        for palette_name in ("normal.pal", "shiny.pal"):
            palette = root / palette_name
            try:
                read_jasc(palette)
            except (FileNotFoundError, ValueError) as error:
                problems.append(f"invalid palette {palette}: {error}")
        if animation.exists():
            with Image.open(animation) as image:
                first_frame = image.crop((0, 0, 64, 64))
                second_frame = image.crop((0, 64, 64, 128))
                if front.exists():
                    with Image.open(front) as front_image:
                        if first_frame.tobytes() != front_image.tobytes():
                            first_frame_mismatch.append(symbol)
                if first_frame.tobytes() == second_frame.tobytes():
                    duplicate_second_frame.append(symbol)
                changed_pixels.append(
                    sum(a != b for a, b in zip(first_frame.getdata(), second_frame.getdata()))
                )
        if len(problems) > problem_count_before:
            invalid_symbols.append(symbol)

    valid = not problems and not duplicate_second_frame and not first_frame_mismatch
    return {
        "valid": valid,
        "species_checked": len(symbols),
        "valid_species": len(symbols) - len(invalid_symbols),
        "invalid_species": invalid_symbols,
        "problems": problems,
        "static_animation_frame_count": len(duplicate_second_frame),
        "static_animation_species": duplicate_second_frame,
        "first_frame_mismatch_count": len(first_frame_mismatch),
        "first_frame_mismatch_species": first_frame_mismatch,
        "changed_pixels_min": min(changed_pixels, default=0),
        "changed_pixels_max": max(changed_pixels, default=0),
        "animation_policy": (
            "Frame one preserves the imported HGSS pose. Frame two applies a one-pixel idle lift "
            "derived from the same indexed artwork; Black/White assets are not mixed in."
        ),
    }


def audit_overworlds(project: Path) -> dict[str, object]:
    report_path = project / f"overworld_import_{release_tag()}.json"
    if not report_path.exists():
        return {"valid": False, "problem": f"missing: {report_path}"}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    valid = (
        report.get("copied_count") == 129
        and report.get("skipped_missing_destination_count") == 0
        and report.get("skipped_dimension_mismatch_count") == 0
        and report.get("fly_animation_alignment_patched") is True
    )
    return {
        "valid": valid,
        "copied_count": report.get("copied_count"),
        "skipped_missing_destination_count": report.get("skipped_missing_destination_count"),
        "skipped_dimension_mismatch_count": report.get("skipped_dimension_mismatch_count"),
        "fly_animation_alignment_patched": report.get("fly_animation_alignment_patched"),
        "palette_strategy": report.get("palette_strategy"),
    }


def audit_water(project: Path) -> dict[str, object]:
    general = project / "data/tilesets/primary/general"
    expected = {
        **{general / f"anim/water/{index}.png": (16, 120) for index in range(8)},
        **{general / f"anim/waterfall/{index}.png": (8, 48) for index in range(4)},
        project / "graphics/field_effects/pics/surf_blob.png": (96, 32),
        project / "graphics/field_effects/pics/ripple.png": (80, 16),
        project / "graphics/field_effects/pics/splash.png": (32, 8),
        project / "graphics/field_effects/pics/water_surfacing.png": (80, 16),
    }
    problems: list[str] = []
    for path, size in expected.items():
        problems.extend(inspect_indexed_image(path, size))
    return {
        "assets_checked": len(expected),
        "problems": problems,
        "valid": not problems,
        "generation_policy": "Water, waterfall, surf, ripple and splash assets are procedurally generated for the GBA palette.",
    }


def audit_maps(project: Path) -> dict[str, object]:
    layouts_path = project / "data/layouts/layouts.json"
    layouts = json.loads(layouts_path.read_text(encoding="utf-8"))["layouts"]
    by_name = {layout["name"]: layout for layout in layouts}
    problems: list[str] = []
    found: dict[str, dict[str, str]] = {}
    for name, expected in EXPECTED_LAYOUTS.items():
        layout = by_name.get(name)
        if layout is None:
            problems.append(f"missing layout: {name}")
            continue
        actual = (layout.get("primary_tileset"), layout.get("secondary_tileset"))
        found[name] = {"primary": str(actual[0]), "secondary": str(actual[1])}
        if actual != expected:
            problems.append(f"{name}: {actual} != {expected}")
    return {
        "layouts_checked": len(EXPECTED_LAYOUTS),
        "layouts": found,
        "problems": problems,
        "valid": not problems,
        "art_policy": "These four layouts use isolated Emerald tilesets with an HGSS-inspired palette treatment, not ripped HGSS map art.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()

    pokemon = audit_pokemon(project)
    overworlds = audit_overworlds(project)
    water = audit_water(project)
    maps = audit_maps(project)
    valid = pokemon["valid"] and overworlds["valid"] and water["valid"] and maps["valid"]
    report = {
        "version": release_version(),
        "valid": valid,
        "pokemon_battle_sprites": pokemon,
        "human_overworlds": overworlds,
        "water_and_field_effects": water,
        "map_overhaul": maps,
    }
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "valid": valid,
        "pokemon_species_checked": pokemon["species_checked"],
        "human_overworlds_copied": overworlds.get("copied_count"),
        "water_assets_checked": water["assets_checked"],
        "map_layouts_checked": maps["layouts_checked"],
        "static_animation_frame_count": pokemon["static_animation_frame_count"],
    }, indent=2, ensure_ascii=False))
    if not valid:
        raise SystemExit("Visual asset audit failed")


if __name__ == "__main__":
    main()
