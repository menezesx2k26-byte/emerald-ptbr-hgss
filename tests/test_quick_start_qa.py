from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_quick_start_qa import EXPECTED_LABELS, validate  # noqa: E402


def make_report(root: Path) -> Path:
    samples = []
    for index, label in enumerate(EXPECTED_LABELS, start=1):
        filename = f"quick_start_{index}_{label}.png"
        image = Image.new("RGB", (240, 160), (index * 30, index * 20, 80))
        for color in range(12):
            image.putpixel((color, color), (color * 20, index * 25, 255 - color * 10))
        image.save(root / filename)
        samples.append(
            {
                "label": label,
                "frame": index * 200,
                "screenshot": filename,
                "callback2": 0x08000100 + index * 4,
                "pc": 0x08001000 + index * 4,
            }
        )
    raw = root / "raw.json"
    raw.write_text(
        json.dumps(
            {
                "version": "1.4.0-dev.1",
                "status": "passed",
                "crashed": False,
                "game_title": "POKEMON EMER",
                "game_code": "BPEE",
                "rom_size": 16 * 1024 * 1024,
                "frames_reached": 1200,
                "samples": samples,
            }
        ),
        encoding="utf-8",
    )
    return raw


class QuickStartQaValidationTests(unittest.TestCase):
    def test_accepts_compact_production_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = make_report(root)
            with patch.dict(os.environ, {"EMERALD_RELEASE_VERSION": "1.4.0-dev.1"}):
                report = validate(raw, root)
            self.assertTrue(report["valid"])
            self.assertTrue(all(report["checks"].values()))

    def test_rejects_a_missing_or_repeated_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = make_report(root)
            data = json.loads(raw.read_text(encoding="utf-8"))
            data["samples"][1]["label"] = "main_menu"
            raw.write_text(json.dumps(data), encoding="utf-8")
            with patch.dict(os.environ, {"EMERALD_RELEASE_VERSION": "1.4.0-dev.1"}):
                report = validate(raw, root)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["required_flow_reached"])


if __name__ == "__main__":
    unittest.main()
