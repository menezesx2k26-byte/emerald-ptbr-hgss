from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from quick_start import (  # noqa: E402
    BIRCH_TAIL_OLD,
    INTRO_BOOT_OLD,
    NAMING_RETURN_OLD,
    apply_quick_start,
    patch_intro,
    patch_main_menu,
)
from release import release_tag  # noqa: E402


INTRO_FIXTURE = f'''#include "intro.h"
#include "main.h"
{INTRO_BOOT_OLD}
'''

MAIN_MENU_FIXTURE = f'''static void Task_NewGameBirchSpeech_Init(u8 taskId)
{{
{BIRCH_TAIL_OLD}

static void CB2_NewGameBirchSpeech_ReturnFromNamingScreen(void)
{{
{NAMING_RETURN_OLD}
}}
'''


class QuickStartTests(unittest.TestCase):
    def test_skips_boot_cinematic_and_birch_speech(self) -> None:
        intro = patch_intro(INTRO_FIXTURE)
        main_menu = patch_main_menu(MAIN_MENU_FIXTURE)
        self.assertIn('#include "main_menu.h" /* V14_QUICK_START */', intro)
        self.assertIn("SetMainCallback2(CB2_InitMainMenu); /* V14_QUICK_START */", intro)
        self.assertIn("SetSaveBlocksPointers(GetSaveBlocksPointersBaseOffset());", intro)
        self.assertIn("LoadGameSave(SAVE_NORMAL);", intro)
        self.assertIn("SetSerialCallback(SerialCB);", intro)
        self.assertIn("Task_NewGameBirchSpeech_BoyOrGirl; /* V14_QUICK_START */", main_menu)
        self.assertIn("SetMainCallback2(CB2_NewGame);", main_menu)
        self.assertNotIn("tTimer = 0xD8", main_menu)

    def test_project_patch_is_idempotent_and_reports_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "src").mkdir()
            (project / "src/intro.c").write_text(INTRO_FIXTURE, encoding="utf-8")
            (project / "src/main_menu.c").write_text(MAIN_MENU_FIXTURE, encoding="utf-8")

            report = apply_quick_start(project)
            first_intro = (project / "src/intro.c").read_text(encoding="utf-8")
            first_menu = (project / "src/main_menu.c").read_text(encoding="utf-8")
            apply_quick_start(project)

            self.assertEqual(first_intro, (project / "src/intro.c").read_text(encoding="utf-8"))
            self.assertEqual(first_menu, (project / "src/main_menu.c").read_text(encoding="utf-8"))
            self.assertIn("gender and player-name selection", report["new_game_flow"])
            self.assertTrue((project / f"quick_start_{release_tag()}.json").exists())


if __name__ == "__main__":
    unittest.main()
