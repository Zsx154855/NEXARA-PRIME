"""Regression coverage for G10 drift detection and secret scanning."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "governance"))
sys.path.insert(0, str(ROOT / "scripts" / "security"))

from detect_state_drift import check_consistency
from scan_hardcoded_secrets import is_allowed, scan_file


class G10DriftDetectionTests(unittest.TestCase):
    def _base_gate_status(self) -> dict:
        return {
            "program": "NEXARA_FIRST_PARTY_SOVEREIGN_AGENT",
            "gates": [{"id": f"G{i}", "status": "PASS"} for i in range(10)],
            "current_gate": "G10",
            "g10_composite_status": {
                "local_release": "LOCAL_RELEASE_READY",
                "external_distribution": "BLOCKED_EXTERNAL_CREDENTIAL",
                "git_push_tag": "PENDING_HUMAN_APPROVAL",
                "product_brand_name": "PRODUCT_DECISION_PENDING",
            },
        }

    def _base_program_state(self) -> dict:
        return {
            "program": "NEXARA_FIRST_PARTY_SOVEREIGN_AGENT",
            "current_program_gate": "G10",
            "gate_status": "LOCAL_RELEASE_READY",
            "gates_pass": [f"G{i}" for i in range(10)],
            "g10_composite_status": {
                "local_release": "LOCAL_RELEASE_READY",
                "external_distribution": "BLOCKED_EXTERNAL_CREDENTIAL",
                "git_push_tag": "PENDING_HUMAN_APPROVAL",
                "product_brand_name": "PRODUCT_DECISION_PENDING",
            },
        }

    def test_nested_g10_state_matches(self) -> None:
        self.assertEqual(check_consistency(self._base_gate_status(), self._base_program_state()), [])

    def test_local_release_mismatch(self) -> None:
        gate_status = self._base_gate_status()
        gate_status["g10_composite_status"]["local_release"] = "WRONG_VALUE"
        issues = check_consistency(gate_status, self._base_program_state())
        self.assertTrue(any("local_release" in issue for issue in issues))

    def test_external_distribution_mismatch(self) -> None:
        program_state = self._base_program_state()
        program_state["g10_composite_status"]["external_distribution"] = "WRONG_VALUE"
        issues = check_consistency(self._base_gate_status(), program_state)
        self.assertTrue(any("external_distribution" in issue for issue in issues))

    def test_git_push_tag_mismatch(self) -> None:
        program_state = self._base_program_state()
        program_state["g10_composite_status"]["git_push_tag"] = "APPROVED"
        issues = check_consistency(self._base_gate_status(), program_state)
        self.assertTrue(any("git_push_tag" in issue for issue in issues))

    def test_gate_status_missing_composite(self) -> None:
        gate_status = self._base_gate_status()
        del gate_status["g10_composite_status"]
        issues = check_consistency(gate_status, self._base_program_state())
        self.assertTrue(any("GATE_STATUS is missing 'g10_composite_status'" in issue for issue in issues))

    def test_program_state_missing_composite(self) -> None:
        program_state = self._base_program_state()
        del program_state["g10_composite_status"]
        issues = check_consistency(self._base_gate_status(), program_state)
        self.assertTrue(any("PROGRAM_STATE is missing 'g10_composite_status'" in issue for issue in issues))

    def test_program_state_wrong_composite_type(self) -> None:
        program_state = self._base_program_state()
        program_state["g10_composite_status"] = []
        issues = check_consistency(self._base_gate_status(), program_state)
        self.assertTrue(any("PROGRAM_STATE.g10_composite_status must be an object" in issue for issue in issues))

    def test_program_state_missing_required_field(self) -> None:
        program_state = self._base_program_state()
        del program_state["g10_composite_status"]["external_distribution"]
        issues = check_consistency(self._base_gate_status(), program_state)
        self.assertTrue(any("missing required field 'external_distribution'" in issue for issue in issues))

    def test_program_state_wrong_required_field_type(self) -> None:
        program_state = self._base_program_state()
        program_state["g10_composite_status"]["local_release"] = None
        issues = check_consistency(self._base_gate_status(), program_state)
        self.assertTrue(any("local_release must be a non-empty string" in issue for issue in issues))

    def test_legacy_top_level_field_detected(self) -> None:
        program_state = self._base_program_state()
        program_state["external_distribution"] = "BLOCKED_EXTERNAL_CREDENTIAL"
        issues = check_consistency(self._base_gate_status(), program_state)
        self.assertTrue(any("legacy top-level" in issue for issue in issues))


class SecretScannerTests(unittest.TestCase):
    def _write_temp(self, content: str, suffix: str = ".py") -> Path:
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
        handle.write(content)
        handle.close()
        return Path(handle.name)

    def _scan_assignment(self, key: str, value: str, quote: str = '"') -> list[dict]:
        path = self._write_temp(f"{key} = {quote}{value}{quote}\n")
        try:
            return scan_file(path)
        finally:
            path.unlink(missing_ok=True)

    def test_double_quoted_secret_detected(self) -> None:
        value = "live-prod-key-" + "8a9b0c1d2e3f"
        findings = self._scan_assignment("api_key", value)
        self.assertTrue(any(item["key"] == "api_key" for item in findings))

    def test_single_quoted_secret_detected(self) -> None:
        value = "s3cr3t!" + "p@ssw0rd"
        findings = self._scan_assignment("password", value, quote="'")
        self.assertTrue(any(item["key"] == "password" for item in findings))

    def test_prefixed_secret_identifiers_detected(self) -> None:
        value = "prod-secret-" + "7f6e5d4c3b2a"
        for key in ("openai_api_key", "github_token", "db_password"):
            with self.subTest(key=key):
                findings = self._scan_assignment(key, value)
                self.assertTrue(any(item["key"] == key for item in findings))

    def test_env_lookup_allowed(self) -> None:
        path = self._write_temp('api_key = os.environ["OPENAI_API_KEY"]\n')
        try:
            self.assertEqual(scan_file(path), [])
        finally:
            path.unlink(missing_ok=True)

    def test_dummy_fixture_allowed(self) -> None:
        path = self._write_temp('token = "dummy-token-for-test"\n')
        try:
            self.assertEqual(scan_file(path), [])
        finally:
            path.unlink(missing_ok=True)

    def test_placeholder_allowed(self) -> None:
        path = self._write_temp('password = "your-password-here"\n')
        try:
            self.assertEqual(scan_file(path), [])
        finally:
            path.unlink(missing_ok=True)

    def test_realistic_token_detected(self) -> None:
        value = "tkn_live_" + "8a9b0c1d2e3f4g5h"
        findings = self._scan_assignment("access_token", value)
        self.assertTrue(any(item["key"] == "access_token" for item in findings))

    def test_is_allowed_env(self) -> None:
        self.assertTrue(is_allowed("api_key = os.getenv('KEY')"))

    def test_is_allowed_example(self) -> None:
        self.assertTrue(is_allowed('api_key = "example-key-123"'))

    def test_is_allowed_template(self) -> None:
        self.assertTrue(is_allowed('token = "<YOUR_TOKEN>"'))

    def test_this_test_module_is_clean_for_repo_scan(self) -> None:
        self.assertEqual(scan_file(Path(__file__)), [])


if __name__ == "__main__":
    unittest.main()
