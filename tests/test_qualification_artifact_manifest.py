"""Qualification Artifact Manifest + CI Provenance tests.

Covers Generator V2 with mandatory --ci-run, --ci-head, --ci-conclusion.
"""
from __future__ import annotations

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
    assert r.returncode == 0
    return r.stdout


def _run_gen(repo: str, subject: str, ci_run: str, ci_head: str, ci_conclusion: str, output: str) -> tuple[int, str, str]:
    r = subprocess.run(
        ["python3", str(MANIFEST_GEN), "--repo", repo, "--subject-head", subject,
         "--ci-run", ci_run, "--ci-head", ci_head, "--ci-conclusion", ci_conclusion,
         "--output", output],
        cwd=REPO, capture_output=True, text=True, timeout=60, check=False,
    )
    return r.returncode, r.stdout, r.stderr


# ═══ Generator compile + positive ═══

class TestGeneratorCompile:
    def test_compiles(self) -> None:
        import py_compile
        py_compile.compile(str(MANIFEST_GEN), doraise=True)

    def test_help(self) -> None:
        r = subprocess.run(["python3", str(MANIFEST_GEN), "--help"],
                           cwd=REPO, capture_output=True, text=True, timeout=15, check=False)
        assert r.returncode == 0
        assert "--ci-run" in r.stdout
        assert "--ci-head" in r.stdout
        assert "--ci-conclusion" in r.stdout


class TestGeneratorPositive:
    def test_valid_provenance_succeeds(self, tmp_path: Path) -> None:
        out = tmp_path / "manifest.json"
        rc, stdout, stderr = _run_gen(str(REPO), QUAL_HEAD, "30057162252", QUAL_HEAD, "success", str(out))
        assert rc == 0, stderr
        d = json.loads(out.read_text())
        assert d["qualification_subject_head"] == QUAL_HEAD
        assert d["ci"]["head_sha"] == QUAL_HEAD
        assert d["ci"]["run_id"] == 30057162252
        assert d["ci"]["conclusion"] == "success"

    def test_two_runs_byte_identical(self, tmp_path: Path) -> None:
        out1 = tmp_path / "m1.json"
        out2 = tmp_path / "m2.json"
        _run_gen(str(REPO), QUAL_HEAD, "30057162252", QUAL_HEAD, "success", str(out1))
        _run_gen(str(REPO), QUAL_HEAD, "30057162252", QUAL_HEAD, "success", str(out2))
        assert out1.read_bytes() == out2.read_bytes()


# ═══ Negative: missing args ═══

class TestGeneratorNegativeMissingArgs:
    def test_missing_ci_run_fails(self, tmp_path: Path) -> None:
        r = subprocess.run(["python3", str(MANIFEST_GEN), "--repo", str(REPO),
                            "--subject-head", QUAL_HEAD, "--ci-head", QUAL_HEAD,
                            "--ci-conclusion", "success", "--output", str(tmp_path / "out.json")],
                           cwd=REPO, capture_output=True, text=True, timeout=15, check=False)
        assert r.returncode != 0

    def test_missing_ci_head_fails(self, tmp_path: Path) -> None:
        r = subprocess.run(["python3", str(MANIFEST_GEN), "--repo", str(REPO),
                            "--subject-head", QUAL_HEAD, "--ci-run", "1",
                            "--ci-conclusion", "success", "--output", str(tmp_path / "out.json")],
                           cwd=REPO, capture_output=True, text=True, timeout=15, check=False)
        assert r.returncode != 0

    def test_missing_ci_conclusion_fails(self, tmp_path: Path) -> None:
        r = subprocess.run(["python3", str(MANIFEST_GEN), "--repo", str(REPO),
                            "--subject-head", QUAL_HEAD, "--ci-run", "1",
                            "--ci-head", QUAL_HEAD, "--output", str(tmp_path / "out.json")],
                           cwd=REPO, capture_output=True, text=True, timeout=15, check=False)
        assert r.returncode != 0

    def test_missing_subject_head_fails(self, tmp_path: Path) -> None:
        r = subprocess.run(["python3", str(MANIFEST_GEN), "--repo", str(REPO),
                            "--ci-run", "1", "--ci-head", QUAL_HEAD,
                            "--ci-conclusion", "success", "--output", str(tmp_path / "out.json")],
                           cwd=REPO, capture_output=True, text=True, timeout=15, check=False)
        assert r.returncode != 0


