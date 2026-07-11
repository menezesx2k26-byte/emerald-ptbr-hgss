#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from maps import apply_map_overhaul
from overworlds import import_overworld_sprites
from sprites import import_hgss_sprites
from water import apply_water_overhaul


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--sprites-root", type=Path, required=True)
    parser.add_argument("--overworlds-root", type=Path, required=True)
    args = parser.parse_args()

    project = args.project.resolve()
    if not (project / "Makefile").exists():
        raise FileNotFoundError(project)

    apply_water_overhaul(project)
    apply_map_overhaul(project)
    import_hgss_sprites(project, args.sprites_root.resolve())
    import_overworld_sprites(project, args.overworlds_root.resolve())
    print("Visual overhaul v1.3 applied successfully")


if __name__ == "__main__":
    main()
