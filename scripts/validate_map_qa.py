from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from release import release_version


EXPECTED_CASES = (
    (1, "littleroot", 10, 12),
    (2, "oldale", 10, 10),
    (3, "route101", 9, 9),
    (4, "petalburg_woods", 18, 28),
)

PLAYER_SAMPLE_BOXES = {
    1: (104, 52, 136, 100),
    2: (56, 52, 88, 100),
    3: (104, 44, 136, 92),
    4: (86, 56, 118, 104),
}


def _has_near_color(colors: list[tuple[int, int, int]], target: tuple[int, int, int], tolerance: int = 5) -> bool:
    return any(all(abs(left - right) <= tolerance for left, right in zip(color, target)) for color in colors)


def validate(raw_report: Path, screenshots: Path) -> dict[str, object]:
    raw = json.loads(raw_report.read_text(encoding="utf-8"))
    samples = raw.get("case_samples")
    if not isinstance(samples, list):
        samples = []
    by_case = {
        sample.get("case"): sample
        for sample in samples
        if isinstance(sample, dict) and isinstance(sample.get("case"), int)
    }

    case_order = [sample.get("case") for sample in samples if isinstance(sample, dict)]
    case_metadata = True
    video_memory = True
    screenshots_valid = True
    screenshot_hashes: list[str] = []
    screenshot_records: list[dict[str, object]] = []
    program_counters = True
    player_palette_visible = True
    for case_id, name, x, y in EXPECTED_CASES:
        sample = by_case.get(case_id)
        if sample is None:
            case_metadata = False
            video_memory = False
            screenshots_valid = False
            program_counters = False
            player_palette_visible = False
            continue
        case_metadata = case_metadata and (
            sample.get("name") == name
            and sample.get("x") == x
            and sample.get("y") == y
            and isinstance(sample.get("map_group"), int)
            and isinstance(sample.get("map_num"), int)
            and int(sample.get("timer", 0)) >= 120
        )
        video_memory = video_memory and all(
            int(sample.get(field, 0)) > 0
            for field in ("vram_nonzero", "palette_nonzero", "oam_nonzero")
        )
        pc = int(sample.get("pc", 0))
        program_counters = program_counters and 0x08000000 <= pc < 0x0E000000

        filename = sample.get("screenshot")
        path = screenshots / str(filename)
        width = height = colors = 0
        digest = None
        try:
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                rgb = image.convert("RGB")
                colors = len(rgb.getcolors(maxcolors=width * height) or [])
                player_colors = [color for _, color in rgb.crop(PLAYER_SAMPLE_BOXES[case_id]).getcolors(maxcolors=4096) or []]
                player_palette_visible = player_palette_visible and (
                    _has_near_color(player_colors, (255, 198, 49))
                    and _has_near_color(player_colors, (198, 66, 66))
                )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            screenshot_hashes.append(digest)
            screenshots_valid = screenshots_valid and (width, height) == (240, 160) and colors >= 20
        except (FileNotFoundError, OSError):
            screenshots_valid = False
        screenshot_records.append({
            "case": case_id,
            "name": name,
            "file": filename,
            "width": width,
            "height": height,
            "colors": colors,
            "sha256": digest,
        })

    checks = {
        "release_version_matches": raw.get("version") == release_version(),
        "emulator_reported_pass": raw.get("status") == "passed" and raw.get("crashed") is False,
        "gba_header_matches": (
            raw.get("game_title") == "POKEMON EMER"
            and raw.get("game_code") == "BPEE"
            and raw.get("rom_size") == 16 * 1024 * 1024
        ),
        "map_harness_completed": raw.get("final_state") == 2 and raw.get("final_error") == 0,
        "case_order_matches": case_order == [1, 2, 3, 4],
        "case_metadata_matches": case_metadata,
        "video_memory_populated": video_memory,
        "map_video_signatures_are_distinct": (
            len(samples) == 4
            and len({sample.get("vram_signature") for sample in samples if isinstance(sample, dict)}) == 4
        ),
        "screenshots_are_valid": screenshots_valid,
        "screenshots_are_distinct": len(screenshot_hashes) == 4 and len(set(screenshot_hashes)) == 4,
        "brendan_v14_palette_visible": player_palette_visible,
        "program_counter_valid": program_counters,
    }
    return {
        "version": release_version(),
        "valid": all(checks.values()),
        "checks": checks,
        "coverage": {
            "maps": [name for _, name, _, _ in EXPECTED_CASES],
            "runtime": "Native map loading, tileset callbacks, VRAM, palettes, OAM and screenshots in mGBA.",
            "geometry": "Collision attributes, blockdata and borders are checked separately as byte-identical.",
        },
        "emulator": {
            "frames_reached": raw.get("frames_reached"),
            "samples": samples,
            "screenshots": screenshot_records,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.raw_report, args.screenshots)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"version": report["version"], "valid": report["valid"], "checks": report["checks"]}, indent=2))
    if not report["valid"]:
        raise SystemExit("mGBA map QA validation failed")


if __name__ == "__main__":
    main()
