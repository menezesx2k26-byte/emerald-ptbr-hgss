from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from common import read_jasc


PILOT_LAYOUTS = (
    "LittlerootTown_Layout",
    "OldaleTown_Layout",
    "Route101_Layout",
    "PetalburgWoods_Layout",
)


@dataclass(frozen=True)
class TilesetSource:
    root: Path
    tiles: tuple[Image.Image, ...]
    palettes: tuple[tuple[tuple[int, int, int], ...], ...]
    metatiles: tuple[tuple[int, ...], ...]


def load_u16(path: Path) -> tuple[int, ...]:
    data = path.read_bytes()
    if len(data) % 2:
        raise ValueError(f"odd-sized u16 file: {path}")
    return struct.unpack(f"<{len(data) // 2}H", data)


def load_tileset(root: Path) -> TilesetSource:
    with Image.open(root / "tiles.png") as source:
        indexed = source.copy()
    if indexed.mode != "P" or indexed.width != 128 or indexed.height % 8:
        raise ValueError(f"invalid tiles image: {root / 'tiles.png'}")
    tiles = tuple(
        indexed.crop((x, y, x + 8, y + 8))
        for y in range(0, indexed.height, 8)
        for x in range(0, indexed.width, 8)
    )
    palettes = tuple(
        tuple(read_jasc(root / "palettes" / f"{index:02}.pal"))
        for index in range(16)
    )
    words = load_u16(root / "metatiles.bin")
    if len(words) % 8:
        raise ValueError(f"invalid metatile word count: {root / 'metatiles.bin'}")
    metatiles = tuple(tuple(words[index:index + 8]) for index in range(0, len(words), 8))
    return TilesetSource(root, tiles, palettes, metatiles)


def render_tile(
    entry: int,
    primary: TilesetSource,
    secondary: TilesetSource,
    *,
    transparent_zero: bool,
) -> Image.Image:
    tile_id = entry & 0x3FF
    palette_id = (entry >> 12) & 0xF
    source = primary if tile_id < 512 else secondary
    local_id = tile_id if tile_id < 512 else tile_id - 512
    if local_id >= len(source.tiles):
        # Animated callbacks populate reserved VRAM slots that are intentionally
        # absent from tiles.png. The static preview leaves those pixels clear;
        # the mGBA runtime gate covers their actual rendering.
        return Image.new("RGBA", (8, 8))
    tile = source.tiles[local_id]
    if entry & 0x400:
        tile = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if entry & 0x800:
        tile = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    palette = source.palettes[palette_id]
    rgba = Image.new("RGBA", (8, 8))
    rgba.putdata([
        (*palette[index], 0 if transparent_zero and index == 0 else 255)
        for index in tile.tobytes()
    ])
    return rgba


def render_metatile(
    metatile_id: int,
    primary: TilesetSource,
    secondary: TilesetSource,
) -> Image.Image:
    source = primary if metatile_id < 512 else secondary
    local_id = metatile_id if metatile_id < 512 else metatile_id - 512
    if local_id >= len(source.metatiles):
        raise ValueError(
            f"metatile {metatile_id} resolves to {local_id}, outside {source.root} "
            f"({len(source.metatiles)} metatiles)"
        )
    entries = source.metatiles[local_id]
    output = Image.new("RGBA", (16, 16))
    positions = ((0, 0), (8, 0), (0, 8), (8, 8))
    for layer in range(2):
        for position, entry in zip(positions, entries[layer * 4:(layer + 1) * 4]):
            tile = render_tile(
                entry,
                primary,
                secondary,
                transparent_zero=layer == 1,
            )
            output.alpha_composite(tile, position)
    return output


def render_layout(
    project: Path,
    layout: dict[str, object],
    primary_root: Path,
    secondary_root: Path,
) -> Image.Image:
    width = int(layout["width"])
    height = int(layout["height"])
    blockdata = load_u16(project / str(layout["blockdata_filepath"]))
    if len(blockdata) != width * height:
        raise ValueError(
            f"{layout['name']}: {len(blockdata)} blocks != {width}x{height}"
        )
    primary = load_tileset(primary_root)
    secondary = load_tileset(secondary_root)
    cache: dict[int, Image.Image] = {}
    output = Image.new("RGBA", (width * 16, height * 16))
    for index, block in enumerate(blockdata):
        metatile_id = block & 0x3FF
        if metatile_id not in cache:
            cache[metatile_id] = render_metatile(metatile_id, primary, secondary)
        output.alpha_composite(cache[metatile_id], ((index % width) * 16, (index // width) * 16))
    return output.convert("RGB")


def tileset_roots(project: Path, layout_name: str) -> tuple[Path, Path]:
    if layout_name == "PetalburgWoods_Layout":
        return (
            project / "data/tilesets/primary/hgss_forest",
            project / "data/tilesets/secondary/hgss_forest",
        )
    return (
        project / "data/tilesets/primary/hgss_town",
        project / "data/tilesets/secondary/hgss_small_town",
    )


def render_pilot_maps(project: Path, output: Path) -> dict[str, object]:
    layouts = json.loads((project / "data/layouts/layouts.json").read_text(encoding="utf-8"))["layouts"]
    by_name = {layout["name"]: layout for layout in layouts}
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for name in PILOT_LAYOUTS:
        layout = by_name[name]
        primary, secondary = tileset_roots(project, name)
        image = render_layout(project, layout, primary, secondary)
        path = output / f"{name}.png"
        image.save(path, optimize=False)
        records.append({
            "layout": name,
            "width": image.width,
            "height": image.height,
            "file": path.name,
            "colors": len(image.getcolors(maxcolors=image.width * image.height) or []),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return {"maps": records}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = render_pilot_maps(args.project.resolve(), args.output.resolve())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
