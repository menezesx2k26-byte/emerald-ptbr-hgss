from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from instrument_form_battle_test import (  # noqa: E402
    BATTLE_MARKER,
    MAIN_MARKER,
    instrument_project,
)
from validate_form_battle import (  # noqa: E402
    CASTFORM_CASES,
    SPECIES_CASTFORM,
    SPECIES_UNOWN,
    UNOWN_CASES,
    unown_letter,
    validate,
)


MAIN_FIXTURE = '''#include "battle.h"
static void InitMainCallbacks(void);
static void InitMainCallbacks(void)
{
    SetMainCallback2(CB2_InitCopyrightScreenAfterBootup);
    gSaveBlock2Ptr = &gSaveblock2.block;
}
'''

BATTLE_FIXTURE = '''#include "battle_controllers.h"
EWRAM_DATA u8 gBattleMonForms[MAX_BATTLERS_COUNT] = {0};
static void Init(void)
{
    gBattleTerrain = BattleSetup_GetTerrainId();
}
void BattleMainCB2(void)
{
    UpdatePaletteFade();
    RunTasks();

    if (JOY_HELD(B_BUTTON))
        return;
}
'''


def make_raw_report(path: Path) -> None:
    samples: list[dict[str, int]] = []
    personalities = [0, 1, 0x10201, 0x10202, 0x10203]

    for expected in CASTFORM_CASES:
        case_id = expected["case"]
        samples.append(
            {
                "case": case_id,
                "frame": 1000 + case_id * 90,
                "state": 1,
                "mode": 1,
                "expected_value": expected["form"],
                "player_value": expected["form"],
                "opponent_value": expected["form"],
                "player_result": expected["form"] + 1,
                "opponent_result": expected["form"] + 1,
                "error": 0,
                "weather": expected["weather"],
                "player_form": expected["form"],
                "opponent_form": expected["form"],
                "back_species": SPECIES_CASTFORM,
                "front_species": SPECIES_CASTFORM,
                "back_personality": 0x12345678,
                "front_personality": 0x87654321,
                "back_tiles_nonzero": 100,
                "back_tiles_signature": 1000 + case_id,
                "front_tiles_nonzero": 100,
                "front_tiles_signature": 2000 + case_id,
                "back_palette_nonzero": 15,
                "back_palette_signature": 3000 + case_id,
                "front_palette_nonzero": 15,
                "front_palette_signature": 4000 + case_id,
                "pc": 0x08000100,
            }
        )

    for index, expected in enumerate(UNOWN_CASES):
        case_id = expected["case"]
        personality = personalities[index]
        samples.append(
            {
                "case": case_id,
                "frame": 1000 + case_id * 90,
                "state": 1,
                "mode": 2,
                "expected_value": expected["letter"],
                "player_value": expected["letter"],
                "opponent_value": expected["letter"],
                "player_result": 0,
                "opponent_result": 0,
                "error": 0,
                "weather": 0,
                "player_form": 0,
                "opponent_form": 0,
                "back_species": SPECIES_UNOWN,
                "front_species": SPECIES_UNOWN,
                "back_personality": personality,
                "front_personality": personality,
                "back_tiles_nonzero": 100,
                "back_tiles_signature": 1000 + case_id,
                "front_tiles_nonzero": 100,
                "front_tiles_signature": 2000 + case_id,
                "back_palette_nonzero": 15,
                "back_palette_signature": 3500,
                "front_palette_nonzero": 15,
                "front_palette_signature": 4500,
                "pc": 0x08000100,
            }
        )

    path.write_text(
        json.dumps(
            {
                "version": os.environ.get("EMERALD_RELEASE_VERSION", "1.3.1"),
                "status": "passed",
                "crashed": False,
                "game_title": "POKEMON EMER",
                "game_code": "BPEE",
                "rom_size": 16 * 1024 * 1024,
                "frames_reached": 2000,
                "final_state": 2,
                "final_error": 0,
                "case_samples": samples,
            }
        ),
        encoding="utf-8",
    )


class FormBattleInstrumentationTests(unittest.TestCase):
    def test_instruments_ephemeral_game_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text(MAIN_FIXTURE, encoding="utf-8")
            (root / "src" / "battle_main.c").write_text(BATTLE_FIXTURE, encoding="utf-8")

            with patch.dict(os.environ, {"EMERALD_RELEASE_VERSION": "1.4.0-dev.1"}):
                report = instrument_project(root)

            main_text = (root / "src" / "main.c").read_text(encoding="utf-8")
            battle_text = (root / "src" / "battle_main.c").read_text(encoding="utf-8")
            self.assertIn(MAIN_MARKER, main_text)
            self.assertIn(BATTLE_MARKER, battle_text)
            self.assertIn("SetMainCallback2(CB2_FormBattleTestInit)", main_text)
            self.assertIn("CastformDataTypeChange(player)", battle_text)
            self.assertIn("GET_UNOWN_LETTER", battle_text)
            self.assertIn("BattleLoadPlayerMonSpriteGfx(&gPlayerParty[0]", battle_text)
            self.assertIn("gMonSpritesGfxPtr->frameImages[playerPosition]", battle_text)
            self.assertIn("gFormBattleTestReadyMask |= 32", battle_text)
            self.assertIn("gMain.newKeys |= A_BUTTON", battle_text)
            self.assertIn("SetMultiuseSpriteTemplateToPokemon(SPECIES_CASTFORM", battle_text)
            self.assertIn("if (!gFormBattleTestOwnsBattle)\n        RunTasks();", battle_text)
            self.assertEqual(len(report["cases"]), 9)

    def test_instruments_the_v14_quick_start_callback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            main = MAIN_FIXTURE.replace(
                "SetMainCallback2(CB2_InitCopyrightScreenAfterBootup);",
                "SetMainCallback2(CB2_InitMainMenu); /* V14_QUICK_START */",
            )
            (root / "src/main.c").write_text(main, encoding="utf-8")
            (root / "src/battle_main.c").write_text(BATTLE_FIXTURE, encoding="utf-8")
            instrument_project(root)
            self.assertIn(
                "SetMainCallback2(CB2_FormBattleTestInit);",
                (root / "src/main.c").read_text(encoding="utf-8"),
            )

    def test_refuses_to_instrument_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text(MAIN_FIXTURE, encoding="utf-8")
            (root / "src" / "battle_main.c").write_text(BATTLE_FIXTURE, encoding="utf-8")
            instrument_project(root)
            with self.assertRaisesRegex(ValueError, "already instrumented"):
                instrument_project(root)


class FormBattleValidationTests(unittest.TestCase):
    def test_unown_personality_formula(self) -> None:
        self.assertEqual([unown_letter(value) for value in (0, 1, 0x10201, 0x10202, 0x10203)], [0, 1, 25, 26, 27])

    def test_accepts_all_runtime_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.json"
            make_raw_report(path)
            report = validate(path)
            self.assertTrue(report["valid"])
            self.assertTrue(all(report["checks"].values()))

    def test_rejects_wrong_weather_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.json"
            make_raw_report(path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["case_samples"][0]["player_result"] = 0
            path.write_text(json.dumps(raw), encoding="utf-8")

            report = validate(path)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["castform_weather_selection"])

    def test_rejects_duplicate_rendered_form(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.json"
            make_raw_report(path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["case_samples"][1]["back_tiles_signature"] = raw["case_samples"][0]["back_tiles_signature"]
            path.write_text(json.dumps(raw), encoding="utf-8")

            report = validate(path)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["front_and_back_forms_are_distinct"])


if __name__ == "__main__":
    unittest.main()
