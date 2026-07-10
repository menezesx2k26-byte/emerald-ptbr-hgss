from __future__ import annotations

import colorsys
import json
import shutil
from pathlib import Path

from common import gba_channel, read_jasc, write_jasc


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


def clone_tileset(project: Path, source: str, destination: str, mode: str, special: bool=False) -> None:
    src=project/source; dst=project/destination
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src,dst)
    for palette in sorted((dst/"palettes").glob("*.pal")):
        write_jasc(palette,[transform_color(c,mode) for c in read_jasc(palette)])
    if special:
        p5=read_jasc(dst/"palettes/05.pal"); p8=read_jasc(dst/"palettes/08.pal")
        for i,c in zip((11,12,13,14),[(224,240,248),(168,200,216),(112,152,176),(64,104,136)]): p5[i]=c
        for i,c in zip((1,2,3,4),[(216,248,240),(144,216,208),(88,176,184),(48,128,152)]): p8[i]=c
        for i,c in zip((11,12,13),[(232,240,248),(184,200,216),(120,144,168)]): p8[i]=c
        write_jasc(dst/"palettes/05.pal",p5); write_jasc(dst/"palettes/08.pal",p8)


def append_once(path: Path, marker: str, text: str) -> None:
    existing=path.read_text(encoding="utf-8")
    if marker not in existing: path.write_text(existing.rstrip()+"\n\n"+text.strip()+"\n",encoding="utf-8")


def palette_includes(directory: str) -> str:
    return "\n".join(f'    INCBIN_U16("{directory}/palettes/{i:02}.gbapal"),' for i in range(16))


def apply_map_overhaul(project: Path) -> None:
    clone_tileset(project,"data/tilesets/primary/general","data/tilesets/primary/hgss_town","town")
    clone_tileset(project,"data/tilesets/primary/general","data/tilesets/primary/hgss_forest","forest")
    clone_tileset(project,"data/tilesets/secondary/petalburg","data/tilesets/secondary/hgss_small_town","town",True)
    clone_tileset(project,"data/tilesets/secondary/rustboro","data/tilesets/secondary/hgss_forest","forest")
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
