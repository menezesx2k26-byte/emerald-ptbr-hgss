from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_visual_assets import inspect_indexed_image  # noqa: E402
from validate_rom import validate  # noqa: E402


class ValidationTests(unittest.TestCase):
    def test_indexed_image_accepts_gba_palette_indices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sprite.png"
            image = Image.new("P", (64, 64), 15)
            image.save(path)
            self.assertEqual(inspect_indexed_image(path, (64, 64)), [])

    def test_indexed_image_rejects_out_of_range_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sprite.png"
            image = Image.new("P", (64, 64), 16)
            image.putpalette([0, 0, 0] * 256)
            image.save(path)
            problems = inspect_indexed_image(path, (64, 64))
            self.assertTrue(any("outside 0..15" in problem for problem in problems))

    def test_rom_validator_rejects_truncated_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.gba"
            path.write_bytes(b"not a rom")
            report = validate(path)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["size_is_16_mib"])


if __name__ == "__main__":
    unittest.main()
