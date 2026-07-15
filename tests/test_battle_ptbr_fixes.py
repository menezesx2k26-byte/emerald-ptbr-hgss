from __future__ import annotations

import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from apply_battle_ptbr_fixes import (  # noqa: E402
    BATTLE_C_FIXES,
    ROUTE101_FIXES,
    STARTER_CATEGORY_FIXES,
    CFix,
    apply_all,
    apply_c_fix,
    placeholder_multiset,
)


class BattlePtbrFixTests(unittest.TestCase):
    def build_project(self, root: Path) -> None:
        by_c_file: dict[str, list[CFix]] = defaultdict(list)
        for fix in BATTLE_C_FIXES:
            by_c_file[fix.path].append(fix)

        for relative, fixes in by_c_file.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            declarations = []
            for fix in fixes:
                prefix = "static " if fix.label.startswith("sText_") else ""
                declarations.append(
                    f'{prefix}const u8 {fix.label}[] = _("{fix.text}");'
                )
            path.write_text("\n".join(declarations) + "\n", encoding="utf-8")

        by_assembly_file = defaultdict(list)
        for fix in ROUTE101_FIXES:
            by_assembly_file[fix.path].append(fix)
        for relative, fixes in by_assembly_file.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            blocks = []
            for fix in fixes:
                body = "".join(f'\t.string "{line}"\n' for line in fix.lines)
                blocks.append(f"{fix.label}:\n{body}")
            path.write_text("\n".join(blocks), encoding="utf-8")

        categories = root / "src/data/pokemon/pokedex_entries.h"
        categories.parent.mkdir(parents=True, exist_ok=True)
        categories.write_text(
            "\n".join(
                f'[{fix.species}] =\n{{\n    .categoryName = _("ENGLISH"),\n}},'
                for fix in STARTER_CATEGORY_FIXES
            )
            + "\n",
            encoding="utf-8",
        )

    def test_applies_complete_first_battle_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.build_project(project)

            report = apply_all(project)

            expected = len(BATTLE_C_FIXES) + len(ROUTE101_FIXES) + len(STARTER_CATEGORY_FIXES)
            self.assertEqual(len(report), expected)
            battle = (project / "src/battle_message.c").read_text(encoding="utf-8")
            route = (project / "data/maps/Route101/scripts.inc").read_text(encoding="utf-8")
            categories = (project / "src/data/pokemon/pokedex_entries.h").read_text(encoding="utf-8")

            self.assertIn("LUTAR{CLEAR_TO 56}MOCHILA", battle)
            self.assertIn("{B_ATK_NAME_WITH_PREFIX} usou", battle)
            self.assertIn("{B_BUFF1} recebeu{B_BUFF2}", battle)
            self.assertIn("A-ajude-me!", route)
            self.assertIn("PROF. BIRCH: Ufa...", route)
            self.assertIn('.categoryName = _("PINTINHO")', categories)
            self.assertIn('.categoryName = _("PEIXE DE LAMA")', categories)

    def test_all_replacements_preserve_control_placeholders(self) -> None:
        for fix in BATTLE_C_FIXES:
            self.assertEqual(placeholder_multiset(fix.text), placeholder_multiset(fix.text))
        for fix in ROUTE101_FIXES:
            raw = "".join(fix.lines)
            self.assertTrue(raw.endswith("$"), fix.label)

    def test_rejects_placeholder_loss(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = project / "src/battle_message.c"
            path.parent.mkdir(parents=True)
            path.write_text(
                'static const u8 sText_Test[] = _("{B_CURRENT_MOVE} used!");\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "Placeholder mismatch"):
                apply_c_fix(project, CFix("src/battle_message.c", "sText_Test", "Golpe usado!"))

    def test_move_names_and_descriptions_are_not_touched(self) -> None:
        touched = {fix.path for fix in BATTLE_C_FIXES}
        touched.update(fix.path for fix in ROUTE101_FIXES)
        self.assertNotIn("src/data/text/move_names.h", touched)
        self.assertNotIn("src/data/text/move_descriptions.h", touched)
        self.assertTrue(any("{B_BUFF2}" in fix.text for fix in BATTLE_C_FIXES))
        self.assertTrue(any("{B_CURRENT_MOVE}" in fix.text for fix in BATTLE_C_FIXES))


if __name__ == "__main__":
    unittest.main()
