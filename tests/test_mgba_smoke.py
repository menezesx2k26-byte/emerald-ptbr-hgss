from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_mgba_smoke import validate  # noqa: E402


def make_frame(path: Path, offset: int) -> None:
    image = Image.new("RGB", (240, 160))
    image.putdata(
        [
            ((x + offset) % 256, (y * 2 + offset) % 256, (x + y + offset) % 256)
            for y in range(160)
            for x in range(240)
        ]
    )
    image.save(path)


def raw_report(path: Path, screenshots: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "1.3.1",
                "status": "passed",
                "crashed": False,
                "game_title": "POKEMON EMER",
                "game_code": "BPEE",
                "rom_size": 16 * 1024 * 1024,
                "platform": 1,
                "frames_reached": 900,
                "frame_samples": [
                    {"frame": 120, "vram_nonzero_samples": 10, "pc": 0x08000100},
                    {"frame": 600, "vram_nonzero_samples": 20, "pc": 0x08000100},
                    {"frame": 900, "vram_nonzero_samples": 30, "pc": 0x08000100},
                ],
                "screenshots": screenshots,
            }
        ),
        encoding="utf-8",
    )


class MgbaSmokeValidationTests(unittest.TestCase):
    def test_accepts_rendered_and_changing_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ["frame-120.png", "frame-600.png", "frame-900.png"]
            for index, name in enumerate(names):
                make_frame(root / name, index * 20)
            report_path = root / "raw.json"
            raw_report(report_path, names)

            report = validate(report_path, root)
            self.assertTrue(report["valid"])
            self.assertTrue(all(report["checks"].values()))

    def test_rejects_three_identical_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ["frame-120.png", "frame-600.png", "frame-900.png"]
            for name in names:
                make_frame(root / name, 0)
            report_path = root / "raw.json"
            raw_report(report_path, names)

            report = validate(report_path, root)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["screenshots_changed"])

    def test_rejects_missing_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ["frame-120.png", "frame-600.png", "missing.png"]
            make_frame(root / names[0], 0)
            make_frame(root / names[1], 20)
            report_path = root / "raw.json"
            raw_report(report_path, names)

            report = validate(report_path, root)
            self.assertFalse(report["valid"])
            self.assertEqual(report["missing_screenshots"], ["missing.png"])


if __name__ == "__main__":
    unittest.main()
