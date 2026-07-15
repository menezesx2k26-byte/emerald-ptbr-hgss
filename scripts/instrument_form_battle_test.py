from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release import release_version


MAIN_MARKER = "/* FORM_BATTLE_TEST_MAIN_INSTRUMENTATION */"
BATTLE_MARKER = "/* FORM_BATTLE_TEST_RUNTIME_INSTRUMENTATION */"

UNOWN_CASES = (
    ("unown_a", 0, 0x00000000),
    ("unown_b", 1, 0x00000001),
    ("unown_z", 25, 0x00010201),
    ("unown_exclamation", 26, 0x00010202),
    ("unown_question", 27, 0x00010203),
)

CASES = (
    {"id": 1, "name": "castform_sunny", "mode": "castform", "form": 1, "weather": 1 << 5},
    {"id": 2, "name": "castform_rainy", "mode": "castform", "form": 2, "weather": 1 << 0},
    {"id": 3, "name": "castform_snowy", "mode": "castform", "form": 3, "weather": 1 << 7},
    {"id": 4, "name": "castform_normal", "mode": "castform", "form": 0, "weather": 0},
    *(
        {
            "id": index + 5,
            "name": name,
            "mode": "unown",
            "letter": letter,
            "personality": personality,
        }
        for index, (name, letter, personality) in enumerate(UNOWN_CASES)
    ),
)


MAIN_INCLUDES = '''#include "battle.h"
#include "battle_main.h"
#include "pokemon.h"
#include "constants/pokemon.h"
#include "constants/species.h"'''


MAIN_DECLARATION = f'''{MAIN_MARKER}
static void CB2_FormBattleTestInit(void);
static void CB2_FormBattleTestDone(void);
'''


MAIN_RUNTIME = '''/* FORM_BATTLE_TEST_MAIN_RUNTIME */
static const u32 sFormBattleTestUnownPersonalities[] =
{
    0x00000000, // A
    0x00000001, // B
    0x00010201, // Z
    0x00010202, // !
    0x00010203, // ?
};

static void CB2_FormBattleTestDone(void)
{
}

static void CB2_FormBattleTestInit(void)
{
    u32 i;

    SeedRng(0x14A4);
    ZeroPlayerPartyMons();
    ZeroEnemyPartyMons();

    CreateMon(&gPlayerParty[0], SPECIES_CASTFORM, 50, 31, TRUE, 0x12345678, OT_ID_PRESET, 0x10203040);
    CreateMon(&gEnemyParty[0], SPECIES_CASTFORM, 50, 31, TRUE, 0x87654321, OT_ID_PRESET, 0x40302010);

    for (i = 0; i < ARRAY_COUNT(sFormBattleTestUnownPersonalities); i++)
    {
        CreateMon(&gPlayerParty[i + 1], SPECIES_UNOWN, 50, 31, TRUE,
                  sFormBattleTestUnownPersonalities[i], OT_ID_PRESET, 0x10203040);
        CreateMon(&gEnemyParty[i + 1], SPECIES_UNOWN, 50, 31, TRUE,
                  sFormBattleTestUnownPersonalities[i], OT_ID_PRESET, 0x40302010);
    }

    gBattleTypeFlags = 0;
    gMain.savedCallback = CB2_FormBattleTestDone;
    CB2_InitBattle();
}

'''


BATTLE_GLOBALS = '''/* FORM_BATTLE_TEST_RUNTIME_INSTRUMENTATION */
EWRAM_DATA u8 gFormBattleTestState = 0;
EWRAM_DATA u8 gFormBattleTestCase = 0;
EWRAM_DATA u8 gFormBattleTestMode = 0;
EWRAM_DATA u8 gFormBattleTestExpectedValue = 0;
EWRAM_DATA u8 gFormBattleTestPlayerValue = 0;
EWRAM_DATA u8 gFormBattleTestOpponentValue = 0;
EWRAM_DATA u8 gFormBattleTestPlayerResult = 0;
EWRAM_DATA u8 gFormBattleTestOpponentResult = 0;
EWRAM_DATA u8 gFormBattleTestError = 0;
EWRAM_DATA u8 gFormBattleTestBackPaletteNum = 0;
EWRAM_DATA u8 gFormBattleTestFrontPaletteNum = 0;
EWRAM_DATA u16 gFormBattleTestBackTileNum = 0;
EWRAM_DATA u16 gFormBattleTestFrontTileNum = 0;
EWRAM_DATA u16 gFormBattleTestBackSpecies = 0;
EWRAM_DATA u16 gFormBattleTestFrontSpecies = 0;
EWRAM_DATA u32 gFormBattleTestBackPersonality = 0;
EWRAM_DATA u32 gFormBattleTestFrontPersonality = 0;
'''


