from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, Sequence
from xml.etree import ElementTree

from PIL import Image, ImageDraw, ImageSequence

from common import apply_palette, read_jasc
from sprites import destination, import_hgss_sprites, national_dex_symbols


MOD_NAME = "Emerald HGSS Visual 386"
MOD_VERSION = "0.1.0"
MOD_AUTHOR = "Gabriel Menezes"
SPRITE_SCALE = 3.0
EXPECTED_SPECIES = 386
VARIANTS = ("front-n", "front-s", "back-n", "back-s")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deterministic_zip_write(archive: zipfile.ZipFile, path: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def palette_image(image: Image.Image, palette: Sequence[tuple[int, int, int]]) -> Image.Image:
    if image.mode != "P":
        raise ValueError("PokeMMO export expects indexed Emerald sprites")
    output = image.copy()
    apply_palette(output, palette)
    output.info["transparency"] = 0
    return output


def animation_frames(path: Path, palette: Sequence[tuple[int, int, int]]) -> list[Image.Image]:
    with Image.open(path) as source:
        if source.mode != "P" or source.width != 64 or source.height not in (64, 128):
            raise ValueError(f"Invalid Emerald animation sheet: {path} ({source.mode}, {source.size})")
        frame_count = source.height // 64
        return [
            palette_image(source.crop((0, index * 64, 64, (index + 1) * 64)), palette)
            for index in range(frame_count)
        ]


def static_frame(path: Path, palette: Sequence[tuple[int, int, int]]) -> list[Image.Image]:
    with Image.open(path) as source:
        if source.mode != "P" or source.size != (64, 64):
            raise ValueError(f"Invalid Emerald back sprite: {path} ({source.mode}, {source.size})")
        return [palette_image(source, palette)]


def save_gif(frames: Sequence[Image.Image], output: Path) -> None:
    if not frames:
        raise ValueError("Cannot write an empty GIF")
    output.parent.mkdir(parents=True, exist_ok=True)
    durations = [560] * len(frames)
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=list(frames[1:]),
        duration=durations,
        loop=0,
        transparency=0,
        disposal=2,
        optimize=False,
    )


def export_species(project: Path, staging: Path, dex_id: int, symbol: str) -> dict[str, object]:
    root = destination(project, symbol)
    palette_root = root if (root / "normal.pal").is_file() else root.parent
    palettes = {
        "n": read_jasc(palette_root / "normal.pal"),
        "s": read_jasc(palette_root / "shiny.pal"),
    }
    sprite_dir = staging / "sprites" / "battlesprites"
    outputs = {
        "front-n": animation_frames(root / "anim_front.png", palettes["n"]),
        "front-s": animation_frames(root / "anim_front.png", palettes["s"]),
        "back-n": static_frame(root / "back.png", palettes["n"]),
        "back-s": static_frame(root / "back.png", palettes["s"]),
    }
    hashes: dict[str, str] = {}
    for variant, frames in outputs.items():
        path = sprite_dir / f"{dex_id:03d}-{variant}.gif"
        save_gif(frames, path)
        hashes[variant] = sha256(path)
    return {
        "dex_id": dex_id,
        "symbol": symbol,
        "source": root.relative_to(project).as_posix(),
        "palette_source": palette_root.relative_to(project).as_posix(),
        "frames": {variant: len(frames) for variant, frames in outputs.items()},
        "sha256": hashes,
    }


def write_scale_tables(staging: Path, dex_ids: Iterable[int]) -> None:
    root = staging / "sprites" / "battlesprites"
    header = (
        "; PokeMMO battle sprite scale overrides\n"
        "; Generated for 64x64 HGSS/GBA-compatible sprites\n"
    )
    entries = "".join(f"{dex_id}={SPRITE_SCALE:.2f}\n" for dex_id in dex_ids)
    for name in ("summary", "front", "back"):
        (root / f"table-{name}-scale.txt").write_text(header + entries, encoding="utf-8")


