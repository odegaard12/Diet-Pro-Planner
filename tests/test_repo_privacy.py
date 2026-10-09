import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_repo_privacy", Path(__file__).resolve().parents[1] / "scripts" / "check_repo_privacy.py"
)
privacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(privacy)


class RepoPrivacyTest(unittest.TestCase):
    def test_flags_personal_details_without_echoing_them(self):
        # Built by concatenation so this file itself passes the check.
        text = "host=" + "192.168" + ".0.5\nlog /home/" + "someone/app\nactivity 1" + "8123456789\n"
        problems = privacy.content_problems("x.md", text)
        self.assertEqual(len(problems), 3)
        self.assertFalse(any("192" in p or "someone" in p for p in problems))

    def test_allows_examples_and_ordinary_numbers(self):
        text = "DPP_AI_BASE_URL=http://" + "192.168.1.10" + ":11434/v1\nkcal 2307.0 at 127.0.0.1, ts 1700000000\n"
        self.assertEqual(privacy.content_problems("x.md", text), [])

    def test_private_named_files_are_forbidden(self):
        self.assertTrue(privacy.is_forbidden("scripts/private_migrate.py"))
        self.assertTrue(privacy.is_forbidden("reports/food_intel_audit.json"))
        self.assertFalse(privacy.is_forbidden("scripts/audit_food_intel.py"))


if __name__ == "__main__":
    unittest.main()
