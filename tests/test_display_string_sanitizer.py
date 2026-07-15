from __future__ import annotations

import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from sanitize_display_quotes import (  # noqa: E402
    CORE_UI_REPLACEMENTS,
    P1_ASSEMBLY_REPLACEMENTS,
    normalize_core_ui_strings,
    normalize_p1_assembly_strings,
    replace_quotes,
)


class DisplayStringSanitizerTests(unittest.TestCase):
    def test_replaces_escaped_display_quotes(self) -> None:
        updated, count = replace_quotes(r'Ele disse: \"sim\".')
        self.assertEqual(updated, 'Ele disse: “sim”.')
        self.assertEqual(count, 2)

    def test_normalizes_shared_ui_and_relationship_strings(self) -> None:
        originals = {
            "gText_YesNo": r"YES\nNO",
            "gText_Yes": "SIM",
            "gText_No": "NäO",
            "gText_No4": "NäO",
            "gText_Daughter": "daughter",
            "gText_Son": "son",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "strings.c"
            path.write_text(
                "\n".join(
                    f'const u8 {label}[] = _("{value}");'
                    for label, value in originals.items()
                )
                + "\n",
                encoding="utf-8",
            )

            report = normalize_core_ui_strings(path)
            updated = path.read_text(encoding="utf-8")

            self.assertEqual(len(report), len(CORE_UI_REPLACEMENTS))
            self.assertIn(r'const u8 gText_YesNo[] = _("SIM\nNÃO");', updated)
            self.assertIn('const u8 gText_No[] = _("NÃO");', updated)
            self.assertIn('const u8 gText_Daughter[] = _("nossa filha");', updated)
            self.assertIn('const u8 gText_Son[] = _("nosso filho");', updated)

    def test_normalizes_all_reviewed_littleroot_blocks(self) -> None:
        by_file: dict[str, list[tuple[str, tuple[str, ...]]]] = defaultdict(list)
        for relative, label, replacement in P1_ASSEMBLY_REPLACEMENTS:
            by_file[relative].append((label, replacement))

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for relative, blocks in by_file.items():
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                source_blocks = []
                for label, replacement in blocks:
                    raw = "".join(replacement)
                    rough = (
                        raw.replace("MÃE", "MäE")
                        .replace("REPÓRTER", "INTERVIEWER")
                        .replace("Transmitimos", "Trouxemos")
                        .replace("nossa filha", "daughter")
                    )
                    source_blocks.append(f'{label}:\n\t.string "{rough}"\n')
                path.write_text("\n".join(source_blocks), encoding="utf-8")

            report = normalize_p1_assembly_strings(project)

            self.assertEqual(len(report), len(P1_ASSEMBLY_REPLACEMENTS))
            for relative, label, replacement in P1_ASSEMBLY_REPLACEMENTS:
                updated = (project / relative).read_text(encoding="utf-8")
                self.assertIn(f"{label}:", updated)
                for line in replacement:
                    self.assertIn(f'\t.string "{line}"', updated)
            bedroom = (project / P1_ASSEMBLY_REPLACEMENTS[0][0]).read_text(encoding="utf-8")
            television = (project / P1_ASSEMBLY_REPLACEMENTS[1][0]).read_text(encoding="utf-8")
            rival_house = (project / P1_ASSEMBLY_REPLACEMENTS[-1][0]).read_text(encoding="utf-8")
            self.assertIn("MÃE: {JOGADOR}, gostou do seu", bedroom)
            self.assertIn("REPÓRTER: ...Transmitimos esta", television)
            self.assertNotIn("INTERVIEWER", television)
            self.assertIn("{STR_VAR_1} mora aqui e tem", rival_house)
            self.assertEqual(rival_house.count("{STR_VAR_1}"), 3)

    def test_move_tables_are_outside_display_normalization(self) -> None:
        self.assertTrue(all("Move" not in label for label in CORE_UI_REPLACEMENTS))
        self.assertTrue(all("move_names" not in path for path, _, _ in P1_ASSEMBLY_REPLACEMENTS))
        self.assertTrue(all("move_descriptions" not in path for path, _, _ in P1_ASSEMBLY_REPLACEMENTS))


if __name__ == "__main__":
    unittest.main()
