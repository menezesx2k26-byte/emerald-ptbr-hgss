from __future__ import annotations

import argparse
import json
from pathlib import Path

from release import release_version


MAIN_MARKER = "/* MAP_QA_MAIN_INSTRUMENTATION */"
OVERWORLD_MARKER = "/* MAP_QA_OVERWORLD_INSTRUMENTATION */"

MAIN_DECLARATION = f'''{MAIN_MARKER}
void CB2_MapQaInit(void);
'''

OVERWORLD_INCLUDE = '''#include "overworld.h"
#include "constants/maps.h"'''

OVERWORLD_GLOBALS = f'''{OVERWORLD_MARKER}
EWRAM_DATA u8 gMapQaState = 0;
EWRAM_DATA u8 gMapQaCase = 0;
EWRAM_DATA u8 gMapQaReady = 0;
EWRAM_DATA u8 gMapQaAdvance = 0;
EWRAM_DATA u8 gMapQaError = 0;
EWRAM_DATA u8 gMapQaMapGroup = 0;
EWRAM_DATA u8 gMapQaMapNum = 0;
EWRAM_DATA s8 gMapQaX = 0;
EWRAM_DATA s8 gMapQaY = 0;
EWRAM_DATA u16 gMapQaTimer = 0;
'''

OVERWORLD_RUNTIME = '''/* MAP_QA_OVERWORLD_RUNTIME */
#define MAP_QA_CASE_COUNT 4

struct MapQaWarp
{
    s8 group;
    s8 map;
    s8 x;
    s8 y;
};

static const struct MapQaWarp sMapQaWarps[] =
{
    {MAP_GROUP(LITTLEROOT_TOWN), MAP_NUM(LITTLEROOT_TOWN), 10, 12},
    {MAP_GROUP(OLDALE_TOWN), MAP_NUM(OLDALE_TOWN), 10, 10},
    {MAP_GROUP(ROUTE101), MAP_NUM(ROUTE101), 9, 9},
    {MAP_GROUP(PETALBURG_WOODS), MAP_NUM(PETALBURG_WOODS), 18, 28},
};

static void MapQaLoadCase(u8 caseId)
{
    const struct MapQaWarp *warp = &sMapQaWarps[caseId - 1];

    gMapQaCase = caseId;
    gMapQaReady = FALSE;
    gMapQaAdvance = FALSE;
    gMapQaTimer = 0;
    gMapQaMapGroup = warp->group;
    gMapQaMapNum = warp->map;
    gMapQaX = warp->x;
    gMapQaY = warp->y;
    SetWarpDestination(warp->group, warp->map, WARP_ID_NONE, warp->x, warp->y);
    WarpIntoMap();
    SetMainCallback2(CB2_LoadMap);
}

void CB2_MapQaInit(void)
{
    NewGameInitData();
    gMapQaState = 1;
    gMapQaError = 0;
    MapQaLoadCase(1);
}

static void MapQaStep(void)
{
    if (gMapQaState != 1 || gPaletteFade.active)
        return;

    if (gMapQaTimer < 0xFFFF)
        gMapQaTimer++;
    if (gMapQaTimer >= 120)
        gMapQaReady = TRUE;

    if (!gMapQaAdvance)
        return;
    if (!gMapQaReady)
    {
        gMapQaError = 1;
        gMapQaState = 3;
        return;
    }
    if (gMapQaCase >= MAP_QA_CASE_COUNT)
    {
        gMapQaState = 2;
        gMapQaReady = FALSE;
        gMapQaAdvance = FALSE;
        return;
    }
    MapQaLoadCase(gMapQaCase + 1);
}

'''

CASES = (
    {"case": 1, "name": "littleroot", "map": "LITTLEROOT_TOWN", "x": 10, "y": 12},
    {"case": 2, "name": "oldale", "map": "OLDALE_TOWN", "x": 10, "y": 10},
    {"case": 3, "name": "route101", "map": "ROUTE101", "x": 9, "y": 9},
    {"case": 4, "name": "petalburg_woods", "map": "PETALBURG_WOODS", "x": 18, "y": 28},
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def replace_boot_callback(text: str, callback: str) -> str:
    anchors = (
        "    SetMainCallback2(CB2_InitMainMenu); /* V14_QUICK_START */",
        "    SetMainCallback2(CB2_InitCopyrightScreenAfterBootup);",
    )
    matches = [anchor for anchor in anchors if anchor in text]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one boot callback anchor, found {len(matches)}")
    return text.replace(matches[0], f"    SetMainCallback2({callback});", 1)


def instrument_main(text: str) -> str:
    if MAIN_MARKER in text:
        raise ValueError("src/main.c is already instrumented for map QA")
    text = replace_once(
        text,
        "static void InitMainCallbacks(void);",
        MAIN_DECLARATION + "static void InitMainCallbacks(void);",
        "main declaration",
    )
    text = replace_boot_callback(text, "CB2_MapQaInit")
    text = replace_once(
        text,
        "    gSaveBlock2Ptr = &gSaveblock2.block;",
        "    gSaveBlock1Ptr = &gSaveblock1.block;\n    gSaveBlock2Ptr = &gSaveblock2.block;",
        "save block initialization",
    )
    return text


def instrument_overworld(text: str) -> str:
    if OVERWORLD_MARKER in text:
        raise ValueError("src/overworld.c is already instrumented for map QA")
    text = replace_once(text, '#include "overworld.h"', OVERWORLD_INCLUDE, "overworld include")
    text = replace_once(
        text,
        "COMMON_DATA u16 *gOverworldTilemapBuffer_Bg2 = NULL;",
        OVERWORLD_GLOBALS + "\nCOMMON_DATA u16 *gOverworldTilemapBuffer_Bg2 = NULL;",
        "overworld globals",
    )
    text = replace_once(
        text,
        "void CB2_OverworldBasic(void)\n{",
        OVERWORLD_RUNTIME + "void CB2_OverworldBasic(void)\n{",
        "overworld runtime",
    )
    text = replace_once(
        text,
        "    OverworldBasic();\n    if (fading)",
        "    OverworldBasic();\n    MapQaStep();\n    if (fading)",
        "overworld frame hook",
    )
    return text


def instrument_project(project: Path) -> dict[str, object]:
    main_path = project / "src/main.c"
    overworld_path = project / "src/overworld.c"
    main_path.write_text(instrument_main(main_path.read_text(encoding="utf-8")), encoding="utf-8")
    overworld_path.write_text(
        instrument_overworld(overworld_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return {
        "version": release_version(),
        "scope": "Ephemeral in-emulator QA harness for the four v1.4 pilot maps.",
        "cases": CASES,
        "production_rom_policy": "The playable ROM is copied and checksummed before instrumentation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = instrument_project(args.project.resolve())
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
