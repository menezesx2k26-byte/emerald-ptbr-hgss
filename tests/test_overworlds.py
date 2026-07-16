from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from overworlds import PLAYER_ACTIONS, apply_player_redesign  # noqa: E402


BRENDAN_PALETTE = (
    (115, 197, 164), (255, 213, 180), (255, 197, 148), (222, 148, 115),
    (123, 65, 65), (57, 74, 123), (41, 57, 98), (24, 41, 82),
    (16, 32, 57), (222, 230, 238), (115, 205, 115), (74, 148, 82),
    (255, 98, 90), (197, 65, 65), (255, 255, 255), (0, 0, 0),
)

BRENDAN_REFLECTION_PALETTE = (
    (148, 230, 230), (255, 238, 213), (255, 213, 213), (238, 180, 180),
    (172, 156, 164), (164, 164, 180), (106, 123, 148), (106, 123, 148),
    (123, 131, 131), (238, 238, 255), (164, 246, 156), (123, 205, 123),
    (255, 156, 156), (230, 123, 139), (255, 255, 255), (106, 115, 106),
)


def make_palette(path: Path, colors: tuple[tuple[int, int, int], ...]) -> None:
    body = "\n".join(" ".join(map(str, color)) for color in colors)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"JASC-PAL\n0100\n16\n{body}\n", encoding="utf-8")


def make_sprite(path: Path, player: str) -> None:
    image = Image.new("P", (16, 32), 0)
    palette = [0] * (256 * 3)
    colors = (
        (115, 197, 164),
        (0, 0, 0),
        (255, 255, 255),
        (222, 230, 238),
        (74, 148, 82),
        (115, 205, 115),
        (123, 65, 65),
        (255, 98, 90),
        (106, 213, 65),
        (65, 172, 32),
        (205, 205, 222),
        (197, 65, 65),
        (41, 57, 65),
        (164, 106, 82),
        (222, 164, 148),
        (255, 222, 205),
    )
    for index, color in enumerate(colors):
        palette[index * 3:index * 3 + 3] = color
    image.putpalette(palette)
    pixels = image.load()
    if player == "brendan":
        for y in range(5, 15):
            for x in range(3, 13):
                pixels[x, y] = 2 if x < 8 else 3
        for y in range(16, 30):
            for x in range(3, 13):
                pixels[x, y] = 4 if x < 8 else 5
        pixels[7, 20] = 6
        pixels[8, 20] = 7
    else:
        for y in range(5, 17):
            for x in range(3, 13):
                pixels[x, y] = 8 if x < 8 else 9
        for y in range(17, 30):
            for x in range(3, 13):
                pixels[x, y] = 8 if x < 8 else 9
        pixels[7, 20] = 11
        pixels[8, 20] = 7
        pixels[6, 24] = 12
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


class PlayerOverworldRedesignTests(unittest.TestCase):
    def test_redesigns_every_visible_player_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for player in ("brendan", "may"):
                for action in PLAYER_ACTIONS:
                    make_sprite(root / player / action, player)
            palettes = root.parent / "palettes"
            make_palette(palettes / "brendan.pal", BRENDAN_PALETTE)
            make_palette(palettes / "brendan_reflection.pal", BRENDAN_REFLECTION_PALETTE)

            report = apply_player_redesign(root, palettes)

            self.assertEqual(report["files_checked"], 20)
            self.assertEqual(report["files_changed"], 18)
            self.assertGreater(report["total_changed_pixels"], 1000)
            self.assertEqual(report["runtime_palettes"]["files_changed"], 2)
            self.assertEqual(
                {record["path"] for record in report["records"]},
                {f"{player}/{action}" for player in ("brendan", "may") for action in PLAYER_ACTIONS},
            )

            with Image.open(root / "brendan/walking.png") as brendan:
                self.assertEqual(brendan.mode, "P")
                colors = {color for _, color in brendan.convert("RGB").getcolors(maxcolors=16) or []}
                self.assertIn((255, 197, 49), colors)
                self.assertIn((197, 65, 65), colors)
                self.assertNotIn((74, 148, 82), colors)
            with Image.open(root / "may/walking.png") as may:
                self.assertEqual(may.mode, "P")
                colors = {color for _, color in may.convert("RGB").getcolors(maxcolors=16) or []}
                self.assertIn((255, 255, 255), colors)
                self.assertIn((197, 65, 65), colors)
                self.assertNotIn((106, 213, 65), colors)
            brendan_palette = (palettes / "brendan.pal").read_text(encoding="utf-8")
            self.assertIn("255 197 49", brendan_palette)
            self.assertIn("213 139 32", brendan_palette)
            self.assertNotIn("74 148 82", brendan_palette)
            reflection_palette = (palettes / "brendan_reflection.pal").read_text(encoding="utf-8")
            self.assertIn("255 213 115", reflection_palette)
            self.assertNotIn("123 205 123", reflection_palette)

    def test_requires_all_native_action_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for player in ("brendan", "may"):
                for action in PLAYER_ACTIONS:
                    if player == "may" and action == "fishing.png":
                        continue
                    make_sprite(root / player / action, player)
            with self.assertRaises(FileNotFoundError):
                apply_player_redesign(root, root.parent / "palettes")


if __name__ == "__main__":
    unittest.main()
