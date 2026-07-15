from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from apply_manual_ptbr_fixes import FIXES, Fix, apply_fix, placeholder_multiset  # noqa: E402


class ManualPtbrFixesTests(unittest.TestCase):
    def test_reviewed_fix_manifest_is_complete_and_unique(self) -> None:
        identities = {(fix.path, fix.label) for fix in FIXES}
        self.assertEqual(len(FIXES), 15)
        self.assertEqual(len(identities), len(FIXES))
        self.assertTrue(any("DYNAMICPUNCH" in "".join(fix.lines) for fix in FIXES))
        self.assertTrue(any("PROTECT" in "".join(fix.lines) for fix in FIXES))

    def test_all_replacements_are_encoded_strings_with_terminators(self) -> None:
        for fix in FIXES:
            raw = "".join(fix.lines)
            self.assertTrue(raw.endswith("$"), fix.label)
            self.assertNotIn('"', raw, fix.label)
            self.assertNotIn("\n", raw, fix.label)
            for line in re.split(r"\\[nlp]", raw.rstrip("$")):
                visible = re.sub(r"\{[^{}]+\}", "", line)
                self.assertLessEqual(len(visible), 29, f"{fix.label}: {visible}")

    def test_apply_fix_preserves_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            relative = "data/text/example.inc"
            path = project / relative
            path.parent.mkdir(parents=True)
            path.write_text(
                'Example_Label::\n\t.string "Hello {STR_VAR_1}!$"\n',
                encoding="utf-8",
            )
            fix = Fix(relative, "Example_Label", (r"Olá, {STR_VAR_1}!$",))
            result = apply_fix(project, fix)
            self.assertEqual(result["label"], "Example_Label")
            self.assertIn("Olá", path.read_text(encoding="utf-8"))
            self.assertEqual(placeholder_multiset("".join(fix.lines))["{STR_VAR_1}"], 1)

    def test_apply_fix_rejects_placeholder_loss(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            relative = "data/text/example.inc"
            path = project / relative
            path.parent.mkdir(parents=True)
            path.write_text(
                'Example_Label::\n\t.string "Hello {STR_VAR_1}!$"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "Placeholder mismatch"):
                apply_fix(project, Fix(relative, "Example_Label", (r"Olá!$",)))


if __name__ == "__main__":
    unittest.main()
