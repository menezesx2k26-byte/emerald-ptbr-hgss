from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import write_jasc  # noqa: E402
from maps import clone_tileset, restyle_tileset_art  # noqa: E402
from render_map_previews import render_pilot_maps  # noqa: E402


PALETTE = [(index * 8, index * 8, index * 8) for index in range(16)]


def make_tileset(root: Path, *, height: int = 256, fill: int = 0xD) -> None:
    (root / "palettes").mkdir(parents=True)
    image = Image.new("P", (128, height), fill)
    image.putpalette([component for color in PALETTE for component in color] + [0] * (768 - 48))
    image.save(root / "tiles.png")
    for index in range(16):
        write_jasc(root / "palettes" / f"{index:02}.pal", PALETTE)
    (root / "metatiles.bin").write_bytes(struct.pack("<16H", *([0] * 16)))
    (root / "metatile_attributes.bin").write_bytes(b"\x00\x00\x00\x00")


class MapArtTests(unittest.TestCase):
    def test_primary_pixel_art_pass_changes_tiles_without_expanding_palette(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "tileset"
            make_tileset(root)
            before = (root / "tiles.png").read_bytes()
            report = restyle_tileset_art(root, "town", "primary")
            with Image.open(root / "tiles.png") as image:
                self.assertEqual(image.size, (128, 256))
                self.assertEqual(image.mode, "P")
                self.assertLessEqual(max(image.tobytes()), 15)
            self.assertNotEqual((root / "tiles.png").read_bytes(), before)
            self.assertGreater(report["pixels_changed"], 0)
            self.assertGreater(report["tiles_changed"], 0)

    def test_clone_preserves_geometry_and_records_real_pixel_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "data/tilesets/primary/general"
            make_tileset(source)
            destination = project / "data/tilesets/primary/hgss_town"
            record = clone_tileset(
                project,
                "data/tilesets/primary/general",
                "data/tilesets/primary/hgss_town",
                "town",
                role="primary",
            )
            self.assertEqual(
                (destination / "metatiles.bin").read_bytes(),
                (source / "metatiles.bin").read_bytes(),
            )
            self.assertEqual(
                (destination / "metatile_attributes.bin").read_bytes(),
                (source / "metatile_attributes.bin").read_bytes(),
            )
            self.assertNotEqual(record["source_tiles_sha256"], record["output_sha256"])
            self.assertGreater(record["pixels_changed"], 0)


class MapPreviewTests(unittest.TestCase):
    def test_renders_all_four_pilot_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            roots = (
                project / "data/tilesets/primary/hgss_town",
                project / "data/tilesets/secondary/hgss_small_town",
                project / "data/tilesets/primary/hgss_forest",
                project / "data/tilesets/secondary/hgss_forest",
            )
            for root in roots:
                make_tileset(root)

            layouts = []
            definitions = (
                ("LittlerootTown_Layout", "LittlerootTown"),
                ("OldaleTown_Layout", "OldaleTown"),
                ("Route101_Layout", "Route101"),
                ("PetalburgWoods_Layout", "PetalburgWoods"),
            )
            for name, directory_name in definitions:
                layout_root = project / "data/layouts" / directory_name
                layout_root.mkdir(parents=True)
                (layout_root / "map.bin").write_bytes(struct.pack("<H", 0))
                layouts.append({
                    "name": name,
                    "width": 1,
                    "height": 1,
                    "blockdata_filepath": f"data/layouts/{directory_name}/map.bin",
                })
            layouts_root = project / "data/layouts"
            (layouts_root / "layouts.json").write_text(
                json.dumps({"layouts": layouts}),
                encoding="utf-8",
            )
            output = project / "previews"
            report = render_pilot_maps(project, output)
            self.assertEqual(len(report["maps"]), 4)
            self.assertTrue(all((output / record["file"]).exists() for record in report["maps"]))
            self.assertTrue(all(record["sha256"] for record in report["maps"]))


if __name__ == "__main__":
    unittest.main()
