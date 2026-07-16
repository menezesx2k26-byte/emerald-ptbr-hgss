from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image

from common import apply_palette, gba_channel, gba_color, write_jasc
from release import release_tag, release_version

CANVAS_SIZE = 64
MAX_OPAQUE_COLORS = 15
UNOWN_FORM_SOURCES = {
    "a": "201",
    **{letter: f"201-{letter}" for letter in "bcdefghijklmnopqrstuvwxyz"},
    "exclamation_mark": "201-exclamation",
    "question_mark": "201-question",
}
CASTFORM_FORM_SOURCES = {
    "sunny": "10013",
    "rainy": "10014",
    "snowy": "10015",
}


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


def build_idle_frame(image: Image.Image) -> Image.Image:
    """Create a subtle second pose without mixing another generation's artwork."""
    if image.mode != "P" or image.size != (CANVAS_SIZE, CANVAS_SIZE):
        raise ValueError("Idle animation expects a 64x64 indexed image")

    bbox = image.getbbox()
    if bbox is None:
        raise ValueError("Idle animation cannot be generated from an empty sprite")

    left, top, right, bottom = bbox
    offset: tuple[int, int] | None = None
    if top > 0:
        offset = (0, -1)
    elif bottom < CANVAS_SIZE:
        offset = (0, 1)
    elif left > 0:
        offset = (-1, 0)
    elif right < CANVAS_SIZE:
        offset = (1, 0)
    output = Image.new("P", image.size, 0)
    output.putpalette(image.getpalette())
    if left == 0 and top == 0 and right == CANVAS_SIZE and bottom == CANVAS_SIZE:
        compressed = image.resize((CANVAS_SIZE, CANVAS_SIZE - 1), Image.Resampling.NEAREST)
        output.paste(compressed, (0, 1))
    elif offset is not None:
        output.paste(image, offset)
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


def sprite_source_paths(sprites_root: Path, source_id: str) -> dict[str, Path]:
    return {
        "front": sprites_root / f"{source_id}.png",
        "back": sprites_root / "back" / f"{source_id}.png",
        "shiny_front": sprites_root / "shiny" / f"{source_id}.png",
        "shiny_back": sprites_root / "back/shiny" / f"{source_id}.png",
    }


def load_sprite_set(
    sprites_root: Path,
    source_id: str,
) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    paths = sprite_source_paths(sprites_root, source_id)
    return (
        prepare_rgba(paths["front"]),
        prepare_rgba(paths["back"]),
        prepare_rgba(paths["shiny_front"]),
        prepare_rgba(paths["shiny_back"]),
    )


def write_sprite_set(
    out: Path,
    sprites: tuple[Image.Image, Image.Image, Image.Image, Image.Image],
    normal_palette: Sequence[tuple[int, int, int]] | None = None,
    shiny_palette: Sequence[tuple[int, int, int]] | None = None,
    *,
    animate_front: bool = True,
    write_palettes: bool = True,
) -> None:
    normal_front, normal_back, shiny_front, shiny_back = sprites
    normal_palette = normal_palette or build_normal_palette([normal_front, normal_back])
    indexed_front = index_image(normal_front, normal_palette)
    indexed_back = index_image(normal_back, normal_palette)
    shiny_palette = shiny_palette or build_shiny_palette(
        [normal_front, normal_back],
        [shiny_front, shiny_back],
        [indexed_front, indexed_back],
        normal_palette,
    )

    out.mkdir(parents=True, exist_ok=True)
    indexed_front.save(out / "front.png", optimize=False)
    indexed_back.save(out / "back.png", optimize=False)
    if animate_front:
        idle_frame = build_idle_frame(indexed_front)
        animation = Image.new("P", (64, 128), 0)
        animation.putpalette(indexed_front.getpalette())
        animation.paste(indexed_front, (0, 0))
        animation.paste(idle_frame, (0, 64))
        animation.info["transparency"] = 0
    else:
        # Castform concatenates four 64x64 form frames into one engine sheet.
        # A second idle frame here would shift Rainy/Snowy out of the four
        # indices selected by CastformDataTypeChange.
        animation = indexed_front.copy()
    animation.save(out / "anim_front.png", optimize=False)
    if write_palettes:
        write_jasc(out / "normal.pal", normal_palette)
        write_jasc(out / "shiny.pal", shiny_palette)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def form_record(
    project: Path,
    sprites_root: Path,
    family: str,
    form: str,
    source_id: str,
    out: Path,
) -> dict[str, object]:
    sources = sprite_source_paths(sprites_root, source_id)
    return {
        "family": family,
        "form": form,
        "source_id": source_id,
        "destination": out.relative_to(project).as_posix(),
        "source_sha256": {name: file_sha256(path) for name, path in sources.items()},
        "output_sha256": {
            name: file_sha256(out / name)
            for name in ("front.png", "back.png", "anim_front.png")
        },
    }


