"""P2 Review Fixes: G10 drift detection + secret scanner tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ── P2-1: Drift Detection with nested G10 schema ──

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "governance"))
from detect_state_drift import check_consistency


class G10DriftDetectionTests(unittest.TestCase):
    """Verify drift detector correctly handles nested g10_composite_status."""

    def _base_gate_status(self):
        return {
            "program": "NEXARA_FIRST_PARTY_SOVEREIGN_AGENT",
            "gates": [{"id": f"G{i}", "status": "PASS"} for i in range(10)],
            "current_gate": "G10",
            "gates_pass": ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"],
            "g10_composite_status": {
                "local_release": "LOCAL_RELEASE_READY",
                "external_distribution": "BLOCKED_EXTERNAL_CREDENTIAL",
                "git_push_tag": "PENDING_HUMAN_APPROVAL",
                "product_brand_name": "PRODUCT_DECISION_PENDING",
            },
        }

    def _base_program_state(self):
        return {
            "program": "NEXARA_FIRST_PARTY_SOVEREIGN_AGENT",
            "current_program_gate": "G10",
            "gate_status": "LOCAL_RELEASE_READY",
            "gates_pass": ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"],
            "g10_composite_status": {
                "local_release": "LOCAL_RELEASE_READY",
                "external_distribution": "BLOCKED_EXTERNAL_CREDENTIAL",
                "git_push_tag": "PENDING_HUMAN_APPROVAL",
                "product_brand_name": "PRODUCT_DECISION_PENDING",
            },
        }

    def test_nested_g10_state_matches(self):
        gs = self._base_gate_status()
        ps = self._base_program_state()
        issues = check_consistency(gs, ps)
        self.assertEqual(issues, [], f"Expected no issues, got: {issues}")

    def test_local_release_mismatch(self):
        gs = self._base_gate_status()
        ps = self._base_program_state()
        gs["g10_composite_status"]["local_release"] = "WRONG_VALUE"
        issues = check_consistency(gs, ps)
        self.assertTrue(any("local_release" in i for i in issues),
                        f"Should detect local_release mismatch, got: {issues}")

    def test_external_distribution_mismatch(self):
        gs = self._base_gate_status()
        ps = self._base_program_state()
        gs["g10_composite_status"]["external_distribution"] = "WRONG_VALUE"
        issues = check_consistency(gs, ps)
        self.assertTrue(any("external_distribution" in i for i in issues),
                        f"Should detect external_distribution mismatch, got: {issues}")

    def test_human_approval_mismatch(self):
        gs = self._base_gate_status()
        ps = self._base_program_state()
        gs["g10_composite_status"]["git_push_tag"] = "APPROVED"
        issues = check_consistency(gs, ps)
        self.assertTrue(any("git_push_tag" in i for i in issues),
                        f"Should detect git_push_tag mismatch, got: {issues}")

    def test_missing_g10_composite_status(self):
        gs = self._base_gate_status()
        ps = self._base_program_state()
        del gs["g10_composite_status"]
        issues = check_consistency(gs, ps)
        self.assertTrue(any("missing" in i for i in issues),
                        f"Should flag missing g10_composite_status, got: {issues}")

    def test_wrong_type_g10_composite_status(self):
        gs = self._base_gate_status()
        ps = self._base_program_state()
        gs["g10_composite_status"] = "LOCAL_RELEASE_READY"  # string, not dict
        issues = check_consistency(gs, ps)
        self.assertTrue(any("must be an object" in i for i in issues),
                        f"Should flag wrong type, got: {issues}")

    def test_top_level_external_distribution_detected(self):
        gs = self._base_gate_status()
        gs["external_distribution"] = "BLOCKED_EXTERNAL_CREDENTIAL"
        ps = self._base_program_state()
        issues = check_consistency(gs, ps)
        self.assertTrue(any("top-level" in i for i in issues),
                        f"Should flag legacy flat field, got: {issues}")


# ── P2-2: Secret Scanner ──

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "security"))
from scan_hardcoded_secrets import is_allowed, scan_file


class SecretScannerTests(unittest.TestCase):
    """Verify secret scanner detects both quote styles and respects allowlist."""

    def _write_temp(self, content: str, suffix: str = ".py") -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_double_quoted_secret_detected(self):
        f = self._write_temp('api_key = "live-prod-key-8a9b0c1d2e3f"\n')
        findings = scan_file(f)
        f.unlink()
        self.assertTrue(any("api_key" in finding["key"] for finding in findings),
                        f"Should detect double-quoted secret, got: {findings}")

    def test_single_quoted_secret_detected(self):
        f = self._write_temp("password = 's3cr3t!p@ssw0rd'\n")
        findings = scan_file(f)
        f.unlink()
        self.assertTrue(any("password" in finding["key"] for finding in findings),
                        f"Should detect single-quoted secret, got: {findings}")

    def test_env_lookup_allowed(self):
        f = self._write_temp('api_key = os.environ["OPENAI_API_KEY"]\n')
        findings = scan_file(f)
        f.unlink()
        self.assertEqual(findings, [], f"Env lookup should be allowed, got: {findings}")

    def test_dummy_fixture_allowed(self):
        f = self._write_temp('token = "dummy-token-for-test"\n')
        findings = scan_file(f)
        f.unlink()
        self.assertEqual(findings, [], f"Dummy fixture should be allowed, got: {findings}")

    def test_placeholder_allowed(self):
        f = self._write_temp('password = "your-password-here"\n')
        findings = scan_file(f)
        f.unlink()
        self.assertEqual(findings, [], f"Placeholder should be allowed, got: {findings}")

    def test_realistic_token_detected(self):
        f = self._write_temp('access_token = "tkn_live_8a9b0c1d2e3f4g5h"\n')
        findings = scan_file(f)
        f.unlink()
        self.assertTrue(any("access_token" in finding["key"] for finding in findings),
                        f"Should detect realistic token, got: {findings}")

    def test_is_allowed_env(self):
        self.assertTrue(is_allowed("api_key = os.getenv('KEY')"))

    def test_is_allowed_example(self):
        self.assertTrue(is_allowed('api_key = "example-key-123"'))

    def test_is_allowed_template(self):
        self.assertTrue(is_allowed('token = "<YOUR_TOKEN>"'))


if __name__ == "__main__":
    unittest.main()
