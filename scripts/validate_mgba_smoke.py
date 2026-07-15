from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image


EXPECTED_TITLE = "POKEMON EMER"
EXPECTED_GAME_CODE = "BPEE"
EXPECTED_ROM_SIZE = 16 * 1024 * 1024
EXPECTED_SCREEN_SIZE = (240, 160)
EXPECTED_TARGET_FRAMES = (120, 600, 900)


def image_entropy(image: Image.Image) -> float:
    histogram = image.convert("L").histogram()
    total = sum(histogram)
    if not total:
        return 0.0
    return -sum(
        (count / total) * math.log2(count / total)
        for count in histogram
        if count
    )


def inspect_screenshot(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        pixels = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
        colors = len(set(pixels))
        entropy = image_entropy(rgb)
        return {
            "file": path.name,
            "size": list(image.size),
            "mode": image.mode,
            "file_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "unique_colors": colors,
            "grayscale_entropy": round(entropy, 4),
            "valid": (
                image.size == EXPECTED_SCREEN_SIZE
                and len(data) >= 200
                and colors >= 8
                and entropy >= 0.5
            ),
        }


def validate(raw_report: Path, screenshots_dir: Path) -> dict[str, Any]:
    raw = json.loads(raw_report.read_text(encoding="utf-8"))
    screenshot_names = raw.get("screenshots", [])
    screenshot_results: list[dict[str, Any]] = []
    missing_screenshots: list[str] = []
    for name in screenshot_names:
        path = screenshots_dir / Path(name).name
        if not path.exists():
            missing_screenshots.append(name)
            continue
        screenshot_results.append(inspect_screenshot(path))

    frame_samples = raw.get("frame_samples", [])
    sampled_frames = [int(sample.get("frame", -1)) for sample in frame_samples]
    vram_samples = [int(sample.get("vram_nonzero_samples", 0)) for sample in frame_samples]
    program_counters = [int(sample.get("pc", 0)) for sample in frame_samples]
    screenshot_hashes = {item["sha256"] for item in screenshot_results}

    def executable_address(address: int) -> bool:
        return (
            0x02000000 <= address <= 0x0203FFFF
            or 0x03000000 <= address <= 0x03007FFF
            or 0x08000000 <= address <= 0x09FFFFFF
        )

    checks = {
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
        "video_memory_changed": len(vram_samples) == 3 and all(value > 0 for value in vram_samples),
        "program_counter_valid": len(program_counters) == 3 and all(executable_address(pc) for pc in program_counters),
        "screenshots_present": len(screenshot_results) == 3 and not missing_screenshots,
        "screenshots_rendered": len(screenshot_results) == 3 and all(item["valid"] for item in screenshot_results),
        "screenshots_changed": len(screenshot_hashes) >= 2,
    }
    return {
        "version": "1.3.1",
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
        "screenshots": screenshot_results,
        "missing_screenshots": missing_screenshots,
        "scope": (
            "Automated boot/render smoke test. Manual QA remains required for text, input flow, "
            "collisions, battles, map transitions, Surf, Waterfall and Fly."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--screenshots-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    report = validate(args.raw_report, args.screenshots_dir)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["valid"]:
        raise SystemExit("mGBA smoke validation failed")


if __name__ == "__main__":
    main()