def import_unown_forms(project: Path, sprites_root: Path) -> list[dict[str, object]]:
    loaded = {
        form: load_sprite_set(sprites_root, source_id)
        for form, source_id in UNOWN_FORM_SOURCES.items()
    }
    normal_images = [image for sprites in loaded.values() for image in sprites[:2]]
    shiny_images = [image for sprites in loaded.values() for image in sprites[2:]]
    normal_palette = build_normal_palette(normal_images)
    indexed_images = [index_image(image, normal_palette) for image in normal_images]
    shiny_palette = build_shiny_palette(normal_images, shiny_images, indexed_images, normal_palette)

    root = project / "graphics/pokemon/unown"
    write_jasc(root / "normal.pal", normal_palette)
    write_jasc(root / "shiny.pal", shiny_palette)
    records: list[dict[str, object]] = []
    for form, source_id in UNOWN_FORM_SOURCES.items():
        out = root / form
        write_sprite_set(
            out,
            loaded[form],
            normal_palette,
            shiny_palette,
            write_palettes=False,
        )
        if form != "a":
            records.append(form_record(project, sprites_root, "unown", form, source_id, out))
    return records


def import_castform_forms(project: Path, sprites_root: Path) -> list[dict[str, object]]:
    root = project / "graphics/pokemon/castform"
    records: list[dict[str, object]] = []
    for form, source_id in CASTFORM_FORM_SOURCES.items():
        out = root / form
        write_sprite_set(out, load_sprite_set(sprites_root, source_id), animate_front=False)
        records.append(form_record(project, sprites_root, "castform", form, source_id, out))
    return records


def import_hgss_sprites(project: Path, sprites_root: Path) -> dict[str, object]:
    symbols = national_dex_symbols(project)
    required: list[Path] = []
    for dex_id in range(1, 387):
        required.extend(sprite_source_paths(sprites_root, str(dex_id)).values())
    form_source_ids = {
        *UNOWN_FORM_SOURCES.values(),
        *CASTFORM_FORM_SOURCES.values(),
    }
    for source_id in form_source_ids:
        required.extend(sprite_source_paths(sprites_root, source_id).values())
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing HGSS sprites: " + ", ".join(missing[:20]))

    for dex_id, symbol in enumerate(symbols, 1):
        if symbol != "UNOWN":
            write_sprite_set(
                destination(project, symbol),
                load_sprite_set(sprites_root, str(dex_id)),
                animate_front=symbol != "CASTFORM",
            )
        if dex_id % 25 == 0 or dex_id == 386:
            print(f"HGSS sprites: {dex_id}/386")

    forms = [
        *import_unown_forms(project, sprites_root),
        *import_castform_forms(project, sprites_root),
    ]
    report: dict[str, object] = {
        "version": release_version(),
        "source": "PokeAPI/sprites generation-iv/heartgold-soulsilver",
        "source_revision": os.environ.get("POKEAPI_SPRITES_SHA", "unknown"),
        "primary_species_imported": len(symbols),
        "alternative_forms_imported": len(forms),
        "unown_shared_palette": True,
        "castform_per_form_palettes": True,
        "forms": forms,
    }
    (project / f"form_import_{release_tag()}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"HGSS alternative forms: {len(forms)}/30")
    return report
