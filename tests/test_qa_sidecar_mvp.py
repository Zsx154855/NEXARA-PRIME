"""Offline fixture tests for independent QA Sidecar (no real credentials or network)."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "qa_sidecar" / "verify.py"

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class SidecarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo, self.evidence = base / "repo", base / "evidence"
        self.repo.mkdir()
        self.evidence.mkdir()
        self.git("init", "-q")
        (self.repo / "README").write_text("test\n")
        self.git("add", "README")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "baseline")
        self.commit = self.git("rev-parse", "HEAD").strip()
        contents = {
            "focused.log": "..... [100%]\n5 passed in 1.17s\n",
            "full.log": ".................................. [100%]\n2445 passed, 3 subtests passed in 59.45s\n",
            "commit-sha.txt": self.commit + "\n",
            "git-status.txt": "",
            "final-report.txt": "\n".join((
                "HEAD=" + self.commit, "FOCUSED_EXIT=0", "FULL_EXIT=0",
                "WORKTREE_CLEAN=YES", "REGRESSION=PASS",
                "INDEPENDENT_QA=NOT_VERIFIED")) + "\n",
        }
        for name, body in contents.items():
            (self.evidence / name).write_text(body)
        (self.evidence / "log-sha256.txt").write_text("\n".join(
            f"{sha256(self.evidence / name)}  {self.evidence / name}"
            for name in ("focused.log", "full.log")) + "\n")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), "--repo", str(self.repo),
                               "--evidence", str(self.evidence), "--sha", self.commit,
                               *args], capture_output=True, text=True)

    def test_consistent_bundle_stays_identity_blocked(self):
        result = self.cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["technical"], "PASS")
        self.assertEqual(output["gate"], "QA_BLOCKED")
        self.assertEqual(output["observed"]["full_passed"], 2445)

    def test_tampered_log_is_blocked(self):
        with (self.evidence / "full.log").open("a") as f:
            f.write("tampered\n")
        result = self.cli()
        self.assertEqual(result.returncode, 3)
        self.assertIn("tampered:full.log", result.stderr)

    def test_incorrect_git_sha_is_blocked(self):
        result = self.cli("--sha", "f" * 40)
        self.assertEqual(result.returncode, 3)
        self.assertIn("git_sha_mismatch", result.stderr)

    def test_conflicting_sidecar_exit_is_blocked(self):
        with (self.evidence / "final-report.txt").open("a") as f:
            f.write("FULL_EXIT=1\n")
        result = self.cli()
        self.assertEqual(result.returncode, 3)
        self.assertIn("missing_or_duplicate_field:FULL_EXIT", result.stderr)

    def test_symlink_log_rejected(self):
        source, copy = self.evidence / "full.log", self.evidence / "copy.log"
        source.rename(copy)
        source.symlink_to(copy)
        result = self.cli()
        self.assertEqual(result.returncode, 3)
        self.assertIn("missing_or_symlink", result.stderr)

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen unavailable")
    def test_disposable_signature_verifies_but_cannot_prove_independence(self):
        base = Path(self.tmp.name)
        statement, key, trust, sig = (
            base / "statement.json", base / "qa-key",
            base / "trusted-signers", base / "statement.sig")
        pre = self.cli("--statement-out", str(statement))
        self.assertEqual(pre.returncode, 2, pre.stderr)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                        "-f", str(key)], check=True, capture_output=True)
        trust.write_text("independent-qa " + key.with_suffix(".pub").read_text().strip() + "\n")
        signed = subprocess.run(["ssh-keygen", "-Y", "sign",
                                 "-n", "nexara-qa-sidecar-v1", "-f", str(key)],
                                input=statement.read_bytes(), capture_output=True)
        self.assertEqual(signed.returncode, 0, signed.stderr.decode())
        sig.write_bytes(signed.stdout)
        result = self.cli("--signature", str(sig), "--trusted-signers", str(trust),
                          "--trusted-signers-sha256", sha256(trust),
                          "--principal", "independent-qa")
        self.assertEqual(result.returncode, 2, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["signature"], "VALID")
        self.assertEqual(output["independent_identity"], "NOT_VERIFIED")

if __name__ == "__main__":
    unittest.main()
