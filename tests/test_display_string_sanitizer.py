from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from sanitize_display_quotes import (  # noqa: E402
    CORE_UI_REPLACEMENTS,
    normalize_core_ui_strings,
    replace_quotes,
)


class DisplayStringSanitizerTests(unittest.TestCase):
    def test_replaces_escaped_display_quotes(self) -> None:
        updated, count = replace_quotes(r'Ele disse: \"sim\".')
        self.assertEqual(updated, 'Ele disse: “sim”.')
        self.assertEqual(count, 2)

    def test_normalizes_shared_yes_no_strings(self) -> None:
        originals = {
            "gText_YesNo": r"YES\nNO",
            "gText_Yes": "SIM",
            "gText_No": "NäO",
            "gText_No4": "NäO",
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
            self.assertIn('const u8 gText_No4[] = _("NÃO");', updated)

    def test_move_tables_are_outside_display_normalization(self) -> None:
        self.assertTrue(all("Move" not in label for label in CORE_UI_REPLACEMENTS))


if __name__ == "__main__":
    unittest.main()
