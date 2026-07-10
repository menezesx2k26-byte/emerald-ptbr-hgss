from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image


def read_jasc(path: Path) -> list[tuple[int, int, int]]:
    lines = path.read_text(encoding="ascii").splitlines()
    colors = [tuple(map(int, line.split())) for line in lines[3:19]]
    if len(colors) != 16:
        raise ValueError(f"Invalid 16-colour JASC palette: {path}")
    return colors


def write_jasc(path: Path, colors: Sequence[tuple[int, int, int]]) -> None:
    if len(colors) < 16:
        raise ValueError("Expected at least 16 palette colours")
    path.write_text(
        "JASC-PAL\n0100\n16\n"
        + "\n".join(f"{r} {g} {b}" for r, g, b in colors[:16])
        + "\n",
        encoding="ascii",
    )


def apply_palette(image: Image.Image, colors: Sequence[tuple[int, int, int]]) -> Image.Image:
    if image.mode != "P":
        image = image.convert("P")
    flat: list[int] = []
    for color in colors[:16]:
        flat.extend(color)
    flat.extend([0] * (768 - len(flat)))
    image.putpalette(flat)
    return image


def gba_channel(value: float) -> int:
    return max(0, min(248, int(round(value / 8.0)) * 8))


def gba_color(rgb: Sequence[int]) -> tuple[int, int, int]:
    return tuple(gba_channel(float(value)) for value in rgb[:3])  # type: ignore[return-value]
