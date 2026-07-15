from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from apply_manual_ptbr_fixes import (  # noqa: E402
    C_FIXES,
    FIXES,
    CFix,
    Fix,
    apply_c_fix,
    apply_fix,
    placeholder_multiset,
)


CORE_UI_ORIGINALS = {
    "gText_MainMenuOption": "OPÇöES",
    "gText_MenuBag": "BAG",
    "gText_MenuSave": "SAVE",
    "gText_MenuOption": "OPTION",
    "gText_MenuExit": "EXIT",
    "gText_MenuRetire": "RETIRE",
    "gText_MenuRest": "REST",
    "gText_YourName": "YOUR NAME?",
    "gText_MoveOkBack": r"{DPAD_NONE}MOVE  {A_BUTTON}OK  {B_BUTTON}BACK",
    "gText_IsThisTheCorrectTime": "Is this the correct time?",
    "gText_Confirm3": "CONFIRM",
    "gText_Cancel4": "CANCEL",
    "gText_ContinueMenuTime": "TIME",
    "gText_ContinueMenuBadges": "BADGES",
}


class ManualPtbrFixesTests(unittest.TestCase):
    def test_reviewed_fix_manifests_are_complete_and_unique(self) -> None:
        identities = {(fix.path, fix.label) for fix in FIXES}
        ui_identities = {(fix.path, fix.label) for fix in C_FIXES}
        self.assertEqual(len(FIXES), 15)
        self.assertEqual(len(C_FIXES), 14)
        self.assertEqual(len(identities), len(FIXES))
        self.assertEqual(len(ui_identities), len(C_FIXES))
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

    def test_replaces_all_reviewed_core_ui_strings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "src").mkdir()
            strings = project / "src/strings.c"
            strings.write_text(
                "\n".join(
                    f'const u8 {fix.label}[] = _("{CORE_UI_ORIGINALS[fix.label]}");'
                    for fix in C_FIXES
                )
                + "\n",
                encoding="utf-8",
            )

            reports = [apply_c_fix(project, fix) for fix in C_FIXES]
            updated = strings.read_text(encoding="utf-8")

            self.assertTrue(all(report["kind"] == "c_string" for report in reports))
            for fix in C_FIXES:
                self.assertIn(f'const u8 {fix.label}[] = _("{fix.text}");', updated)

    def test_apply_c_fix_rejects_control_code_loss(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "src").mkdir()
            (project / "src/strings.c").write_text(
                'const u8 gText_Test[] = _("{A_BUTTON}OK {B_BUTTON}BACK");\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "Placeholder mismatch"):
                apply_c_fix(project, CFix("src/strings.c", "gText_Test", "OK"))

    def test_move_tables_are_not_part_of_core_ui_fixes(self) -> None:
        self.assertTrue(all("move_names" not in fix.path for fix in C_FIXES))
        self.assertTrue(all("move_descriptions" not in fix.path for fix in C_FIXES))


if __name__ == "__main__":
    unittest.main()
