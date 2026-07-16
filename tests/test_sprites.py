from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from sprites import (  # noqa: E402
    CASTFORM_FORM_SOURCES,
    UNOWN_FORM_SOURCES,
    build_idle_frame,
    sprite_source_paths,
    write_sprite_set,
)


class IdleFrameTests(unittest.TestCase):
    def test_moves_indexed_pose_without_changing_palette(self) -> None:
        image = Image.new("P", (64, 64), 0)
        palette = [0, 0, 0, 248, 128, 64] + [0, 0, 0] * 254
        image.putpalette(palette)
        for y in range(20, 50):
            for x in range(24, 40):
                image.putpixel((x, y), 1)

        frame = build_idle_frame(image)

        self.assertEqual(frame.mode, "P")
        self.assertEqual(frame.size, (64, 64))
        self.assertEqual(frame.getpalette(), image.getpalette())
        self.assertNotEqual(frame.tobytes(), image.tobytes())
        self.assertEqual(frame.getbbox(), (24, 19, 40, 49))

    def test_rejects_empty_sprite(self) -> None:
        image = Image.new("P", (64, 64), 0)
        with self.assertRaisesRegex(ValueError, "empty sprite"):
            build_idle_frame(image)

    def test_compresses_full_canvas_pose_without_clipping_failure(self) -> None:
        image = Image.new("P", (64, 64), 1)
        image.putpalette([0, 0, 0] * 256)
        frame = build_idle_frame(image)
        self.assertNotEqual(frame.tobytes(), image.tobytes())
        self.assertEqual(frame.getbbox(), (0, 1, 64, 64))


class AlternativeFormSourceTests(unittest.TestCase):
    def test_castform_form_keeps_one_engine_frame(self) -> None:
        normal = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        shiny = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        for y in range(20, 40):
            for x in range(24, 40):
                normal.putpixel((x, y), (240, 120, 40, 255))
                shiny.putpixel((x, y), (80, 160, 240, 255))

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "castform"
            write_sprite_set(
                out,
                (normal, normal, shiny, shiny),
                animate_front=False,
            )
            with Image.open(out / "front.png") as front, Image.open(out / "anim_front.png") as animation:
                self.assertEqual(animation.size, (64, 64))
                self.assertEqual(animation.tobytes(), front.tobytes())

    def test_unown_source_map_covers_all_28_forms(self) -> None:
        self.assertEqual(len(UNOWN_FORM_SOURCES), 28)
        self.assertEqual(UNOWN_FORM_SOURCES["a"], "201")
        self.assertEqual(UNOWN_FORM_SOURCES["z"], "201-z")
        self.assertEqual(UNOWN_FORM_SOURCES["exclamation_mark"], "201-exclamation")
        self.assertEqual(UNOWN_FORM_SOURCES["question_mark"], "201-question")
        self.assertEqual(len(set(UNOWN_FORM_SOURCES.values())), 28)

    def test_castform_source_map_uses_pokeapi_weather_ids(self) -> None:
        self.assertEqual(CASTFORM_FORM_SOURCES, {
            "sunny": "10013",
            "rainy": "10014",
            "snowy": "10015",
        })
        self.assertEqual(len(UNOWN_FORM_SOURCES) - 1 + len(CASTFORM_FORM_SOURCES), 30)

    def test_source_paths_include_back_and_shiny_variants(self) -> None:
        root = Path("hgss")
        self.assertEqual(sprite_source_paths(root, "201-question"), {
            "front": root / "201-question.png",
            "back": root / "back/201-question.png",
            "shiny_front": root / "shiny/201-question.png",
            "shiny_back": root / "back/shiny/201-question.png",
        })


if __name__ == "__main__":
    unittest.main()
