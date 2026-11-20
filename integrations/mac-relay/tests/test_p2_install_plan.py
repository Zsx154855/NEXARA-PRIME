import unittest

from p2_install_plan import audit_wheels, InstallPlanDenied


class InstallPlanTests(unittest.TestCase):
    def setUp(self):
        self.entry = {"name": "example", "version": "1.2.3", "sha256": "a" * 64,
                      "url": "https://files.pythonhosted.org/packages/ab/cd/example-1.2.3-py3-none-any.whl"}

    def test_review_output_is_not_an_install_action(self):
        self.assertEqual(audit_wheels([self.entry]), (self.entry.copy(),))

    def test_rejects_changed_source_identity_hash_and_duplicate_package(self):
        cases = [
            [dict(self.entry, url=self.entry["url"].replace("files.pythonhosted.org", "example.org"))],
            [dict(self.entry, url=self.entry["url"].replace("example-", "different-"))],
            [dict(self.entry, version=">=1")],
            [dict(self.entry, sha256="unverified")],
            [self.entry, self.entry],
        ]
        for items in cases:
            with self.subTest(items=items), self.assertRaises(InstallPlanDenied):
                audit_wheels(items)
