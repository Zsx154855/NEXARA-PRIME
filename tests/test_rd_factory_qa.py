"""QA is fail-closed: exit codes decide gates, ambiguity rejects."""

from __future__ import annotations

import subprocess
from pathlib import Path

from nexara_prime.rd_factory.qa import (
    DeterministicGates,
    GateCommand,
    GateReport,
    IndependentQA,
)


def test_gate_fails_on_nonzero_exit(tmp_path: Path) -> None:
    gates = DeterministicGates(
        [
            GateCommand("boom", ("python3", "-c", "import sys; sys.exit(3)"), timeout_s=60),
            GateCommand("ok", ("python3", "-c", "print('fine')"), timeout_s=60),
        ]
    )
    report = gates.run(tmp_path)
    assert report.passed is False
    assert [item.exit_code for item in report.results] == [3, 0]
    assert "boom" in report.summary()


def test_gate_timeout_is_a_failure(tmp_path: Path) -> None:
    gates = DeterministicGates(
        [GateCommand("slow", ("python3", "-c", "import time; time.sleep(5)"), timeout_s=0.2)]
    )
    report = gates.run(tmp_path)
    assert report.passed is False
    assert report.results[0].exit_code is None
    assert "timed out" in report.results[0].tail


def test_missing_command_fails_closed(tmp_path: Path) -> None:
    gates = DeterministicGates([GateCommand("absent", ("definitely-not-a-binary-xyz",))])
    report = gates.run(tmp_path)
    assert report.passed is False
    assert "unavailable" in report.results[0].tail


def test_unparsable_answer_rejects() -> None:
    verdict = IndependentQA.parse("looks good to me")
    assert verdict.approved is False
    assert verdict.parse_ok is False


def test_unknown_verdict_rejects() -> None:
    verdict = IndependentQA.parse('{"verdict": "lgtm", "findings": []}')
    assert verdict.approved is False
    assert verdict.parse_ok is False


def test_approval_is_parsed_from_last_json_object() -> None:
    text = 'chatter {"verdict": "reject"} more {"verdict": "approve", "evidence": ["pytest ok"]}'
    verdict = IndependentQA.parse(text)
    assert verdict.approved is True
    assert verdict.evidence == ("pytest ok",)


def test_reviewer_crash_rejects(tmp_path: Path) -> None:
    def boom(prompt: str, worktree: Path) -> str:
        raise RuntimeError("reviewer died")

    gates = GateReport(passed=True, results=(), checked_at="2026-01-01T00:00:00Z")
    verdict = IndependentQA(boom).review(
        objective="x", acceptance=[], diff="", gates=gates, worktree=tmp_path
    )
    assert verdict.approved is False
    assert "reviewer failed" in verdict.findings[0]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=qa@nexara.local", "-c", "user.name=QA", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts" / "security").mkdir(parents=True)
    (repo / "scripts" / "governance").mkdir(parents=True)
    (repo / "old.py").write_text("VALUE = 1\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")
    return repo


def test_governance_script_resolves_the_worktree_not_the_checkout(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    probe = (
        "import pathlib\n"
        "print('root=' + str(pathlib.Path(__file__).resolve().parents[2]))\n"
    )
    (repo / "scripts" / "governance" / "validate_nsec.py").write_text(probe)
    worktree = tmp_path / "worktree"
    (worktree / "scripts" / "governance").mkdir(parents=True)
    (worktree / "scripts" / "governance" / "validate_nsec.py").write_text(probe)

    gates = DeterministicGates.default(repo, base_ref="HEAD")
    report = gates.run(worktree)

    nsec = [item for item in report.results if item.name == "nsec"][0]
    assert "root=" + str(worktree.resolve()) in nsec.tail


def _scanner(repo: Path) -> None:
    (repo / "scripts" / "security" / "scan_hardcoded_secrets.py").write_text(
        "print('Secret scan: FAILED - 1 finding(s)')\n"
        "print('  old.py:3  api_key = \"...\"')\n"
    )


def test_secret_scan_ignores_findings_in_unchanged_files(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    _scanner(repo)

    gates = DeterministicGates.default(repo, base_ref="HEAD")
    report = gates.run(repo)

    secrets = [item for item in report.results if item.name == "secrets"][0]
    assert secrets.passed is True


def test_secret_scan_fails_on_findings_in_changed_files(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    _scanner(repo)
    (repo / "old.py").write_text("VALUE = 2\n")
    _git(repo, "commit", "-qam", "change")

    gates = DeterministicGates.default(repo, base_ref="HEAD~1")
    report = gates.run(repo)

    secrets = [item for item in report.results if item.name == "secrets"][0]
    assert secrets.passed is False
    assert "old.py" in secrets.tail
