from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release import release_version


EXPECTED_TITLE = "POKEMON EMER"
EXPECTED_GAME_CODE = "BPEE"
EXPECTED_ROM_SIZE = 16 * 1024 * 1024
SPECIES_UNOWN = 201
SPECIES_CASTFORM = 385

CASTFORM_CASES = (
    {"case": 1, "name": "sunny", "form": 1, "weather": 1 << 5},
    {"case": 2, "name": "rainy", "form": 2, "weather": 1 << 0},
    {"case": 3, "name": "snowy", "form": 3, "weather": 1 << 7},
    {"case": 4, "name": "normal", "form": 0, "weather": 0},
)
UNOWN_CASES = (
    {"case": 5, "name": "A", "letter": 0},
    {"case": 6, "name": "B", "letter": 1},
    {"case": 7, "name": "Z", "letter": 25},
    {"case": 8, "name": "!", "letter": 26},
    {"case": 9, "name": "?", "letter": 27},
)


def unown_letter(personality: int) -> int:
    return (
        ((personality & 0x03000000) >> 18)
        | ((personality & 0x00030000) >> 12)
        | ((personality & 0x00000300) >> 6)
        | (personality & 0x00000003)
    ) % 28


def _sample_map(raw: dict[str, Any]) -> dict[int, dict[str, Any]]:
    samples = raw.get("case_samples", [])
    result: dict[int, dict[str, Any]] = {}
    for sample in samples:
        case_id = int(sample.get("case", -1))
        if case_id in result:
            return {}
        result[case_id] = sample
    return result


def _executable_address(address: int) -> bool:
    return (
        0x02000000 <= address <= 0x0203FFFF
        or 0x03000000 <= address <= 0x03007FFF
        or 0x08000000 <= address <= 0x09FFFFFF
    )


def validate(raw_report: Path) -> dict[str, Any]:
    raw = json.loads(raw_report.read_text(encoding="utf-8"))
    samples = _sample_map(raw)
    ordered = [samples.get(case_id, {}) for case_id in range(1, 10)]

    castform_selection = True
    for expected in CASTFORM_CASES:
        sample = samples.get(expected["case"], {})
        castform_selection &= (
            int(sample.get("mode", -1)) == 1
            and int(sample.get("expected_value", -1)) == expected["form"]
            and int(sample.get("player_value", -1)) == expected["form"]
            and int(sample.get("opponent_value", -1)) == expected["form"]
            and int(sample.get("player_form", -1)) == expected["form"]
            and int(sample.get("opponent_form", -1)) == expected["form"]
            and int(sample.get("player_result", -1)) == expected["form"] + 1
            and int(sample.get("opponent_result", -1)) == expected["form"] + 1
            and int(sample.get("weather", -1)) == expected["weather"]
            and int(sample.get("back_species", -1)) == SPECIES_CASTFORM
            and int(sample.get("front_species", -1)) == SPECIES_CASTFORM
        )

    unown_personality_selection = True
    for expected in UNOWN_CASES:
        sample = samples.get(expected["case"], {})
        back_personality = int(sample.get("back_personality", -1))
        front_personality = int(sample.get("front_personality", -1))
        unown_personality_selection &= (
            int(sample.get("mode", -1)) == 2
            and int(sample.get("expected_value", -1)) == expected["letter"]
            and int(sample.get("player_value", -1)) == expected["letter"]
            and int(sample.get("opponent_value", -1)) == expected["letter"]
            and back_personality >= 0
            and front_personality >= 0
            and unown_letter(back_personality) == expected["letter"]
            and unown_letter(front_personality) == expected["letter"]
            and int(sample.get("back_species", -1)) == SPECIES_UNOWN
            and int(sample.get("front_species", -1)) == SPECIES_UNOWN
        )

    back_tile_signatures = [int(sample.get("back_tiles_signature", 0)) for sample in ordered]
    front_tile_signatures = [int(sample.get("front_tiles_signature", 0)) for sample in ordered]
    back_palette_signatures = [int(sample.get("back_palette_signature", 0)) for sample in ordered]
    front_palette_signatures = [int(sample.get("front_palette_signature", 0)) for sample in ordered]

    video_memory_populated = len(samples) == 9 and all(
        int(sample.get(field, 0)) > 0
        for sample in ordered
        for field in (
            "back_tiles_nonzero",
            "front_tiles_nonzero",
            "back_palette_nonzero",
            "front_palette_nonzero",
        )
    )
    distinct_front_and_back_forms = (
        len(samples) == 9
        and len(set(back_tile_signatures)) == 9
        and len(set(front_tile_signatures)) == 9
    )
    palette_policy_matches = (
        len(samples) == 9
        and len(set(back_palette_signatures[:4])) == 4
        and len(set(front_palette_signatures[:4])) == 4
        and len(set(back_palette_signatures[4:])) == 1
        and len(set(front_palette_signatures[4:])) == 1
    )
    harness_clean = (
        int(raw.get("final_error", -1)) == 0
        and all(int(sample.get("error", -1)) == 0 for sample in ordered)
    )
    pcs = [int(sample.get("pc", 0)) for sample in ordered]

    checks = {
        "release_version_matches": raw.get("version") == release_version(),
        "emulator_reported_pass": raw.get("status") == "passed" and raw.get("crashed") is False,
        "gba_header_matches": (
            raw.get("game_title") == EXPECTED_TITLE
            and raw.get("game_code") == EXPECTED_GAME_CODE
            and int(raw.get("rom_size", 0)) == EXPECTED_ROM_SIZE
        ),
        "battle_harness_completed": int(raw.get("final_state", -1)) == 2 and set(samples) == set(range(1, 10)),
        "harness_reported_no_errors": harness_clean,
        "castform_weather_selection": bool(castform_selection),
        "unown_personality_selection": bool(unown_personality_selection),
        "front_and_back_video_memory_populated": video_memory_populated,
        "front_and_back_forms_are_distinct": distinct_front_and_back_forms,
        "palette_policy_matches": palette_policy_matches,
        "program_counter_valid": len(pcs) == 9 and all(_executable_address(pc) for pc in pcs),
    }

    return {
        "version": release_version(),
        "valid": all(checks.values()),
        "checks": checks,
        "coverage": {
            "battle_context": "Single wild battle with both player/back and opponent/front battler sprites visible.",
            "castform": [item["name"] for item in CASTFORM_CASES],
            "unown": [item["name"] for item in UNOWN_CASES],
            "rendering": "Per-battler 2 KiB OBJ tile data and 16-color OBJ palettes sampled from mGBA memory.",
        },
        "emulator": {
            "frames_reached": raw.get("frames_reached"),
            "case_samples": ordered,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    report = validate(args.raw_report)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["valid"]:
        raise SystemExit("mGBA form battle validation failed")


if __name__ == "__main__":
    main()
