from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

from common import apply_palette, read_jasc, write_jasc


def water_frame(palette: Sequence[tuple[int, int, int]], frame: int) -> Image.Image:
    output = Image.new("P", (16, 120), 8)
    apply_palette(output, palette)
    px = output.load()
    shades = [10, 9, 8, 14, 13, 12, 11, 6, 2]
    for y in range(output.height):
        for x in range(output.width):
            wave = math.sin((x + frame * 2) * math.pi / 8) + math.sin((y + frame * 3) * math.pi / 12)
            diagonal = ((x + y + frame * 2) % 16) / 15
            value = max(0, min(8, int(round(4 + wave * 1.4 + (diagonal - 0.5) * 1.5))))
            px[x, y] = 2 if (x + frame * 2 + y // 3) % 23 == 0 else shades[value]
    return output


def waterfall_frame(palette: Sequence[tuple[int, int, int]], frame: int) -> Image.Image:
    output = Image.new("P", (8, 48), 8)
    apply_palette(output, palette)
    px = output.load()
    sequence = [2, 2, 11, 11, 12, 12, 13, 13, 14, 14, 8, 8]
    for y in range(48):
        for x in range(8):
            index = sequence[(y + frame * 2 + x // 3) % 12]
            if y % 8 in (0, 1) and (x + y + frame) % 3 == 0:
                index = 2
            px[x, y] = index
    return output


def copy_strip(tiles_image: Image.Image, strip: Image.Image, first_tile: int, tile_count: int) -> None:
    tiles = [strip.crop((x, y, x + 8, y + 8)) for y in range(0, strip.height, 8) for x in range(0, strip.width, 8)]
    for offset in range(tile_count):
        tile_index = first_tile + offset
        tiles_image.paste(tiles[offset], ((tile_index % 16) * 8, (tile_index // 16) * 8))


def apply_water_overhaul(project: Path) -> None:
    general = project / "data/tilesets/primary/general"
    water_path = general / "palettes/04.pal"
    land_path = general / "palettes/03.pal"
    sand_path = general / "palettes/05.pal"
    water = read_jasc(water_path)
    land = read_jasc(land_path)
    sand = read_jasc(sand_path)
    for index, color in {0:(0,64,112),2:(216,248,248),6:(96,192,208),7:(64,176,200),8:(0,112,160),9:(0,96,144),10:(0,80,128),11:(152,232,240),12:(96,208,224),13:(48,184,208),14:(8,144,184)}.items():
        water[index] = color
    for index, color in {10:(224,208,184),11:(184,168,152),12:(144,128,120),13:(104,96,96),14:(72,72,80)}.items():
        land[index] = color
    for index, color in {0:(0,88,136),11:(248,240,192),12:(240,216,152),13:(224,184,112),14:(192,144,80)}.items():
        sand[index] = color
    write_jasc(water_path, water); write_jasc(land_path, land); write_jasc(sand_path, sand)

    water_frames = []
    for frame in range(8):
        image = water_frame(water, frame)
        image.save(general / f"anim/water/{frame}.png", optimize=False)
        water_frames.append(image)
    waterfalls = []
    for frame in range(4):
        image = waterfall_frame(water, frame)
        image.save(general / f"anim/waterfall/{frame}.png", optimize=False)
        waterfalls.append(image)
    for folder, count, palette in [("land_water_edge", 4, land), ("sand_water_edge", 7, sand)]:
        for frame in range(count):
            path = general / f"anim/{folder}/{frame}.png"
            image = Image.open(path).copy(); apply_palette(image, palette); image.save(path, optimize=False)
    tiles = Image.open(general / "tiles.png").copy()
    copy_strip(tiles, water_frames[0], 432, 30)
    copy_strip(tiles, Image.open(general / "anim/sand_water_edge/0.png"), 464, 10)
    copy_strip(tiles, Image.open(general / "anim/land_water_edge/0.png"), 480, 10)
    copy_strip(tiles, waterfalls[0], 496, 6)
    tiles.save(general / "tiles.png", optimize=False)

    field0_path = project / "graphics/field_effects/palettes/general_0.pal"
    field1_path = project / "graphics/field_effects/palettes/general_1.pal"
    field0 = read_jasc(field0_path); field1 = read_jasc(field1_path)
    for index, color in {0:(24,160,200),4:(248,248,248),5:(216,248,248),6:(152,232,240),7:(96,208,224),8:(48,176,200)}.items(): field0[index] = color
    for index, color in {0:(24,160,200),6:(8,144,184),7:(48,176,200),8:(96,208,224),9:(216,248,248)}.items(): field1[index] = color
    write_jasc(field0_path, field0); write_jasc(field1_path, field1)

    player = read_jasc(project / "graphics/object_events/palettes/brendan.pal")
    surf = Image.new("P", (96, 32), 0); apply_palette(surf, player); d = ImageDraw.Draw(surf)
    for frame, direction in enumerate(("south", "north", "west")):
        ox = frame * 32
        if direction == "south":
            d.ellipse([ox+5,13,ox+26,27],fill=15); d.ellipse([ox+7,14,ox+24,25],fill=6); d.ellipse([ox+9,15,ox+22,20],fill=5); d.rectangle([ox+6,24,ox+25,25],fill=14)
        elif direction == "north":
            d.ellipse([ox+5,6,ox+26,21],fill=15); d.ellipse([ox+7,8,ox+24,20],fill=6); d.ellipse([ox+9,10,ox+22,15],fill=5); d.rectangle([ox+5,8,ox+26,9],fill=14)
        else:
            d.ellipse([ox+4,12,ox+27,25],fill=15); d.ellipse([ox+6,13,ox+25,23],fill=6); d.ellipse([ox+10,14,ox+22,18],fill=5); d.rectangle([ox+8,23,ox+25,24],fill=14)
    surf.save(project / "graphics/field_effects/pics/surf_blob.png", optimize=False)

    ripple = Image.new("P", (80,16), 0); apply_palette(ripple, field1)
    for frame in range(5):
        d = ImageDraw.Draw(ripple); ox = frame*16
        if frame == 0: d.point((ox+8,8), fill=9)
        else:
            rx, ry = 2+frame, max(1,frame//2+1); d.ellipse([ox+8-rx,8-ry,ox+8+rx,8+ry], outline=[9,8,7,6][frame-1])
    ripple.save(project / "graphics/field_effects/pics/ripple.png", optimize=False)

    splash = Image.new("P", (32,8), 0); apply_palette(splash, field0)
    patterns=[[(4,6,4)],[(3,6,5),(5,6,5),(4,4,4)],[(2,6,6),(6,6,6),(3,4,5),(5,3,4)],[(1,7,7),(7,7,7),(2,5,6),(6,4,5),(4,2,4)]]
    for frame, points in enumerate(patterns):
        for x,y,index in points: splash.putpixel((frame*8+x,y), index)
    splash.save(project / "graphics/field_effects/pics/splash.png", optimize=False)

    surfacing = Image.new("P", (80,16), 0); apply_palette(surfacing, field0)
    for frame in range(5):
        d=ImageDraw.Draw(surfacing); ox=frame*16
        if frame==0: d.point((ox+8,9),fill=8)
        elif frame==1: d.arc([ox+5,6,ox+11,12],180,360,fill=6); d.point((ox+8,4),fill=4)
        elif frame==2: d.ellipse([ox+3,6,ox+13,12],outline=5); d.point((ox+5,4),fill=4); d.point((ox+11,3),fill=4)
        elif frame==3: d.ellipse([ox+1,5,ox+15,13],outline=6); d.point((ox+4,3),fill=5); d.point((ox+12,4),fill=5)
        else: d.ellipse([ox,5,ox+15,13],outline=7)
    surfacing.save(project / "graphics/field_effects/pics/water_surfacing.png", optimize=False)
    for name in ["jump_small_splash.png","jump_big_splash.png","bubbles.png","hot_springs_water.png"]:
        path=project/"graphics/field_effects/pics"/name; image=Image.open(path).copy(); apply_palette(image,field0); image.save(path,optimize=False)
