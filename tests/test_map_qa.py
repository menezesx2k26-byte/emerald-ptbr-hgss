from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/rebuild-v1.4.yml"
sys.path.insert(0, str(SCRIPTS))

from instrument_map_qa import (  # noqa: E402
    MAIN_MARKER,
    OVERWORLD_MARKER,
    instrument_project,
)
from compose_map_qa_sheet import compose  # noqa: E402
from patch_mgba_headless_video import MARKER as MGBA_VIDEO_MARKER, patch_source  # noqa: E402
from release import release_version  # noqa: E402
from validate_map_qa import EXPECTED_CASES, validate  # noqa: E402


MAIN_FIXTURE = '''#include "global.h"
static void InitMainCallbacks(void);
static void InitMainCallbacks(void)
{
    SetMainCallback2(CB2_InitCopyrightScreenAfterBootup);
    gSaveBlock2Ptr = &gSaveblock2.block;
}
'''

OVERWORLD_FIXTURE = '''#include "global.h"
#include "overworld.h"
COMMON_DATA u16 *gOverworldTilemapBuffer_Bg2 = NULL;
void CB2_OverworldBasic(void)
{
    OverworldBasic();
}
void CB2_Overworld(void)
{
    bool32 fading = (gPaletteFade.active != 0);
    OverworldBasic();
    if (fading)
        SetFieldVBlankCallback();
}
'''


def make_raw_report(path: Path, screenshots: Path) -> None:
    samples = []
    for case_id, name, x, y in EXPECTED_CASES:
        filename = f"map_qa_{case_id}_{name}.png"
        image = Image.new("RGB", (240, 160), (case_id * 40, case_id * 20, 80))
        for color in range(24):
            for py in range(160):
                image.putpixel((color, py), ((color * 8) % 256, case_id * 30, (color * 11) % 256))
        image.save(screenshots / filename)
        samples.append({
            "case": case_id,
            "name": name,
            "frame": case_id * 200,
            "map_group": case_id,
            "map_num": case_id + 10,
            "x": x,
            "y": y,
            "timer": 120,
            "screenshot": filename,
            "vram_nonzero": 100,
            "vram_signature": 1000 + case_id,
            "palette_nonzero": 100,
            "palette_signature": 2000 + case_id,
            "oam_nonzero": 100,
            "oam_signature": 3000 + case_id,
            "pc": 0x08000100,
        })
    path.write_text(json.dumps({
        "version": release_version(),
        "status": "passed",
        "crashed": False,
        "game_title": "POKEMON EMER",
        "game_code": "BPEE",
        "rom_size": 16 * 1024 * 1024,
        "frames_reached": 1000,
        "final_state": 2,
        "final_error": 0,
        "case_samples": samples,
    }), encoding="utf-8")


class MapQaInstrumentationTests(unittest.TestCase):
    def test_instruments_boot_and_overworld_loop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/main.c").write_text(MAIN_FIXTURE, encoding="utf-8")
            (root / "src/overworld.c").write_text(OVERWORLD_FIXTURE, encoding="utf-8")
            report = instrument_project(root)
            main = (root / "src/main.c").read_text(encoding="utf-8")
            overworld = (root / "src/overworld.c").read_text(encoding="utf-8")
            self.assertIn(MAIN_MARKER, main)
            self.assertIn(OVERWORLD_MARKER, overworld)
            self.assertIn("SetMainCallback2(CB2_MapQaInit)", main)
            self.assertIn("MapQaStep();", overworld)
            self.assertIn("MAP_GROUP(PETALBURG_WOODS)", overworld)
            self.assertEqual(len(report["cases"]), 4)

    def test_refuses_double_instrumentation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/main.c").write_text(MAIN_FIXTURE, encoding="utf-8")
            (root / "src/overworld.c").write_text(OVERWORLD_FIXTURE, encoding="utf-8")
            instrument_project(root)
            with self.assertRaisesRegex(ValueError, "already instrumented"):
                instrument_project(root)


class MapQaValidationTests(unittest.TestCase):
    def test_workflow_uses_framebuffer_frontend_for_screenshots(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("patch_mgba_headless_video.py", workflow)
        self.assertIn(
            'mgba-build/mgba-headless \\\n'
            '            --script "$GITHUB_WORKSPACE/scripts/mgba_map_qa.lua"',
            workflow,
        )

    def test_headless_patch_installs_and_cleans_up_video_buffer(self) -> None:
        source = '''static struct mCore* core;
int main(void)
{
\tcore->init(core);
loadError:
\tcore->deinit(core);
argsExit:
\tfor (i = 0; i < 1; ++i)
\t\tfree(items[i]);
}
'''
        patched = patch_source(source)
        self.assertIn(MGBA_VIDEO_MARKER, patched)
        self.assertIn("core->setVideoBuffer(core, sHeadlessVideoBuffer, 256);", patched)
        self.assertIn("free(sHeadlessVideoBuffer);", patched)

    def test_accepts_four_distinct_runtime_screenshots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            make_raw_report(raw, root)
            report = validate(raw, root)
            self.assertTrue(report["valid"])
            self.assertTrue(all(report["checks"].values()))
            sheet = compose(root, root / "contact-sheet.png")
            with Image.open(sheet) as image:
                self.assertEqual(image.size, (480, 320))

    def test_rejects_duplicate_runtime_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            make_raw_report(raw, root)
            data = json.loads(raw.read_text(encoding="utf-8"))
            first = root / data["case_samples"][0]["screenshot"]
            second = root / data["case_samples"][1]["screenshot"]
            second.write_bytes(first.read_bytes())
            report = validate(raw, root)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["screenshots_are_distinct"])


if __name__ == "__main__":
    unittest.main()
