"""Sidecar security contract: fixture-only, local, no paid API or network."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "qa_sidecar" / "verify.py"
ORIGIN = "https://github.com/Zsx154855/NEXARA-PRIME.git"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class TestSidecar(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.git("init", "-q")
        self.git("remote", "add", "origin", ORIGIN)
        (self.repo / "README").write_text("trusted fixture\n")
        self.git("add", "README")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "baseline")
        self.commit = self.git("rev-parse", "HEAD").strip()
        files = {
            "focused.log": "..... [100%]\n5 passed in 1.17s\n",
            "full.log": ".... [100%]\n2445 passed, 3 subtests passed in 59.45s\n",
            "commit-sha.txt": self.commit + "\n",
            "git-status.txt": "",
            "final-report.txt": "\n".join([
                "HEAD=" + self.commit, "FOCUSED_EXIT=0", "FULL_EXIT=0",
                "WORKTREE_CLEAN=YES", "REGRESSION=PASS",
                "INDEPENDENT_QA=NOT_VERIFIED", "PRODUCTION_LEARNING=NOT_VERIFIED",
                "MODE=MOCK_INTEGRATION", "EVIDENCE_DIR=" + str(self.evidence),
            ]) + "\n",
        }
        for name, body in files.items():
            (self.evidence / name).write_text(body)
        (self.evidence / "log-sha256.txt").write_text("\n".join(
            f"{sha256((self.evidence / name).read_bytes())}  {self.evidence / name}"
            for name in ("focused.log", "full.log")) + "\n")
        self.policy = self.root / "policy.json"
        self.expected = {
            "schema": "nexara.qa-sidecar.policy.v1",
            "repository": "Zsx154855/NEXARA-PRIME",
            "commit_sha": self.commit,
            "expected_counts": {"focused_passed": 5, "full_passed": 2445, "subtests_passed": 3},
            "expected_log_sha256": {
                name: sha256((self.evidence / name).read_bytes())
                for name in ("focused.log", "full.log")
            },
            "signer": None,
        }
        self.save_policy()

    def save_policy(self):
        self.policy.write_text(json.dumps(self.expected, sort_keys=True))

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def run_cli(self, *args, pin=None):
        return subprocess.run([
            sys.executable, str(CLI), "--repo", str(self.repo),
            "--evidence", str(self.evidence), "--policy", str(self.policy),
            "--policy-sha256", pin or sha256(self.policy.read_bytes()), *args
        ], capture_output=True, text=True)

    def assert_blocked(self, result, reason):
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn(reason, result.stderr)

    def test_valid_evidence_has_no_independent_identity(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["technical"], "PASS")
        self.assertEqual(data["gate"], "QA_BLOCKED")
        self.assertEqual(data["signature"], "ABSENT")

    def test_wrong_origin(self):
        self.git("remote", "set-url", "origin", "https://github.com/other/repo")
        self.assert_blocked(self.run_cli(), "git_origin_mismatch")

    def test_wrong_git_sha(self):
        self.expected["commit_sha"] = "f" * 40
        self.save_policy()
        self.assert_blocked(self.run_cli(), "git_sha_mismatch")

    def test_dirty_worktree(self):
        (self.repo / "untracked").write_text("noise")
        self.assert_blocked(self.run_cli(), "git_dirty")

    def test_policy_tampering(self):
        trusted_pin = sha256(self.policy.read_bytes())
        self.expected["expected_counts"]["full_passed"] = 1
        self.save_policy()
        self.assert_blocked(self.run_cli(pin=trusted_pin), "policy_digest_mismatch")

    def test_unsupported_cli_override(self):
        result = self.run_cli("--min-full", "1")
        self.assertEqual(result.returncode, 2)  # argparse rejects the old override flag
        self.assertIn("unrecognized arguments", result.stderr)

    def test_log_tampering(self):
        with (self.evidence / "full.log").open("a") as f:
            f.write("altered\n")
        self.assert_blocked(self.run_cli(), "log_hash_mismatch")

    def test_joint_log_and_sidecar_tampering(self):
        log = self.evidence / "full.log"
        log.write_text("...\n2445 passed, 3 subtests passed in 5.0s\n")
        sums = self.evidence / "log-sha256.txt"
        lines = sums.read_text().splitlines()
        lines[1] = f"{sha256(log.read_bytes())}  {log}"
        sums.write_text("\n".join(lines) + "\n")
        self.assert_blocked(self.run_cli(), "log_hash_mismatch")

    def test_duplicate_exit_in_report(self):
        with (self.evidence / "final-report.txt").open("a") as f:
            f.write("FULL_EXIT=1\n")
        self.assert_blocked(self.run_cli(), "duplicate_field:FULL_EXIT")

    def test_sidecar_hash_path_spoofing(self):
        sums = self.evidence / "log-sha256.txt"
        sums.write_text(sums.read_text().replace(str(self.evidence), "/tmp/other"))
        self.assert_blocked(self.run_cli(), "hash_source_path_mismatch")

    def test_symlinked_log(self):
        log = self.evidence / "full.log"
        copy = self.evidence / "copy.log"
        log.rename(copy)
        log.symlink_to(copy)
        self.assert_blocked(self.run_cli(), "missing_or_symlink:full.log")

    def test_policy_in_repo_is_not_trusted(self):
        self.policy = self.repo / "policy.json"
        self.save_policy()
        self.assert_blocked(self.run_cli(), "policy_not_external")

    def test_bad_counts_without_policy_override(self):
        self.expected["expected_counts"]["full_passed"] = 2444
        self.save_policy()
        self.assert_blocked(self.run_cli(), "pytest_counts_not_expected")

    def test_output_cannot_touch_worktree(self):
        self.assert_blocked(self.run_cli("--statement-out", str(self.repo / "output.json")),
                            "output_not_external")

    def test_signature_requires_trust_policy(self):
        sig, trust = self.root / "fake.sig", self.root / "signers"
        sig.write_text("fake")
        trust.write_text("fake")
        self.assert_blocked(self.run_cli("--signature", str(sig), "--trusted-signers", str(trust)),
                            "signature_not_authorized_by_policy")

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen not installed")
    def test_disposable_signature_still_blocked(self):
        key, trust, sig, statement = (self.root / "key", self.root / "signers",
                                      self.root / "statement.sig", self.root / "statement.json")
        result = self.run_cli("--statement-out", str(statement))
        self.assertEqual(result.returncode, 2, result.stderr)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                       capture_output=True, check=True)
        trust.write_text("qa-principal " + key.with_suffix(".pub").read_text().strip() + "\n")
        self.expected["signer"] = {"principal": "qa-principal", "allowed_signers_sha256": sha256(trust.read_bytes())}
        self.save_policy()
        # Rebuild statement after policy changes, because a signed policy digest is part of its content.
        statement.unlink()
        r2 = self.run_cli("--statement-out", str(statement))
        self.assertEqual(r2.returncode, 2, r2.stderr)
        signed = subprocess.run(["ssh-keygen", "-Y", "sign", "-n", "nexara-qa-sidecar-v1", "-f", str(key)],
                                input=statement.read_bytes(), capture_output=True)
        self.assertEqual(signed.returncode, 0, signed.stderr.decode())
        sig.write_bytes(signed.stdout)
        checked = self.run_cli("--signature", str(sig), "--trusted-signers", str(trust))
        self.assertEqual(checked.returncode, 2, checked.stderr)
        result = json.loads(checked.stdout)
        self.assertEqual(result["signature"], "VALID_BUT_CUSTODY_UNVERIFIED")
        self.assertEqual(result["gate"], "QA_BLOCKED")


if __name__ == "__main__":
    unittest.main()
