"""Qualification Artifact Manifest regression tests.

Verifies manifest generation from git commit (not working tree),
schema compliance, byte stability, and field integrity.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

REPO = Path(os.environ.get("NEXARA_REPO", Path(__file__).resolve().parents[1])).resolve()
QUAL_HEAD = "82b1211213932cba71be68bf894dca0b8764e964"
MANIFEST_GEN = REPO / "scripts/qualification/build_artifact_manifest.py"
MANIFEST_OUT = REPO / ".nexara/qualification/qualification_artifact_manifest.json"
COMPLETION_RECEIPT = REPO / ".nexara/receipts/claude_completion_receipt.json"
QUAL_RECEIPT = REPO / ".nexara/receipts/system_qualification_final_receipt.json"


def _git(*args: str, timeout: int = 15) -> str:
    r = subprocess.run(["git"] + list(args), cwd=REPO,
                       capture_output=True, text=True, timeout=timeout, check=False)
    assert r.returncode == 0, "git {} failed: {}".format(" ".join(args), r.stderr.strip()[:200])
    return r.stdout.strip()


def _git_show_content(commit: str, path: str) -> bytes:
    r = subprocess.run(["git", "show", "{}:{}".format(commit, path)], cwd=REPO,
                       capture_output=True, timeout=15, check=False)
    assert r.returncode == 0, "git show {}:{} failed: {}".format(
        commit[:12], path, r.stderr.decode()[:200])
    return r.stdout


class TestGeneratorIntegrity:

    def test_generator_exists_and_compiles(self) -> None:
        assert MANIFEST_GEN.exists(), "Generator not found at {}".format(MANIFEST_GEN)
        import py_compile
        py_compile.compile(str(MANIFEST_GEN), doraise=True)

    def test_subject_tree_matches_git(self) -> None:
        expected = _git("show", "-s", "--format=%T", QUAL_HEAD)
        data = json.loads(MANIFEST_OUT.read_text())
        assert data["qualification_subject_tree"] == expected

    def test_collection_method_is_git_show(self) -> None:
        data = json.loads(MANIFEST_OUT.read_text())
        assert "git show" in data.get("collection_method", "")


class TestAll148Artifacts:

    def test_artifact_count_is_148(self) -> None:
        data = json.loads(MANIFEST_OUT.read_text())
        assert len(data["artifacts"]) == 148

    def test_every_artifact_has_valid_blob_sha(self) -> None:
        data = json.loads(MANIFEST_OUT.read_text())
        for a in data["artifacts"]:
            bs = a["git_blob_sha"]
            assert bs, "Empty git_blob_sha for {}".format(a["path"])
            assert len(bs) == 40, "Blob SHA not 40 hex chars: {}".format(a["path"])
            assert all(c in "0123456789abcdef" for c in bs), "Invalid hex: {}".format(bs[:12])

    def test_every_artifact_has_valid_sha256(self) -> None:
        data = json.loads(MANIFEST_OUT.read_text())
        for a in data["artifacts"]:
            h = a["sha256"]
            assert h, "Empty sha256 for {}".format(a["path"])
            assert len(h) == 64, "sha256 not 64 hex chars: {}".format(a["path"])

    def test_every_artifact_sha256_matches_git_blob(self) -> None:
        data = json.loads(MANIFEST_OUT.read_text())
        for a in data["artifacts"]:
            content = _git_show_content(QUAL_HEAD, a["path"])
            expected = hashlib.sha256(content).hexdigest()
            assert a["sha256"] == expected, (
                "sha256 mismatch for {}: manifest={}, actual={}".format(
                    a["path"], a["sha256"][:12], expected[:12]))


class TestByteStability:

    def test_two_runs_produce_identical_output(self, tmp_path: Path) -> None:
        out1 = tmp_path / "manifest_pass1.json"
        out2 = tmp_path / "manifest_pass2.json"
        r1 = subprocess.run(
            ["python3", str(MANIFEST_GEN), "--repo", str(REPO),
             "--subject-head", QUAL_HEAD, "--output", str(out1)],
            cwd=REPO, capture_output=True, text=True, timeout=60, check=False)
        assert r1.returncode == 0, "Run 1 failed: {}".format(r1.stderr[:200])
        r2 = subprocess.run(
            ["python3", str(MANIFEST_GEN), "--repo", str(REPO),
             "--subject-head", QUAL_HEAD, "--output", str(out2)],
            cwd=REPO, capture_output=True, text=True, timeout=60, check=False)
        assert r2.returncode == 0, "Run 2 failed: {}".format(r2.stderr[:200])
        assert out1.read_bytes() == out2.read_bytes(), "Byte mismatch across two runs"

    def test_formal_manifest_not_mutated_by_temp_run(self, tmp_path: Path) -> None:
        h1 = hashlib.sha256(MANIFEST_OUT.read_bytes()).hexdigest()
        out_tmp = tmp_path / "manifest_tmp.json"
        subprocess.run(
            ["python3", str(MANIFEST_GEN), "--repo", str(REPO),
             "--subject-head", QUAL_HEAD, "--output", str(out_tmp)],
            cwd=REPO, capture_output=True, text=True, timeout=60, check=False)
        h2 = hashlib.sha256(MANIFEST_OUT.read_bytes()).hexdigest()
        assert h1 == h2, "Formal manifest was mutated by temp run"


class TestSchemaCompliance:

    def test_completion_receipt_has_evidence_subject_head(self) -> None:
        r = json.loads(COMPLETION_RECEIPT.read_text())
        assert "evidence_subject_head" in r, "Completion receipt must have evidence_subject_head"
        assert r["evidence_subject_head"] == QUAL_HEAD

    def test_completion_receipt_no_dual_authority(self) -> None:
        r = json.loads(COMPLETION_RECEIPT.read_text())
        assert "qualification_subject_head" not in r, (
            "Completion receipt must not have qualification_subject_head (dual authority)")

    def test_qual_manifest_has_qualification_subject_head(self) -> None:
        m = json.loads(MANIFEST_OUT.read_text())
        assert "qualification_subject_head" in m
        assert m["qualification_subject_head"] == QUAL_HEAD

    def test_qual_receipt_has_qualification_subject_head(self) -> None:
        s = json.loads(QUAL_RECEIPT.read_text())
        assert "qualification_subject_head" in s

    def test_subjects_equal_same_frozen_commit(self) -> None:
        r = json.loads(COMPLETION_RECEIPT.read_text())
        m = json.loads(MANIFEST_OUT.read_text())
        assert r["evidence_subject_head"] == QUAL_HEAD
        assert m["qualification_subject_head"] == QUAL_HEAD

    def test_receipt_does_not_self_reference(self) -> None:
        r = json.loads(COMPLETION_RECEIPT.read_text())
        rch = r.get("receipt_commit_head")
        assert rch is None, "receipt_commit_head must be null, got {}".format(rch)


class TestValidatorReadOnly:

    def test_generator_run_does_not_dirty_worktree(self) -> None:
        before = subprocess.run(
            ["git", "status", "--porcelain=v1"], cwd=REPO,
            capture_output=True, text=True, timeout=10, check=False).stdout
        subprocess.run(
            ["python3", str(MANIFEST_GEN), "--repo", str(REPO),
             "--subject-head", QUAL_HEAD, "--output", str(MANIFEST_OUT)],
            cwd=REPO, capture_output=True, text=True, timeout=60, check=False)
        after = subprocess.run(
            ["git", "status", "--porcelain=v1"], cwd=REPO,
            capture_output=True, text=True, timeout=10, check=False).stdout
        new_dirty = set(after.split("\n")) - set(before.split("\n"))
        new_dirty = [line for line in new_dirty if line.strip()]
        assert not new_dirty, "Generator introduced new dirty files: {}".format(new_dirty)