def write_icon(project: Path, staging: Path) -> None:
    treecko = project / "graphics" / "pokemon" / "treecko"
    palette = read_jasc(treecko / "normal.pal")
    with Image.open(treecko / "front.png") as source:
        sprite = palette_image(source, palette).convert("RGBA")
    bbox = sprite.getbbox()
    if bbox is None:
        raise ValueError("Treecko icon source is empty")
    sprite = sprite.crop(bbox)
    sprite.thumbnail((40, 40), Image.Resampling.NEAREST)

    icon = Image.new("RGBA", (48, 48), (11, 48, 39, 255))
    draw = ImageDraw.Draw(icon)
    draw.rectangle((1, 1, 46, 46), outline=(232, 184, 48, 255), width=2)
    draw.line((4, 43, 18, 43), fill=(201, 55, 49, 255), width=2)
    draw.line((30, 4, 43, 4), fill=(201, 55, 49, 255), width=2)
    icon.alpha_composite(sprite, ((48 - sprite.width) // 2, 45 - sprite.height))
    icon.save(staging / "icon.png", optimize=False)


def write_metadata(
    staging: Path,
    version: str,
    author: str,
    records: Sequence[dict[str, object]],
    source_revision: str,
) -> None:
    resource = ElementTree.Element(
        "resource",
        {
            "name": MOD_NAME,
            "version": version,
            "description": "386 battle sprites HGSS from Emerald PT-BR/HGSS v1.4",
            "author": author,
            "weblink": "https://github.com/menezesx2k26-byte/emerald-ptbr-hgss",
        },
    )
    ElementTree.ElementTree(resource).write(
        staging / "info.xml",
        encoding="UTF-8",
        xml_declaration=True,
    )
    (staging / "README.txt").write_text(
        "Emerald HGSS Visual 386 for PokeMMO\n\n"
        "Installation:\n"
        "1. Open PokeMMO > Mod Management.\n"
        "2. Choose Import Mod and select this .mod file.\n"
        "3. Enable the mod and restart the client.\n\n"
        "Scope: National Dex 001-386 battle sprites, normal/shiny, front/back.\n"
        "This package does not modify maps, water, dialogue, gameplay or ROM files.\n",
        encoding="utf-8",
    )
    (staging / "NOTICE.txt").write_text(
        "Fan-made visual resource pack. Not affiliated with Nintendo, Game Freak, "
        "The Pokemon Company or PokeMMO. Pokemon and related assets belong to their "
        "respective owners. Sprite source: PokeAPI/sprites, generation IV, "
        "HeartGold/SoulSilver, pinned by revision. Conversion pipeline: "
        "menezesx2k26-byte/emerald-ptbr-hgss.\n",
        encoding="utf-8",
    )
    manifest = {
        "name": MOD_NAME,
        "version": version,
        "author": author,
        "source": "Emerald PT-BR/HGSS v1.4 indexed battle assets",
        "source_revision": source_revision,
        "species": len(records),
        "sprite_files": len(records) * len(VARIANTS),
        "variants": list(VARIANTS),
        "records": records,
    }
    (staging / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate_staging(staging: Path, dex_ids: Sequence[int]) -> dict[str, object]:
    sprite_dir = staging / "sprites" / "battlesprites"
    missing = [
        f"{dex_id:03d}-{variant}.gif"
        for dex_id in dex_ids
        for variant in VARIANTS
        if not (sprite_dir / f"{dex_id:03d}-{variant}.gif").is_file()
    ]
    gif_files = sorted(sprite_dir.glob("*.gif"))
    invalid: list[str] = []
    repeated_front_frames: list[str] = []
    frame_counts: dict[str, int] = {}
    for path in gif_files:
        try:
            with Image.open(path) as image:
                frames = int(getattr(image, "n_frames", 1))
                if image.size != (64, 64) or image.format != "GIF":
                    invalid.append(path.name)
                frame_counts[path.name] = frames
                if "-front-" in path.name and frames > 1:
                    rendered = [frame.convert("RGBA").tobytes() for frame in ImageSequence.Iterator(image)]
                    if len(set(rendered)) == 1:
                        repeated_front_frames.append(path.name)
        except OSError:
            invalid.append(path.name)
    identical_normal_shiny: list[str] = []
    for dex_id in dex_ids:
        for direction in ("front", "back"):
            normal = sprite_dir / f"{dex_id:03d}-{direction}-n.gif"
            shiny = sprite_dir / f"{dex_id:03d}-{direction}-s.gif"
            if normal.is_file() and shiny.is_file() and normal.read_bytes() == shiny.read_bytes():
                identical_normal_shiny.append(f"{dex_id:03d}-{direction}")
    with Image.open(staging / "icon.png") as icon:
        icon_valid = icon.format == "PNG" and icon.size == (48, 48)
    info = ElementTree.parse(staging / "info.xml").getroot()
    metadata_valid = info.tag == "resource" and all(
        info.attrib.get(key) for key in ("name", "version", "description", "author")
    )
    expected = len(dex_ids) * len(VARIANTS)
    valid = (
        not missing
        and not invalid
        and not repeated_front_frames
        and not identical_normal_shiny
        and len(gif_files) == expected
        and icon_valid
        and metadata_valid
    )
    return {
        "valid": valid,
        "species": len(dex_ids),
        "expected_sprite_files": expected,
        "actual_sprite_files": len(gif_files),
        "missing": missing,
        "invalid": invalid,
        "repeated_front_frames": repeated_front_frames,
        "identical_normal_shiny": identical_normal_shiny,
        "icon_48x48_png": icon_valid,
        "metadata_valid": metadata_valid,
        "animated_front_files": sum(
            1 for name, frames in frame_counts.items() if "-front-" in name and frames > 1
        ),
    }


def build_mod(
    project: Path,
    output: Path,
    *,
    version: str = MOD_VERSION,
    author: str = MOD_AUTHOR,
    source_revision: str = "unknown",
    species: Sequence[tuple[int, str]] | None = None,
) -> dict[str, object]:
    production_build = species is None
    species = species or list(enumerate(national_dex_symbols(project), 1))
    dex_ids = [dex_id for dex_id, _ in species]
    if production_build and len(species) != EXPECTED_SPECIES:
        raise RuntimeError(f"Expected {EXPECTED_SPECIES} species")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pokemmo-hgss-") as directory:
        staging = Path(directory)
        records = [export_species(project, staging, dex_id, symbol) for dex_id, symbol in species]
        write_scale_tables(staging, dex_ids)
        write_icon(project, staging)
        write_metadata(staging, version, author, records, source_revision)
        validation = validate_staging(staging, dex_ids)
        if not validation["valid"]:
            raise RuntimeError(f"PokeMMO staging validation failed: {validation}")
        with zipfile.ZipFile(output, "w") as archive:
            for path in sorted(item for item in staging.rglob("*") if item.is_file()):
                deterministic_zip_write(archive, path, path.relative_to(staging).as_posix())

    with zipfile.ZipFile(output) as archive:
        corrupt = archive.testzip()
        names = archive.namelist()
    validation.update(
        {
            "archive": output.name,
            "archive_sha256": sha256(output),
            "archive_size_bytes": output.stat().st_size,
            "archive_entries": len(names),
            "zip_integrity": corrupt is None,
        }
    )
    validation["valid"] = bool(validation["valid"] and corrupt is None)
    return validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Emerald HGSS PokeMMO visual mod")
    parser.add_argument("--project", type=Path, required=True, help="pokeemerald source tree")
    parser.add_argument("--output", type=Path, required=True, help="destination .mod file")
    parser.add_argument("--report", type=Path, required=True, help="validation JSON")
    parser.add_argument("--sprites-root", type=Path, help="optional pinned HGSS PokeAPI directory")
    parser.add_argument("--version", default=MOD_VERSION)
    parser.add_argument("--author", default=MOD_AUTHOR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project = args.project.resolve()
    if args.sprites_root:
        import_hgss_sprites(project, args.sprites_root.resolve())
    report = build_mod(
        project,
        args.output.resolve(),
        version=args.version,
        author=args.author,
        source_revision=os.environ.get("POKEAPI_SPRITES_SHA", "unknown"),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not report["valid"]:
        raise SystemExit("PokeMMO mod validation failed")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
