from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from release import release_version

EXPECTED_TITLE = "POKEMON EMER"
EXPECTED_GAME_CODE = "BPEE"
EXPECTED_ROM_SIZE = 16 * 1024 * 1024
EXPECTED_TARGET_FRAMES = (5, 120, 900)


def validate(raw_report: Path) -> dict[str, Any]:
    raw = json.loads(raw_report.read_text(encoding="utf-8"))
    frame_samples = raw.get("frame_samples", [])
    sampled_frames = [int(sample.get("frame", -1)) for sample in frame_samples]
    vram_samples = [int(sample.get("vram_nonzero_samples", 0)) for sample in frame_samples]
    palette_samples = [int(sample.get("palette_nonzero_samples", 0)) for sample in frame_samples]
    video_signatures = [
        (
            int(sample.get("vram_signature", 0)),
            int(sample.get("palette_signature", 0)),
            int(sample.get("oam_signature", 0)),
        )
        for sample in frame_samples
    ]
    program_counters = [int(sample.get("pc", 0)) for sample in frame_samples]

    def executable_address(address: int) -> bool:
        return (
            0x02000000 <= address <= 0x0203FFFF
            or 0x03000000 <= address <= 0x03007FFF
            or 0x08000000 <= address <= 0x09FFFFFF
        )

    checks = {
        "release_version_matches": raw.get("version") == release_version(),
        "emulator_reported_pass": raw.get("status") == "passed" and raw.get("crashed") is False,
        "gba_header_matches": (
            raw.get("game_title") == EXPECTED_TITLE
            and raw.get("game_code") == EXPECTED_GAME_CODE
            and raw.get("rom_size") == EXPECTED_ROM_SIZE
        ),
        "target_frames_reached": (
            int(raw.get("frames_reached", 0)) >= EXPECTED_TARGET_FRAMES[-1]
            and len(sampled_frames) == len(EXPECTED_TARGET_FRAMES)
            and all(actual >= expected for actual, expected in zip(sampled_frames, EXPECTED_TARGET_FRAMES))
        ),
        "video_memory_initialized": (
            len(vram_samples) == len(EXPECTED_TARGET_FRAMES)
            and all(value > 0 for value in vram_samples)
            and all(value > 0 for value in palette_samples)
        ),
        "video_memory_changed": (
            len(video_signatures) == len(EXPECTED_TARGET_FRAMES)
            and len(set(video_signatures)) >= 2
        ),
        "program_counter_valid": len(program_counters) == 3 and all(executable_address(pc) for pc in program_counters),
    }
    return {
        "version": release_version(),
        "valid": all(checks.values()),
        "checks": checks,
        "emulator": {
            "game_title": raw.get("game_title"),
            "game_code": raw.get("game_code"),
            "rom_size": raw.get("rom_size"),
            "platform": raw.get("platform"),
            "frames_reached": raw.get("frames_reached"),
            "frame_samples": frame_samples,
        },
        "scope": (
            "Automated headless boot and video-memory smoke test. Manual visual QA remains required for text, input flow, "
            "collisions, battles, map transitions, Surf, Waterfall and Fly."
        ),
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
        raise SystemExit("mGBA smoke validation failed")


if __name__ == "__main__":
    main()
