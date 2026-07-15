from __future__ import annotations

import argparse
import base64
from pathlib import Path

from PIL import Image

from validate_map_qa import EXPECTED_CASES


def compose(screenshots: Path, output: Path) -> Path:
    sheet = Image.new("RGB", (480, 320))
    for index, (case_id, name, _, _) in enumerate(EXPECTED_CASES):
        path = screenshots / f"map_qa_{case_id}_{name}.png"
        with Image.open(path) as source:
            image = source.convert("RGB")
            if image.size != (240, 160):
                raise ValueError(f"Unexpected screenshot size for {path}: {image.size}")
            sheet.paste(image, ((index % 2) * 240, (index // 2) * 160))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--emit-base64", action="store_true")
    args = parser.parse_args()
    output = compose(args.screenshots.resolve(), args.output.resolve())
    if args.emit_base64:
        print("MAP_QA_CONTACT_SHEET_BASE64_BEGIN")
        print(base64.b64encode(output.read_bytes()).decode("ascii"))
        print("MAP_QA_CONTACT_SHEET_BASE64_END")


if __name__ == "__main__":
    main()