BATTLE_RUNTIME = '''/* FORM_BATTLE_TEST_RUNTIME */
#define FORM_BATTLE_TEST_MODE_CASTFORM 1
#define FORM_BATTLE_TEST_MODE_UNOWN    2
#define FORM_BATTLE_TEST_CASE_COUNT    9

static u16 sFormBattleTestWarmup = 0;
static u16 sFormBattleTestCaseTimer = 0;
static u8 sFormBattleTestNextCase = 0;

static bool8 FormBattleTestSpritesReady(u8 player, u8 opponent)
{
    u8 playerSpriteId = gBattlerSpriteIds[player];
    u8 opponentSpriteId = gBattlerSpriteIds[opponent];

    if (gBattlersCount != 2
     || gBattleMons[player].species != SPECIES_CASTFORM
     || gBattleMons[opponent].species != SPECIES_CASTFORM
     || playerSpriteId >= MAX_SPRITES
     || opponentSpriteId >= MAX_SPRITES)
        return FALSE;

    if (!gSprites[playerSpriteId].inUse
     || !gSprites[opponentSpriteId].inUse
     || gSprites[playerSpriteId].invisible
     || gSprites[opponentSpriteId].invisible)
        return FALSE;

    return TRUE;
}

static void FormBattleTestFreezeAndPositionSprite(u8 battler, u16 species)
{
    struct Sprite *sprite = &gSprites[gBattlerSpriteIds[battler]];

    sprite->data[2] = species;
    sprite->callback = SpriteCallbackDummy;
    sprite->invisible = FALSE;
    sprite->x2 = 0;
    sprite->y2 = 0;
    sprite->y = GetBattlerSpriteFinal_Y(battler, species, FALSE);
}

static void FormBattleTestPublishSpriteMetadata(u8 player, u8 opponent)
{
    struct Sprite *backSprite = &gSprites[gBattlerSpriteIds[player]];
    struct Sprite *frontSprite = &gSprites[gBattlerSpriteIds[opponent]];

    gFormBattleTestBackTileNum = backSprite->oam.tileNum;
    gFormBattleTestFrontTileNum = frontSprite->oam.tileNum;
    gFormBattleTestBackPaletteNum = backSprite->oam.paletteNum;
    gFormBattleTestFrontPaletteNum = frontSprite->oam.paletteNum;
}

static void FormBattleTestApplyCastformCase(u8 caseId, u8 player, u8 opponent)
{
    static const u16 sWeather[] =
    {
        B_WEATHER_SUN_TEMPORARY,
        B_WEATHER_RAIN_TEMPORARY,
        B_WEATHER_HAIL_TEMPORARY,
        0,
    };
    static const u8 sForms[] =
    {
        CASTFORM_FIRE,
        CASTFORM_WATER,
        CASTFORM_ICE,
        CASTFORM_NORMAL,
    };
    u8 index = caseId - 1;
    u8 expectedForm = sForms[index];

    gBattlerPartyIndexes[player] = 0;
    gBattlerPartyIndexes[opponent] = 0;
    gBattleWeather = sWeather[index];
    gFormBattleTestMode = FORM_BATTLE_TEST_MODE_CASTFORM;
    gFormBattleTestExpectedValue = expectedForm;
    gFormBattleTestBackSpecies = SPECIES_CASTFORM;
    gFormBattleTestFrontSpecies = SPECIES_CASTFORM;
    gFormBattleTestBackPersonality = GetMonData(&gPlayerParty[0], MON_DATA_PERSONALITY);
    gFormBattleTestFrontPersonality = GetMonData(&gEnemyParty[0], MON_DATA_PERSONALITY);

    gFormBattleTestPlayerResult = CastformDataTypeChange(player);
    if (gFormBattleTestPlayerResult != expectedForm + 1)
        gFormBattleTestError |= 1;
    gBattleSpritesDataPtr->animationData->animArg = expectedForm;
    HandleSpeciesGfxDataChange(player, opponent, TRUE);

    gFormBattleTestOpponentResult = CastformDataTypeChange(opponent);
    if (gFormBattleTestOpponentResult != expectedForm + 1)
        gFormBattleTestError |= 2;
    gBattleSpritesDataPtr->animationData->animArg = expectedForm;
    HandleSpeciesGfxDataChange(opponent, player, TRUE);

    gFormBattleTestPlayerValue = gBattleMonForms[player];
    gFormBattleTestOpponentValue = gBattleMonForms[opponent];
    if (gFormBattleTestPlayerValue != expectedForm || gFormBattleTestOpponentValue != expectedForm)
        gFormBattleTestError |= 4;

    FormBattleTestFreezeAndPositionSprite(player, SPECIES_CASTFORM);
    FormBattleTestFreezeAndPositionSprite(opponent, SPECIES_CASTFORM);
}

static void FormBattleTestApplyUnownCase(u8 caseId, u8 player, u8 opponent)
{
    static const u8 sExpectedLetters[] = {0, 1, 25, 26, 27};
    u8 index = caseId - 5;
    u8 partyIndex = index + 1;
    struct Sprite *backSprite = &gSprites[gBattlerSpriteIds[player]];
    struct Sprite *frontSprite = &gSprites[gBattlerSpriteIds[opponent]];

    gBattlerPartyIndexes[player] = partyIndex;
    gBattlerPartyIndexes[opponent] = partyIndex;
    gBattleWeather = 0;
    gBattleMonForms[player] = 0;
    gBattleMonForms[opponent] = 0;
    gFormBattleTestMode = FORM_BATTLE_TEST_MODE_UNOWN;
    gFormBattleTestExpectedValue = sExpectedLetters[index];
    gFormBattleTestBackSpecies = SPECIES_UNOWN;
    gFormBattleTestFrontSpecies = SPECIES_UNOWN;
    gFormBattleTestBackPersonality = GetMonData(&gPlayerParty[partyIndex], MON_DATA_PERSONALITY);
    gFormBattleTestFrontPersonality = GetMonData(&gEnemyParty[partyIndex], MON_DATA_PERSONALITY);
    gFormBattleTestPlayerValue = GET_UNOWN_LETTER(gFormBattleTestBackPersonality);
    gFormBattleTestOpponentValue = GET_UNOWN_LETTER(gFormBattleTestFrontPersonality);
    gFormBattleTestPlayerResult = 0;
    gFormBattleTestOpponentResult = 0;

    if (gFormBattleTestPlayerValue != sExpectedLetters[index]
     || gFormBattleTestOpponentValue != sExpectedLetters[index])
        gFormBattleTestError |= 8;

    BattleLoadPlayerMonSpriteGfx(&gPlayerParty[partyIndex], player);
    BattleLoadOpponentMonSpriteGfx(&gEnemyParty[partyIndex], opponent);
    backSprite->anims = gAnims_MonPic;
    frontSprite->anims = gMonFrontAnimsPtrTable[SPECIES_UNOWN];
    StartSpriteAnim(backSprite, 0);
    StartSpriteAnim(frontSprite, 0);
    FormBattleTestFreezeAndPositionSprite(player, SPECIES_UNOWN);
    FormBattleTestFreezeAndPositionSprite(opponent, SPECIES_UNOWN);
}

static void FormBattleTestApplyCase(u8 caseId, u8 player, u8 opponent)
{
    gFormBattleTestCase = 0;
    if (caseId <= 4)
        FormBattleTestApplyCastformCase(caseId, player, opponent);
    else
        FormBattleTestApplyUnownCase(caseId, player, opponent);
}

static void FormBattleTestMain(void)
{
    u8 player = GetBattlerAtPosition(B_POSITION_PLAYER_LEFT);
    u8 opponent = GetBattlerAtPosition(B_POSITION_OPPONENT_LEFT);

    if (gFormBattleTestState == 2)
        return;

    if (gFormBattleTestState == 0)
    {
        if (!FormBattleTestSpritesReady(player, opponent))
        {
            sFormBattleTestWarmup = 0;
            return;
        }

        if (++sFormBattleTestWarmup < 120)
            return;

        sFormBattleTestNextCase = 1;
        sFormBattleTestCaseTimer = 0;
        FormBattleTestApplyCase(sFormBattleTestNextCase, player, opponent);
        gFormBattleTestState = 1;
        return;
    }

    sFormBattleTestCaseTimer++;
    if (sFormBattleTestCaseTimer == 12)
    {
        FormBattleTestPublishSpriteMetadata(player, opponent);
        gFormBattleTestCase = sFormBattleTestNextCase;
    }

    if (sFormBattleTestCaseTimer < 90)
        return;

    if (sFormBattleTestNextCase == FORM_BATTLE_TEST_CASE_COUNT)
    {
        gFormBattleTestState = 2;
        return;
    }

    sFormBattleTestNextCase++;
    sFormBattleTestCaseTimer = 0;
    FormBattleTestApplyCase(sFormBattleTestNextCase, player, opponent);
}

'''


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def instrument_main(text: str) -> str:
    if MAIN_MARKER in text:
        raise ValueError("src/main.c is already instrumented")

    text = _replace_once(text, '#include "battle.h"', MAIN_INCLUDES, "main include")
    text = _replace_once(
        text,
        "static void InitMainCallbacks(void);",
        MAIN_DECLARATION + "static void InitMainCallbacks(void);",
        "main declaration",
    )
    text = _replace_once(
        text,
        "static void InitMainCallbacks(void)\n{",
        MAIN_RUNTIME + "static void InitMainCallbacks(void)\n{",
        "InitMainCallbacks definition",
    )
    text = _replace_once(
        text,
        "    SetMainCallback2(CB2_InitCopyrightScreenAfterBootup);",
        "    SetMainCallback2(CB2_FormBattleTestInit);",
        "boot callback",
    )
    text = _replace_once(
        text,
        "    gSaveBlock2Ptr = &gSaveblock2.block;",
        "    gSaveBlock1Ptr = &gSaveblock1.block;\n    gSaveBlock2Ptr = &gSaveblock2.block;",
        "save block pointer",
    )
    return text


