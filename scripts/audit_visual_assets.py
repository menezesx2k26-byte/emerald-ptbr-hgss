from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from common import read_jasc
from release import release_tag, release_version
from sprites import (
    CASTFORM_FORM_SOURCES,
    UNOWN_FORM_SOURCES,
    destination,
    national_dex_symbols,
)


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
    try:
        with Image.open(path) as image:
            if image.size != expected_size:
                problems.append(f"wrong size {image.size}, expected {expected_size}: {path}")
            if image.mode != "P":
                problems.append(f"wrong mode {image.mode}, expected P: {path}")
            else:
                minimum, maximum = image.getextrema()
                if minimum < 0 or maximum > 15:
                    problems.append(
                        f"palette index outside 0..15 ({minimum}..{maximum}): {path}"
                    )
    except OSError as error:
        problems.append(f"invalid image {path}: {error}")
    return problems


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_animation(front: Path, animation: Path) -> tuple[bool, bool, int]:
    if not front.exists() or not animation.exists():
        return False, False, 0
    try:
        with Image.open(front) as front_image, Image.open(animation) as animation_image:
            first_frame = animation_image.crop((0, 0, 64, 64))
            second_frame = animation_image.crop((0, 64, 64, 128))
            first_matches = first_frame.tobytes() == front_image.tobytes()
            second_differs = first_frame.tobytes() != second_frame.tobytes()
            changed_pixels = sum(
                first != second
                for first, second in zip(first_frame.getdata(), second_frame.getdata())
            )
    except OSError:
        return False, False, 0
    return first_matches, second_differs, changed_pixels


def inspect_single_frame(front: Path, animation: Path) -> bool:
    if not front.exists() or not animation.exists():
        return False
    try:
        with Image.open(front) as front_image, Image.open(animation) as animation_image:
            return front_image.tobytes() == animation_image.tobytes()
    except OSError:
        return False


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
        expected_animation_size = (64, 64) if symbol == "CASTFORM" else (64, 128)
        problems.extend(inspect_indexed_image(animation, expected_animation_size))
        palette_root = project / "graphics/pokemon/unown" if symbol == "UNOWN" else root
        for palette_name in ("normal.pal", "shiny.pal"):
            palette = palette_root / palette_name
            try:
                read_jasc(palette)
            except (FileNotFoundError, ValueError) as error:
                problems.append(f"invalid palette {palette}: {error}")
        if symbol == "CASTFORM" and animation.exists() and front.exists():
            if not inspect_single_frame(front, animation):
                first_frame_mismatch.append(symbol)
        elif animation.exists() and front.exists():
            first_matches, second_differs, changed = inspect_animation(front, animation)
            if not first_matches:
                first_frame_mismatch.append(symbol)
            if not second_differs:
                duplicate_second_frame.append(symbol)
            changed_pixels.append(changed)
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
            "derived from the same indexed artwork; Black/White assets are not mixed in. Castform "
            "keeps one frame per weather form because its four animation indices select forms."
        ),
    }


def expected_alternative_forms(project: Path) -> dict[str, dict[str, str]]:
    unown_root = project / "graphics/pokemon/unown"
    castform_root = project / "graphics/pokemon/castform"
    expected = {
        f"unown/{form}": {
            "family": "unown",
            "form": form,
            "source_id": source_id,
            "destination": (unown_root / form).relative_to(project).as_posix(),
        }
        for form, source_id in UNOWN_FORM_SOURCES.items()
        if form != "a"
    }
    expected.update({
        f"castform/{form}": {
            "family": "castform",
            "form": form,
            "source_id": source_id,
            "destination": (castform_root / form).relative_to(project).as_posix(),
        }
        for form, source_id in CASTFORM_FORM_SOURCES.items()
    })
    return expected