# ═══ Negative: malformed SHAs ═══

class TestGeneratorNegativeSha:
    def test_short_subject_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), "82b1211", "1", QUAL_HEAD, "success", str(tmp_path / "out.json"))
        assert rc != 0

    def test_short_ci_head_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "1", "82b1211", "success", str(tmp_path / "out.json"))
        assert rc != 0

    def test_unreachable_subject_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), "0" * 40, "1", "0" * 40, "success", str(tmp_path / "out.json"))
        assert rc != 0

    def test_unreachable_ci_head_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "1", "0" * 40, "success", str(tmp_path / "out.json"))
        assert rc != 0

    def test_subject_not_equal_ci_head_fails(self, tmp_path: Path) -> None:
        other = "dd0505ac53721d8e2e6150e47936119fe16734d6"
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "1", other, "success", str(tmp_path / "out.json"))
        assert rc != 0


# ═══ Negative: invalid CI run ═══

class TestGeneratorNegativeCiRun:
    def test_zero_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "0", QUAL_HEAD, "success", str(tmp_path / "out.json"))
        assert rc != 0

    def test_negative_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "-1", QUAL_HEAD, "success", str(tmp_path / "out.json"))
        assert rc != 0

    def test_non_numeric_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "abc", QUAL_HEAD, "success", str(tmp_path / "out.json"))
        assert rc != 0

    def test_empty_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "", QUAL_HEAD, "success", str(tmp_path / "out.json"))
        assert rc != 0


# ═══ Negative: non-success conclusion ═══

class TestGeneratorNegativeConclusion:
    def test_failure_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "1", QUAL_HEAD, "failure", str(tmp_path / "out.json"))
        assert rc != 0

    def test_cancelled_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "1", QUAL_HEAD, "cancelled", str(tmp_path / "out.json"))
        assert rc != 0

    def test_skipped_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "1", QUAL_HEAD, "skipped", str(tmp_path / "out.json"))
        assert rc != 0

    def test_timed_out_fails(self, tmp_path: Path) -> None:
        rc, _, _ = _run_gen(str(REPO), QUAL_HEAD, "1", QUAL_HEAD, "timed_out", str(tmp_path / "out.json"))
        assert rc != 0


# ═══ Hardcoded provenance regression ═══

class TestHardcodedProvenanceRegression:
    def test_no_hardcoded_ci_run(self) -> None:
        src = MANIFEST_GEN.read_text()
        assert "30057162252" not in src, "hardcoded CI run must be removed"

    def test_no_implicit_ci_head_assignment(self) -> None:
        src = MANIFEST_GEN.read_text()
        assert "ci_head = subject_head" not in src.replace(" ", "")

    def test_no_default_success(self) -> None:
        src = MANIFEST_GEN.read_text()
        lines_with_success = [ln for ln in src.split("\n") if 'success' in ln and 'conclusion' in ln.lower()]
        for line in lines_with_success:
            assert "default" not in line.lower() or "no" in line.lower()


# ═══ Schema compliance (unchanged from V1) ═══

class TestSchemaCompliance:
    def test_completion_receipt_has_evidence_subject_head(self) -> None:
        r = json.loads(COMPLETION_RECEIPT.read_text())
        assert "evidence_subject_head" in r
        assert r["evidence_subject_head"] == QUAL_HEAD

    def test_completion_receipt_no_dual_authority(self) -> None:
        r = json.loads(COMPLETION_RECEIPT.read_text())
        assert "qualification_subject_head" not in r

    def test_qual_manifest_has_qualification_subject_head(self) -> None:
        m = json.loads(MANIFEST_OUT.read_text())
        assert "qualification_subject_head" in m

    def test_receipt_does_not_self_reference(self) -> None:
        r = json.loads(COMPLETION_RECEIPT.read_text())
        assert r.get("receipt_commit_head") is None
