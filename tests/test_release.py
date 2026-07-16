from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from release import release_tag, release_version  # noqa: E402


class ReleaseVersionTests(unittest.TestCase):
    def test_defaults_to_stable_v1_3_1(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(release_version(), "1.3.1")
            self.assertEqual(release_tag(), "v1.3.1")

    def test_accepts_development_version(self) -> None:
        with patch.dict(os.environ, {"EMERALD_RELEASE_VERSION": "1.4.0-dev.1"}):
            self.assertEqual(release_version(), "1.4.0-dev.1")
            self.assertEqual(release_tag(), "v1.4.0-dev.1")

    def test_rejects_unsafe_version(self) -> None:
        with patch.dict(os.environ, {"EMERALD_RELEASE_VERSION": "../../bad"}):
            with self.assertRaisesRegex(ValueError, "Invalid EMERALD_RELEASE_VERSION"):
                release_version()


if __name__ == "__main__":
    unittest.main()
