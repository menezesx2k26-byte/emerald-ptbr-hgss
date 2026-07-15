from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


NINTENDO_LOGO_SHA256 = "08a0153cfd6b0ea54b938f7d209933fa849da0d56f5a34c481060c9ff2fad818"
EXPECTED_SIZE = 16 * 1024 * 1024


def decode_header_field(data: bytes) -> str:
    return data.rstrip(b"\0 ").decode("ascii", errors="replace")


def validate(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    calculated_checksum = (-(sum(data[0xA0:0xBD]) + 0x19)) & 0xFF if len(data) >= 0xBE else None
    stored_checksum = data[0xBD] if len(data) >= 0xBE else None
    logo_sha256 = hashlib.sha256(data[0x04:0xA0]).hexdigest() if len(data) >= 0xA0 else None
    checks = {
        "size_is_16_mib": len(data) == EXPECTED_SIZE,
        "title_is_pokemon_emer": data[0xA0:0xAC] == b"POKEMON EMER",
        "game_code_is_bpee": data[0xAC:0xB0] == b"BPEE",
        "maker_code_is_01": data[0xB0:0xB2] == b"01",
        "fixed_header_byte_is_96": len(data) > 0xB2 and data[0xB2] == 0x96,
        "nintendo_logo_is_valid": logo_sha256 == NINTENDO_LOGO_SHA256,
        "header_checksum_is_valid": calculated_checksum == stored_checksum,
    }
    return {
        "version": "1.3.1",
        "file": path.name,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header": {
            "title": decode_header_field(data[0xA0:0xAC]),
            "game_code": decode_header_field(data[0xAC:0xB0]),
            "maker_code": decode_header_field(data[0xB0:0xB2]),
            "version": data[0xBC] if len(data) > 0xBC else None,
            "stored_checksum": stored_checksum,
            "calculated_checksum": calculated_checksum,
            "nintendo_logo_sha256": logo_sha256,
        },
        "checks": checks,
        "valid": all(checks.values()),
        "scope": "Structural GBA ROM validation; emulator playtesting is still required for gameplay and visual QA.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.rom)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["valid"]:
        raise SystemExit("ROM validation failed")


if __name__ == "__main__":
    main()
