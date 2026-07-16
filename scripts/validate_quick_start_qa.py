from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from release import release_version


EXPECTED_LABELS = ("main_menu", "gender", "name_prompt", "naming_screen", "littleroot_start")


def validate(raw_report: Path, screenshots: Path) -> dict[str, Any]:
    raw = json.loads(raw_report.read_text(encoding="utf-8"))
    samples = raw.get("samples", [])
    labels = [sample.get("label") for sample in samples]
    frames = [int(sample.get("frame", -1)) for sample in samples]
    screenshot_problems: list[str] = []
    hashes: list[str] = []

    for sample in samples:
        filename = sample.get("screenshot")
        if not isinstance(filename, str):
            screenshot_problems.append("sample has no screenshot")
            continue
        path = screenshots / filename
        if not path.exists():
            screenshot_problems.append(f"missing screenshot: {filename}")
            continue
        try:
            with Image.open(path) as image:
                if image.size != (240, 160):
                    screenshot_problems.append(f"{filename}: invalid size {image.size}")
                colors = image.convert("RGB").getcolors(maxcolors=240 * 160)
                if colors is None or len(colors) < 10:
                    screenshot_problems.append(f"{filename}: too few visible colors")
        except OSError as error:
            screenshot_problems.append(f"{filename}: {error}")
            continue
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())

    program_counters = [int(sample.get("pc", 0)) for sample in samples]
    checks = {
        "release_version_matches": raw.get("version") == release_version(),
        "emulator_reported_pass": raw.get("status") == "passed" and raw.get("crashed") is False,
        "gba_header_matches": (
            raw.get("game_title") == "POKEMON EMER"
            and raw.get("game_code") == "BPEE"
            and raw.get("rom_size") == 16 * 1024 * 1024
        ),
        "required_flow_reached": labels == list(EXPECTED_LABELS),
        "flow_order_is_strict": len(frames) == 5 and frames == sorted(set(frames)),
        "boot_reaches_menu_quickly": len(frames) == 5 and frames[0] <= 240,
        "flow_finishes_without_long_intro": int(raw.get("frames_reached", 0)) < 4000,
        "screenshots_valid": not screenshot_problems and len(hashes) == 5,
        "screenshots_are_distinct": len(set(hashes)) == 5,
        "program_counters_valid": (
            len(program_counters) == 5
            and all(
                0x02000000 <= pc <= 0x0203FFFF
                or 0x03000000 <= pc <= 0x03007FFF
                or 0x08000000 <= pc <= 0x09FFFFFF
                for pc in program_counters
            )
        ),
    }
    return {
        "version": release_version(),
        "valid": all(checks.values()),
        "checks": checks,
        "labels": labels,
        "frames": frames,
        "screenshot_sha256": hashes,
        "screenshot_problems": screenshot_problems,
        "scope": "Production-ROM QA for direct boot, compact character setup and transition into Littleroot.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.raw_report, args.screenshots)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["valid"]:
        raise SystemExit("Quick-start mGBA QA failed")


if __name__ == "__main__":
    main()
