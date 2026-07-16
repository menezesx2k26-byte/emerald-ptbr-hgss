from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_pokemmo_mod import VARIANTS, build_mod  # noqa: E402
from common import write_jasc  # noqa: E402


def fake_sprite_set(root: Path, *, one_front_frame: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    palette = [(0, 0, 0), (24, 160, 80), (232, 184, 48)] + [(0, 0, 0)] * 13
    shiny = [(0, 0, 0), (72, 128, 232), (232, 96, 72)] + [(0, 0, 0)] * 13
    front = Image.new("P", (64, 64), 0)
    front.putpalette([channel for color in palette for channel in color] + [0] * (768 - 48))
    for y in range(20, 54):
        for x in range(22, 42):
            front.putpixel((x, y), 1 if y < 40 else 2)
    front.info["transparency"] = 0
    front.save(root / "front.png")
    front.save(root / "back.png")
    if one_front_frame:
        animation = front
    else:
        animation = Image.new("P", (64, 128), 0)
        animation.putpalette(front.getpalette())
        animation.paste(front, (0, 0))
        animation.paste(front, (0, 63))
        animation.info["transparency"] = 0
    animation.save(root / "anim_front.png")
    write_jasc(root / "normal.pal", palette)
    write_jasc(root / "shiny.pal", shiny)


def move_palettes_to_parent(root: Path) -> None:
    for name in ("normal.pal", "shiny.pal"):
        (root / name).replace(root.parent / name)


class PokeMMOModTests(unittest.TestCase):
    def test_builds_valid_flat_mod_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "game"
            fake_sprite_set(project / "graphics/pokemon/treecko")
            fake_sprite_set(project / "graphics/pokemon/bulbasaur")
            fake_sprite_set(project / "graphics/pokemon/unown/a")
            move_palettes_to_parent(project / "graphics/pokemon/unown/a")
            fake_sprite_set(project / "graphics/pokemon/castform/normal", one_front_frame=True)
            output = root / "Emerald-HGSS-Visual-386-v0.1.0.mod"

            report = build_mod(
                project,
                output,
                species=[(1, "BULBASAUR"), (201, "UNOWN"), (385, "CASTFORM")],
                source_revision="test-revision",
            )

            self.assertTrue(report["valid"])
            self.assertEqual(report["species"], 3)
            self.assertEqual(report["actual_sprite_files"], 3 * len(VARIANTS))
            self.assertEqual(report["animated_front_files"], 4)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("info.xml", names)
                self.assertIn("icon.png", names)
                self.assertIn("sprites/battlesprites/001-front-n.gif", names)
                self.assertIn("sprites/battlesprites/385-back-s.gif", names)
                self.assertFalse(any(name.startswith("Emerald-HGSS") for name in names))
                info = ElementTree.fromstring(archive.read("info.xml"))
                self.assertEqual(info.tag, "resource")
                self.assertEqual(info.attrib["author"], "Gabriel Menezes")

    def test_rejects_non_indexed_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "game"
            fake_sprite_set(project / "graphics/pokemon/treecko")
            fake_sprite_set(project / "graphics/pokemon/bulbasaur")
            Image.new("RGBA", (64, 128), (0, 0, 0, 0)).save(
                project / "graphics/pokemon/bulbasaur/anim_front.png"
            )
            with self.assertRaisesRegex(ValueError, "Invalid Emerald animation sheet"):
                build_mod(
                    project,
                    root / "bad.mod",
                    species=[(1, "BULBASAUR")],
                )


if __name__ == "__main__":
    unittest.main()