def audit_alternative_forms(project: Path) -> dict[str, object]:
    report_path = project / f"form_import_{release_tag()}.json"
    if not report_path.exists():
        return {
            "valid": False,
            "forms_checked": 0,
            "problems": [f"missing: {report_path}"],
        }

    source_report = json.loads(report_path.read_text(encoding="utf-8"))
    expected = expected_alternative_forms(project)
    problems: list[str] = []
    static_forms: list[str] = []
    first_frame_mismatches: list[str] = []
    changed_pixels: list[int] = []

    records = source_report.get("forms")
    if not isinstance(records, list):
        records = []
        problems.append("form import report has no forms list")
    by_key: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            problems.append("form import report contains a non-object record")
            continue
        key = f"{record.get('family')}/{record.get('form')}"
        if key in by_key:
            problems.append(f"duplicate form record: {key}")
        by_key[key] = record

    missing_records = sorted(set(expected) - set(by_key))
    unexpected_records = sorted(set(by_key) - set(expected))
    if missing_records:
        problems.append(f"missing form records: {', '.join(missing_records)}")
    if unexpected_records:
        problems.append(f"unexpected form records: {', '.join(unexpected_records)}")
    if source_report.get("alternative_forms_imported") != len(expected):
        problems.append(
            "alternative_forms_imported does not match the 30 expected alternative forms"
        )
    if source_report.get("unown_shared_palette") is not True:
        problems.append("Unown shared palette policy was not recorded")
    if source_report.get("castform_per_form_palettes") is not True:
        problems.append("Castform per-form palette policy was not recorded")

    for key, form in expected.items():
        record = by_key.get(key)
        if record is None:
            continue
        for field in ("family", "form", "source_id", "destination"):
            if record.get(field) != form[field]:
                problems.append(
                    f"{key}: {field} {record.get(field)!r} != {form[field]!r}"
                )

        root = project / form["destination"]
        front = root / "front.png"
        back = root / "back.png"
        animation = root / "anim_front.png"
        problems.extend(inspect_indexed_image(front, (64, 64)))
        problems.extend(inspect_indexed_image(back, (64, 64)))
        expected_animation_size = (64, 64) if form["family"] == "castform" else (64, 128)
        problems.extend(inspect_indexed_image(animation, expected_animation_size))
        palette_root = project / "graphics/pokemon/unown" if form["family"] == "unown" else root
        for palette_name in ("normal.pal", "shiny.pal"):
            palette = palette_root / palette_name
            try:
                read_jasc(palette)
            except (FileNotFoundError, ValueError) as error:
                problems.append(f"invalid palette {palette}: {error}")

        output_sha256 = record.get("output_sha256")
        if not isinstance(output_sha256, dict):
            problems.append(f"{key}: output SHA-256 map is missing")
        else:
            for name in ("front.png", "back.png", "anim_front.png"):
                path = root / name
                if path.exists() and output_sha256.get(name) != file_sha256(path):
                    problems.append(f"{key}: output SHA-256 mismatch for {name}")

        source_sha256 = record.get("source_sha256")
        if not isinstance(source_sha256, dict) or any(
            not isinstance(source_sha256.get(name), str)
            or len(str(source_sha256.get(name))) != 64
            for name in ("front", "back", "shiny_front", "shiny_back")
        ):
            problems.append(f"{key}: incomplete source SHA-256 provenance")

        if form["family"] == "castform" and front.exists() and animation.exists():
            if not inspect_single_frame(front, animation):
                first_frame_mismatches.append(key)
        elif front.exists() and animation.exists():
            first_matches, second_differs, changed = inspect_animation(front, animation)
            if not first_matches:
                first_frame_mismatches.append(key)
            if not second_differs:
                static_forms.append(key)
            changed_pixels.append(changed)

    valid = not problems and not static_forms and not first_frame_mismatches
    return {
        "valid": valid,
        "forms_checked": len(expected),
        "unown_forms_checked": len(UNOWN_FORM_SOURCES) - 1,
        "castform_forms_checked": len(CASTFORM_FORM_SOURCES),
        "problems": problems,
        "static_animation_frame_count": len(static_forms),
        "static_animation_forms": static_forms,
        "first_frame_mismatch_count": len(first_frame_mismatches),
        "first_frame_mismatch_forms": first_frame_mismatches,
        "changed_pixels_min": min(changed_pixels, default=0),
        "changed_pixels_max": max(changed_pixels, default=0),
        "unown_palette_policy": "One shared normal/shiny palette for all 28 forms.",
        "castform_palette_policy": "One normal/shiny palette pair per weather form.",
        "castform_animation_policy": "One 64x64 frame per form; the four engine animation indices are form selectors.",
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
    alternative_forms = audit_alternative_forms(project)
    overworlds = audit_overworlds(project)
    water = audit_water(project)
    maps = audit_maps(project)
    valid = (
        pokemon["valid"]
        and alternative_forms["valid"]
        and overworlds["valid"]
        and water["valid"]
        and maps["valid"]
    )
    report = {
        "version": release_version(),
        "valid": valid,
        "pokemon_battle_sprites": pokemon,
        "alternative_forms": alternative_forms,
        "human_overworlds": overworlds,
        "water_and_field_effects": water,
        "map_overhaul": maps,
    }
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "valid": valid,
        "pokemon_species_checked": pokemon["species_checked"],
        "alternative_forms_checked": alternative_forms["forms_checked"],
        "human_overworlds_copied": overworlds.get("copied_count"),
        "water_assets_checked": water["assets_checked"],
        "map_layouts_checked": maps["layouts_checked"],
        "static_animation_frame_count": pokemon["static_animation_frame_count"],
    }, indent=2, ensure_ascii=False))
    if not valid:
        raise SystemExit("Visual asset audit failed")


if __name__ == "__main__":
    main()
