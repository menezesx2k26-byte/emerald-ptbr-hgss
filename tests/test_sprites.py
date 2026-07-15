from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from sprites import build_idle_frame  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
