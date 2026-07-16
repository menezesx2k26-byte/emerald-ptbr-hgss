from __future__ import annotations

import colorsys
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from common import gba_channel, read_jasc, write_jasc
from release import release_tag, release_version


TOWN_GROUND_TILES = {
    2: (
        "dddddddd",
        "dddcdddd",
        "ddcedddd",
        "dddceddd",
        "dddddddd",
        "deddddcd",
        "dceddddd",
        "dddddddd",
    ),
    3: (
        "ddddeddd",
        "dcdddddd",
        "dceddddd",
        "ddddddcd",
        "dddddcde",
        "dddddddd",
        "ddeddddd",
        "dddddddd",
    ),
}

FOREST_GROUND_TILES = {
    2: (
        "dddddddd",
        "ddd5dddd",
        "ddcedddd",
        "dddceddd",
        "dddddddd",
        "deddddd5",
        "dceddddd",
        "dddddddd",
    ),
    3: (
        "ddddeddd",
        "d5dddddd",
        "ddeddddd",
        "ddddddcd",
        "dddddcde",
        "dddddddd",
        "dd5ddddd",
        "dddddddd",
    ),
}

PATH_TILE_IDS = set(range(249, 303))
TREE_TILE_IDS = {
    9, 10, 25, 41,
    384, 385, 400, 401,
    416, 417, 418, 419, 420, 421,
}
TOWN_ROOF_TILE_IDS = {
    2, 3, 4, 9,
    18, 19, 20, 25,
    34, 35, 36, 40, 41, 42,
    50, 51, 52, 57,
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tile_box(tile_id: int) -> tuple[int, int, int, int]:
    x = (tile_id % 16) * 8
    y = (tile_id // 16) * 8
    return x, y, x + 8, y + 8


def read_tile(image: Image.Image, tile_id: int) -> list[list[int]]:
    data = image.crop(tile_box(tile_id)).tobytes()
    return [list(data[index:index + 8]) for index in range(0, 64, 8)]


def write_tile(image: Image.Image, tile_id: int, pixels: list[list[int]]) -> None:
    tile = Image.new("P", (8, 8))
    tile.putpalette(image.getpalette())
    tile.putdata([value for row in pixels for value in row])
    image.paste(tile, tile_box(tile_id)[:2])


def write_pattern(image: Image.Image, tile_id: int, rows: tuple[str, ...]) -> None:
    if len(rows) != 8 or any(len(row) != 8 for row in rows):
        raise ValueError(f"tile {tile_id}: expected an 8x8 hexadecimal pattern")
    write_tile(image, tile_id, [[int(value, 16) for value in row] for row in rows])


def install_tall_grass(image: Image.Image) -> None:
    mapping = {0xF: 0x4, 0x4: 0xF, 0xC: 0xF}
    for tile_id in (16, 17, 32, 33):
        pixels = read_tile(image, tile_id)
        for y, row in enumerate(pixels):
            for x, value in enumerate(row):
                if value in mapping and (tile_id * 5 + x * 7 + y * 11) % 23 == 0:
                    row[x] = mapping[value]
        write_tile(image, tile_id, pixels)


def recolor_paths(image: Image.Image) -> None:
    mapping = {0xC: 0x9, 0xD: 0xA, 0xE: 0x5, 0xF: 0x7, 0x1: 0x6, 0x2: 0x8}
    for tile_id in PATH_TILE_IDS:
        if tile_id * 64 >= image.width * image.height:
            continue
        pixels = read_tile(image, tile_id)
        if sum(value == 0xC for row in pixels for value in row) < 20:
            continue
        write_tile(image, tile_id, [[mapping.get(value, value) for value in row] for row in pixels])


def sculpt_tree_crowns(image: Image.Image, mode: str) -> None:
    for tile_id in TREE_TILE_IDS:
        pixels = read_tile(image, tile_id)
        for y, row in enumerate(pixels):
            for x, value in enumerate(row):
                if value not in (1, 2, 3, 4):
                    continue
                key = (tile_id * 3 + x * 5 + y * 7) % 17
                if y <= 3 and value in (2, 3) and key in (0, 1):
                    row[x] = 1
                elif y >= 4 and value == 1 and key == 2:
                    row[x] = 2
                elif mode == "forest" and y >= 4 and value in (1, 2) and key == 3:
                    row[x] = min(4, value + 2)
        write_tile(image, tile_id, pixels)


def texture_town_roofs(image: Image.Image) -> None:
    cycle = {0xE: 0xC, 0xC: 0xB, 0xB: 0xE, 0xD: 0xC}
    for tile_id in TOWN_ROOF_TILE_IDS:
        pixels = read_tile(image, tile_id)
        original = [row[:] for row in pixels]
        for y in range(1, 7):
            for x in range(1, 7):
                value = original[y][x]
                if value not in cycle or (x + y * 2 + tile_id) % 7:
                    continue
                if all(original[ny][nx] != 0 for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                    pixels[y][x] = cycle[value]
        write_tile(image, tile_id, pixels)


def texture_forest_details(image: Image.Image) -> None:
    for tile_id in (174, 175):
        if tile_id * 64 >= image.width * image.height:
            continue
        pixels = read_tile(image, tile_id)
        for y in range(8):
            x = (tile_id + y * 3) % 8
            if pixels[y][x] in (2, 3, 4, 0xF):
                pixels[y][x] = 4 if y >= 4 else 2
        write_tile(image, tile_id, pixels)


def restyle_tileset_art(root: Path, mode: str, role: str) -> dict[str, object]:
    path = root / "tiles.png"
    with Image.open(path) as source:
        image = source.copy()
    if image.mode != "P" or image.width != 128 or image.height % 8:
        raise ValueError(f"invalid indexed tiles image: {path}")
    before = image.tobytes()
    if role == "primary":
        patterns = TOWN_GROUND_TILES if mode == "town" else FOREST_GROUND_TILES
        for tile_id, rows in patterns.items():
            write_pattern(image, tile_id, rows)
        install_tall_grass(image)
        recolor_paths(image)
        sculpt_tree_crowns(image, mode)
    elif mode == "town":
        texture_town_roofs(image)
    else:
        texture_forest_details(image)
    after = image.tobytes()
    if before == after:
        raise ValueError(f"pixel-art pass changed no tiles: {path}")
    changed_pixels = sum(left != right for left, right in zip(before, after))
    changed_tiles = sum(
        before[index:index + 64] != after[index:index + 64]
        for index in range(0, len(before), 64)
    )
    image.save(path, optimize=False)
    return {
        "tiles_changed": changed_tiles,
        "pixels_changed": changed_pixels,
        "output_sha256": file_sha256(path),
        "dimensions": [image.width, image.height],
    }


def transform_color(rgb: tuple[int, int, int], mode: str) -> tuple[int, int, int]:
    if max(rgb) < 20: return rgb
    r,g,b=(c/255 for c in rgb); h,s,v=colorsys.rgb_to_hsv(r,g,b)
    if s < 0.12:
        h,s,v=(0.58,min(0.09,s+0.03),min(1,v*1.03)) if mode=="town" else (0.55,min(0.11,s+0.04),v*0.90)
    elif 0.18 <= h <= 0.47:
        if mode=="town": h,s,v=0.34+(h-0.34)*0.35,min(1,s*1.18+0.05),min(1,v*1.06+0.01)
        else: h,s,v=0.38+(h-0.38)*0.45,min(1,s*1.25+0.06),v*0.82
    elif h < 0.18 or h > 0.95:
        h=0.085 if mode=="town" and h<0.18 else 0.075 if h<0.18 else 0.98
        s=min(1,s*(0.96 if mode=="town" else 1.06)+0.03); v*=1.04 if mode=="town" else 0.82
    elif 0.47 < h < 0.72:
        h,s,v=(0.54,min(1,s*1.15+0.03),v*1.05) if mode=="town" else (0.52,min(1,s*1.12+0.03),v*0.86)
    else:
        s=min(1,s*(1.05 if mode=="town" else 1.08)); v*=1.03 if mode=="town" else 0.86
    nr,ng,nb=colorsys.hsv_to_rgb(h,s,max(0,min(1,v)))
    return tuple(gba_channel(c*255) for c in (nr,ng,nb))  # type: ignore[return-value]


def clone_tileset(
    project: Path,
    source: str,
    destination: str,
    mode: str,
    *,
    role: str,
    special: bool = False,
) -> dict[str, object]:
    src = project / source
    dst = project / destination
    source_tiles_sha256 = file_sha256(src / "tiles.png")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for palette in sorted((dst/"palettes").glob("*.pal")):
        write_jasc(palette,[transform_color(c,mode) for c in read_jasc(palette)])
    if special:
        p5=read_jasc(dst/"palettes/05.pal"); p8=read_jasc(dst/"palettes/08.pal")
        for i,c in zip((11,12,13,14),[(224,240,248),(168,200,216),(112,152,176),(64,104,136)]): p5[i]=c
        for i,c in zip((1,2,3,4),[(216,248,240),(144,216,208),(88,176,184),(48,128,152)]): p8[i]=c
        for i,c in zip((11,12,13),[(232,240,248),(184,200,216),(120,144,168)]): p8[i]=c
        write_jasc(dst/"palettes/05.pal",p5); write_jasc(dst/"palettes/08.pal",p8)
    art = restyle_tileset_art(dst, mode, role)
    return {
        "source": source,
        "destination": destination,
        "mode": mode,
        "role": role,
        "source_tiles_sha256": source_tiles_sha256,
        "metatiles_sha256": file_sha256(dst / "metatiles.bin"),
        "metatile_attributes_sha256": file_sha256(dst / "metatile_attributes.bin"),
        **art,
    }


def append_once(path: Path, marker: str, text: str) -> None:
    existing=path.read_text(encoding="utf-8")
    if marker not in existing: path.write_text(existing.rstrip()+"\n\n"+text.strip()+"\n",encoding="utf-8")


def palette_includes(directory: str) -> str:
    return "\n".join(f'    INCBIN_U16("{directory}/palettes/{i:02}.gbapal"),' for i in range(16))


def apply_map_overhaul(project: Path) -> None:
    art_records = [
        clone_tileset(
            project,
            "data/tilesets/primary/general",
            "data/tilesets/primary/hgss_town",
            "town",
            role="primary",
        ),
        clone_tileset(
            project,
            "data/tilesets/primary/general",
            "data/tilesets/primary/hgss_forest",
            "forest",
            role="primary",
        ),
        clone_tileset(
            project,
            "data/tilesets/secondary/petalburg",
            "data/tilesets/secondary/hgss_small_town",
            "town",
            role="secondary",
            special=True,
        ),
        clone_tileset(
            project,
            "data/tilesets/secondary/rustboro",
            "data/tilesets/secondary/hgss_forest",
            "forest",
            role="secondary",
        ),
    ]
    blocks=[]
    for symbol,directory in [("HGSSGeneralTown","data/tilesets/primary/hgss_town"),("HGSSGeneralForest","data/tilesets/primary/hgss_forest"),("HGSSSmallTown","data/tilesets/secondary/hgss_small_town"),("HGSSForest","data/tilesets/secondary/hgss_forest")]:
        blocks.append(f'''const u32 gTilesetTiles_{symbol}[] = INCBIN_U32("{directory}/tiles.4bpp.lz");\n\nconst u16 gTilesetPalettes_{symbol}[][16] =\n{{\n{palette_includes(directory)}\n}};''')
    append_once(project/"src/data/tilesets/graphics.h","gTilesetTiles_HGSSGeneralTown","\n\n".join(blocks))
    append_once(project/"src/data/tilesets/metatiles.h","gMetatiles_HGSSGeneralTown",'''const u16 gMetatiles_HGSSGeneralTown[] = INCBIN_U16("data/tilesets/primary/hgss_town/metatiles.bin");
const u16 gMetatileAttributes_HGSSGeneralTown[] = INCBIN_U16("data/tilesets/primary/hgss_town/metatile_attributes.bin");
const u16 gMetatiles_HGSSGeneralForest[] = INCBIN_U16("data/tilesets/primary/hgss_forest/metatiles.bin");
const u16 gMetatileAttributes_HGSSGeneralForest[] = INCBIN_U16("data/tilesets/primary/hgss_forest/metatile_attributes.bin");
const u16 gMetatiles_HGSSSmallTown[] = INCBIN_U16("data/tilesets/secondary/hgss_small_town/metatiles.bin");
const u16 gMetatileAttributes_HGSSSmallTown[] = INCBIN_U16("data/tilesets/secondary/hgss_small_town/metatile_attributes.bin");
const u16 gMetatiles_HGSSForest[] = INCBIN_U16("data/tilesets/secondary/hgss_forest/metatiles.bin");
const u16 gMetatileAttributes_HGSSForest[] = INCBIN_U16("data/tilesets/secondary/hgss_forest/metatile_attributes.bin");''')
    append_once(project/"src/data/tilesets/headers.h","gTileset_HGSSGeneralTown",'''const struct Tileset gTileset_HGSSGeneralTown = {.isCompressed=TRUE,.isSecondary=FALSE,.tiles=gTilesetTiles_HGSSGeneralTown,.palettes=gTilesetPalettes_HGSSGeneralTown,.metatiles=gMetatiles_HGSSGeneralTown,.metatileAttributes=gMetatileAttributes_HGSSGeneralTown,.callback=InitTilesetAnim_General};
const struct Tileset gTileset_HGSSGeneralForest = {.isCompressed=TRUE,.isSecondary=FALSE,.tiles=gTilesetTiles_HGSSGeneralForest,.palettes=gTilesetPalettes_HGSSGeneralForest,.metatiles=gMetatiles_HGSSGeneralForest,.metatileAttributes=gMetatileAttributes_HGSSGeneralForest,.callback=InitTilesetAnim_General};
const struct Tileset gTileset_HGSSSmallTown = {.isCompressed=TRUE,.isSecondary=TRUE,.tiles=gTilesetTiles_HGSSSmallTown,.palettes=gTilesetPalettes_HGSSSmallTown,.metatiles=gMetatiles_HGSSSmallTown,.metatileAttributes=gMetatileAttributes_HGSSSmallTown,.callback=InitTilesetAnim_Petalburg};
const struct Tileset gTileset_HGSSForest = {.isCompressed=TRUE,.isSecondary=TRUE,.tiles=gTilesetTiles_HGSSForest,.palettes=gTilesetPalettes_HGSSForest,.metatiles=gMetatiles_HGSSForest,.metatileAttributes=gMetatileAttributes_HGSSForest,.callback=InitTilesetAnim_Rustboro};''')
    append_once(project/"graphics_file_rules.mk","primary/hgss_town/tiles.4bpp",'''$(TILESETGFXDIR)/primary/hgss_town/tiles.4bpp: %.4bpp: %.png
\t$(GFX) $< $@ -num_tiles 512 -Wnum_tiles
$(TILESETGFXDIR)/primary/hgss_forest/tiles.4bpp: %.4bpp: %.png
\t$(GFX) $< $@ -num_tiles 512 -Wnum_tiles
$(TILESETGFXDIR)/secondary/hgss_small_town/tiles.4bpp: %.4bpp: %.png
\t$(GFX) $< $@ -num_tiles 159 -Wnum_tiles
$(TILESETGFXDIR)/secondary/hgss_forest/tiles.4bpp: %.4bpp: %.png
\t$(GFX) $< $@ -num_tiles 498 -Wnum_tiles''')
    path=project/"data/layouts/layouts.json"; data=json.loads(path.read_text(encoding="utf-8"))
    town={"LittlerootTown_Layout","OldaleTown_Layout","Route101_Layout"}; forest={"PetalburgWoods_Layout"}
    for layout in data["layouts"]:
        if layout["name"] in town: layout["primary_tileset"]="gTileset_HGSSGeneralTown"; layout["secondary_tileset"]="gTileset_HGSSSmallTown"
        elif layout["name"] in forest: layout["primary_tileset"]="gTileset_HGSSGeneralForest"; layout["secondary_tileset"]="gTileset_HGSSForest"
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    report = {
        "version": release_version(),
        "art_policy": (
            "Original deterministic GBA pixel-art pass over the pinned Emerald geometry; "
            "no HGSS map tiles are ripped or relabeled."
        ),
        "compatibility_policy": (
            "Metatiles, attributes, blockdata, borders, collisions, warps and events remain unchanged."
        ),
        "tilesets": art_records,
    }
    (project / f"map_art_{release_tag()}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