def instrument_battle_main(text: str) -> str:
    if BATTLE_MARKER in text:
        raise ValueError("src/battle_main.c is already instrumented")

    text = _replace_once(
        text,
        '#include "battle_controllers.h"',
        '#include "battle_controllers.h"\n#include "battle_gfx_sfx_util.h"',
        "battle include",
    )
    text = _replace_once(
        text,
        "EWRAM_DATA u8 gBattleMonForms[MAX_BATTLERS_COUNT] = {0};",
        "EWRAM_DATA u8 gBattleMonForms[MAX_BATTLERS_COUNT] = {0};\n\n" + BATTLE_GLOBALS,
        "battle globals",
    )
    text = _replace_once(
        text,
        "    gBattleTerrain = BattleSetup_GetTerrainId();",
        "    gBattleTerrain = BATTLE_TERRAIN_PLAIN;",
        "battle terrain",
    )
    text = _replace_once(
        text,
        "void BattleMainCB2(void)\n{",
        BATTLE_RUNTIME + "void BattleMainCB2(void)\n{",
        "BattleMainCB2 definition",
    )
    text = _replace_once(
        text,
        "    RunTasks();\n\n    if (JOY_HELD(B_BUTTON)",
        "    RunTasks();\n    FormBattleTestMain();\n\n    if (JOY_HELD(B_BUTTON)",
        "BattleMainCB2 task call",
    )
    return text


def instrument_project(project: Path, report_path: Path | None = None) -> dict[str, Any]:
    main_path = project / "src" / "main.c"
    battle_path = project / "src" / "battle_main.c"
    if not main_path.is_file() or not battle_path.is_file():
        raise FileNotFoundError("Expected src/main.c and src/battle_main.c in the game project")

    main_path.write_text(instrument_main(main_path.read_text(encoding="utf-8")), encoding="utf-8")
    battle_path.write_text(
        instrument_battle_main(battle_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    report: dict[str, Any] = {
        "version": release_version(),
        "status": "instrumented",
        "scope": "Ephemeral diagnostic ROM only; the production ROM is built and copied before instrumentation.",
        "files": ["src/main.c", "src/battle_main.c"],
        "cases": list(CASES),
    }
    if report_path is not None:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = instrument_project(args.project, args.report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
