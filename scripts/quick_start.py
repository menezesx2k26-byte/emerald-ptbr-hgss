from __future__ import annotations

import json
from pathlib import Path

from release import release_tag, release_version


MAIN_INCLUDE_MARKER = '#include "main_menu.h" /* V14_QUICK_START */'
MAIN_BOOT_OLD = "    SetMainCallback2(CB2_InitCopyrightScreenAfterBootup);"
MAIN_BOOT_NEW = "    SetMainCallback2(CB2_InitMainMenu); /* V14_QUICK_START */"

BIRCH_TAIL_OLD = """    AddBirchSpeechObjects(taskId);
    BeginNormalPaletteFade(PALETTES_ALL, 0, 16, 0, RGB_BLACK);
    gTasks[taskId].tBG1HOFS = 0;
    gTasks[taskId].func = Task_NewGameBirchSpeech_WaitToShowBirch;
    gTasks[taskId].tPlayerSpriteId = SPRITE_NONE;
    gTasks[taskId].data[3] = 0xFF;
    gTasks[taskId].tTimer = 0xD8;
    PlayBGM(MUS_ROUTE122);
    ShowBg(0);
    ShowBg(1);
}"""

BIRCH_TAIL_NEW = """    AddBirchSpeechObjects(taskId);
    BeginNormalPaletteFade(PALETTES_ALL, 0, 16, 0, RGB_BLACK);
    gTasks[taskId].tBG1HOFS = 0;
    gTasks[taskId].tPlayerSpriteId = gTasks[taskId].tBrendanSpriteId;
    gTasks[taskId].tPlayerGender = MALE;
    gTasks[taskId].data[3] = 0xFF;
    gTasks[taskId].tTimer = 0;
    gSprites[gTasks[taskId].tPlayerSpriteId].x = 180;
    gSprites[gTasks[taskId].tPlayerSpriteId].y = 60;
    gSprites[gTasks[taskId].tPlayerSpriteId].invisible = FALSE;
    InitWindows(sNewGameBirchSpeechTextWindows);
    LoadMainMenuWindowFrameTiles(0, 0xF3);
    LoadMessageBoxGfx(0, 0xFC, BG_PLTT_ID(15));
    NewGameBirchSpeech_ShowDialogueWindow(0, 1);
    PutWindowTilemap(0);
    CopyWindowToVram(0, COPYWIN_GFX);
    NewGameBirchSpeech_ClearWindow(0);
    gTasks[taskId].func = Task_NewGameBirchSpeech_BoyOrGirl; /* V14_QUICK_START */
    PlayBGM(MUS_ROUTE122);
    ShowBg(0);
    ShowBg(1);
}"""

NAMING_RETURN_OLD = """    u8 taskId;
    u8 spriteId;
    u16 savedIme;

    ResetBgsAndClearDma3BusyFlags(0);"""

NAMING_RETURN_NEW = """    u8 taskId;
    u8 spriteId;
    u16 savedIme;

    /* V14_QUICK_START: gender and name are the only required new-game setup. */
    SetMainCallback2(CB2_NewGame);
    return;

    ResetBgsAndClearDma3BusyFlags(0);"""


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def patch_main(text: str) -> str:
    if MAIN_BOOT_NEW in text:
        return text
    text = _replace_once(
        text,
        '#include "main.h"',
        '#include "main.h"\n' + MAIN_INCLUDE_MARKER,
        "main menu include",
    )
    return _replace_once(text, MAIN_BOOT_OLD, MAIN_BOOT_NEW, "boot callback")


def patch_main_menu(text: str) -> str:
    if "Task_NewGameBirchSpeech_BoyOrGirl; /* V14_QUICK_START */" in text:
        return text
    text = _replace_once(text, BIRCH_TAIL_OLD, BIRCH_TAIL_NEW, "Birch intro tail")
    return _replace_once(text, NAMING_RETURN_OLD, NAMING_RETURN_NEW, "naming return callback")


def apply_quick_start(project: Path) -> dict[str, object]:
    main_path = project / "src/main.c"
    main_menu_path = project / "src/main_menu.c"
    main_path.write_text(patch_main(main_path.read_text(encoding="utf-8")), encoding="utf-8")
    main_menu_path.write_text(
        patch_main_menu(main_menu_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    report: dict[str, object] = {
        "version": release_version(),
        "boot_flow": "Power-on opens the main menu directly; copyright, logo, cinematic and title loops are skipped.",
        "new_game_flow": "New Game keeps gender and player-name selection, then starts in Littleroot.",
        "skipped_new_game_steps": [
            "Birch welcome speech",
            "Lotad demonstration",
            "name confirmation speech",
            "player shrink animation",
        ],
        "save_compatibility": "Continue remains available and existing saves are unchanged.",
    }
    (project / f"quick_start_{release_tag()}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
