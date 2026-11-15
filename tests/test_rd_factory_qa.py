"""QA is fail-closed: exit codes decide gates, ambiguity rejects."""

from __future__ import annotations

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
