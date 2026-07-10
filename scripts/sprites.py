from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image

from common import apply_palette, gba_channel, gba_color, write_jasc

CANVAS_SIZE = 64
MAX_OPAQUE_COLORS = 15


def prepare_rgba(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size == (80, 80):
        return image.crop((8, 8, 72, 72))
    bbox = image.getbbox()
    if bbox is None:
        return Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    cropped = image.crop(bbox)
    if cropped.width > CANVAS_SIZE or cropped.height > CANVAS_SIZE:
        scale = min(CANVAS_SIZE / cropped.width, CANVAS_SIZE / cropped.height)
        cropped = cropped.resize(
            (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
            Image.Resampling.NEAREST,
        )
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(cropped, ((CANVAS_SIZE - cropped.width) // 2, CANVAS_SIZE - cropped.height))
    return canvas


def opaque_pixels(images: Iterable[Image.Image]) -> list[tuple[int, int, int]]:
    result: list[tuple[int, int, int]] = []
    for image in images:
        for r, g, b, a in image.getdata():
            if a >= 128:
                result.append((r, g, b))
    return result


def build_normal_palette(images: Sequence[Image.Image]) -> list[tuple[int, int, int]]:
    pixels = opaque_pixels(images)
    if not pixels:
        return [(0, 0, 0)] * 16
    sample = Image.new("RGB", (len(pixels), 1))
    sample.putdata(pixels)
    quantized = sample.quantize(
        colors=MAX_OPAQUE_COLORS,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    raw = quantized.getpalette() or []
    unique: list[tuple[int, int, int]] = []
    for index in sorted(set(quantized.getdata())):
        color = gba_color(raw[index * 3 : index * 3 + 3])
        if color not in unique:
            unique.append(color)
    unique = unique[:MAX_OPAQUE_COLORS]
    while len(unique) < MAX_OPAQUE_COLORS:
        unique.append(unique[-1] if unique else (0, 0, 0))
    return [(0, 0, 0), *unique]


def color_distance(a: Sequence[int], b: Sequence[int]) -> float:
    return 2.0 * (a[0] - b[0]) ** 2 + 4.0 * (a[1] - b[1]) ** 2 + 3.0 * (a[2] - b[2]) ** 2


def index_image(image: Image.Image, palette: Sequence[tuple[int, int, int]]) -> Image.Image:
    output = Image.new("P", image.size, 0)
    apply_palette(output, palette)
    opaque_palette = palette[1:16]
    indices: list[int] = []
    for r, g, b, a in image.getdata():
        if a < 128:
            indices.append(0)
        else:
            nearest = min(range(len(opaque_palette)), key=lambda i: color_distance((r, g, b), opaque_palette[i]))
            indices.append(nearest + 1)
    output.putdata(indices)
    output.info["transparency"] = 0
    return output


def build_shiny_palette(
    normal_images: Sequence[Image.Image],
    shiny_images: Sequence[Image.Image],
    indexed_images: Sequence[Image.Image],
    normal_palette: Sequence[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    buckets: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    for normal, shiny, indexed in zip(normal_images, shiny_images, indexed_images):
        for normal_px, shiny_px, palette_index in zip(normal.getdata(), shiny.getdata(), indexed.getdata()):
            palette_index = int(palette_index)
            if palette_index == 0 or normal_px[3] < 128 or shiny_px[3] < 128:
                continue
            buckets[palette_index].append((shiny_px[0], shiny_px[1], shiny_px[2]))
    result = [(0, 0, 0)]
    for index in range(1, 16):
        samples = buckets.get(index, [])
        if not samples:
            result.append(normal_palette[index])
            continue
        counts = Counter(gba_color(sample) for sample in samples).most_common(6)
        total = sum(count for _, count in counts)
        result.append(
            tuple(
                gba_channel(sum(color[channel] * count for color, count in counts) / total)
                for channel in range(3)
            )
        )
    return result


def national_dex_symbols(project: Path) -> list[str]:
    text = (project / "include/constants/pokedex.h").read_text(encoding="utf-8")
    symbols = re.findall(r"^\s*NATIONAL_DEX_([A-Z0-9_]+)\s*,?", text, flags=re.M)
    symbols = [symbol for symbol in symbols if symbol != "NONE"]
    symbols = symbols[: symbols.index("DEOXYS") + 1]
    if len(symbols) != 386:
        raise RuntimeError(f"Expected 386 National Dex symbols, got {len(symbols)}")
    return symbols


def destination(project: Path, symbol: str) -> Path:
    if symbol == "UNOWN":
        relative = "unown/a"
    elif symbol == "CASTFORM":
        relative = "castform/normal"
    else:
        relative = symbol.lower()
    return project / "graphics/pokemon" / relative


def import_hgss_sprites(project: Path, sprites_root: Path) -> None:
    symbols = national_dex_symbols(project)
    required: list[Path] = []
    for dex_id in range(1, 387):
        required.extend([
            sprites_root / f"{dex_id}.png",
            sprites_root / "back" / f"{dex_id}.png",
            sprites_root / "shiny" / f"{dex_id}.png",
            sprites_root / "back/shiny" / f"{dex_id}.png",
        ])
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing HGSS sprites: " + ", ".join(missing[:20]))

    for dex_id, symbol in enumerate(symbols, 1):
        normal_front = prepare_rgba(sprites_root / f"{dex_id}.png")
        normal_back = prepare_rgba(sprites_root / "back" / f"{dex_id}.png")
        shiny_front = prepare_rgba(sprites_root / "shiny" / f"{dex_id}.png")
        shiny_back = prepare_rgba(sprites_root / "back/shiny" / f"{dex_id}.png")
        normal_palette = build_normal_palette([normal_front, normal_back])
        indexed_front = index_image(normal_front, normal_palette)
        indexed_back = index_image(normal_back, normal_palette)
        shiny_palette = build_shiny_palette(
            [normal_front, normal_back],
            [shiny_front, shiny_back],
            [indexed_front, indexed_back],
            normal_palette,
        )
        out = destination(project, symbol)
        out.mkdir(parents=True, exist_ok=True)
        indexed_front.save(out / "front.png", optimize=False)
        indexed_back.save(out / "back.png", optimize=False)
        animation = Image.new("P", (64, 128), 0)
        animation.putpalette(indexed_front.getpalette())
        animation.paste(indexed_front, (0, 0))
        animation.paste(indexed_front, (0, 64))
        animation.info["transparency"] = 0
        animation.save(out / "anim_front.png", optimize=False)
        write_jasc(out / "normal.pal", normal_palette)
        write_jasc(out / "shiny.pal", shiny_palette)
        if dex_id % 25 == 0 or dex_id == 386:
            print(f"HGSS sprites: {dex_id}/386")
