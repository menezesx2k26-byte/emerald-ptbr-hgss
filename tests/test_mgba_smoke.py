from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_mgba_smoke import validate  # noqa: E402
from release import release_version  # noqa: E402


def raw_report(path: Path, *, static: bool = False, crashed: bool = False, sample_count: int = 3) -> None:
    signatures = [101, 202, 303] if not static else [101, 101, 101]
    path.write_text(
        json.dumps(
            {
                "version": release_version(),
                "status": "crashed" if crashed else "passed",
                "crashed": crashed,
                "game_title": "POKEMON EMER",
                "game_code": "BPEE",
                "rom_size": 16 * 1024 * 1024,
                "platform": 1,
                "frames_reached": 900,
                "frame_samples": [
                    {
                        "frame": frame,
                        "vram_nonzero_samples": 10 + index,
                        "vram_signature": signatures[index],
                        "palette_nonzero_samples": 8 + index,
                        "palette_signature": signatures[index] + 1,
                        "oam_nonzero_samples": index,
                        "oam_signature": signatures[index] + 2,
                        "pc": 0x08000100,
                    }
                    for index, frame in enumerate((5, 120, 900)[:sample_count])
                ],
            }
        ),
        encoding="utf-8",
    )


class MgbaSmokeValidationTests(unittest.TestCase):
    def test_accepts_initialized_and_changing_video_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "raw.json"
            raw_report(report_path)

            report = validate(report_path)
            self.assertTrue(report["valid"])
            self.assertTrue(all(report["checks"].values()))

    def test_rejects_static_video_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "raw.json"
            raw_report(report_path, static=True)

            report = validate(report_path)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["video_memory_changed"])

    def test_rejects_crash_or_missing_frame_sample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "raw.json"
            raw_report(report_path, crashed=True, sample_count=2)

            report = validate(report_path)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["emulator_reported_pass"])
            self.assertFalse(report["checks"]["target_frames_reached"])


if __name__ == "__main__":
    unittest.main()
