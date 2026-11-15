"""Executor and reviewer selection: process groups, exit codes, no silent fallback."""

from __future__ import annotations

import stat
from pathlib import Path

from nexara_prime.rd_factory.executor import ClaudeCodeExecutor
from nexara_prime.rd_factory.qa import IndependentQA


def _fake_bin(tmp_path: Path, name: str, script: str) -> Path:
    path = tmp_path / "bin" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess_run = __import__("subprocess").run
    subprocess_run(["git", "init", "-q"], cwd=str(repo), check=True)
    (repo / "a.txt").write_text("one\n")
    subprocess_run(["git", "add", "a.txt"], cwd=str(repo), check=True)
    subprocess_run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"],
        cwd=str(repo),
        check=True,
    )
    return repo


def test_claude_executor_captures_diff_and_exit_code(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fake = _fake_bin(tmp_path, "claude", "#!/bin/sh\necho \"{\\\"type\\\":\\\"result\\\"}\"\necho changed >> a.txt\nexit 0\n")
    log = tmp_path / "logs" / "run.log"
    executor = ClaudeCodeExecutor(claude_bin=str(fake), timeout_s=60)
    result = executor.execute(repo, "do the thing", log)
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.changed_files == ["a.txt"]
    assert result.diff_sha256
    assert result.events == 1


def test_claude_executor_marks_timeout(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fake = _fake_bin(tmp_path, "claude", "#!/bin/sh\nsleep 30\n")
    log = tmp_path / "run.log"
    executor = ClaudeCodeExecutor(claude_bin=str(fake), timeout_s=1)
    result = executor.execute(repo, "hang", log)
    assert result.timed_out is True
    assert result.exit_code is None


def test_claude_reviewer_returns_stdout(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fake = _fake_bin(
        tmp_path,
        "claude",
        "#!/bin/sh\necho '{\"verdict\": \"approve\", \"findings\": [], \"evidence\": [\"ok\"]}'\n",
    )
    qa = IndependentQA.claude(claude_bin=str(fake), timeout_s=60)
    verdict = qa.review(
        objective="tidy a.txt",
        acceptance=["a.txt changes"],
        diff="--- a/a.txt\n+++ b/a.txt\n+changed\n",
        gates=_passing_gates(),
        worktree=repo,
    )
    assert verdict.approved is True
    assert verdict.parse_ok is True


def test_claude_reviewer_failure_is_not_approval(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fake = _fake_bin(tmp_path, "claude", "#!/bin/sh\necho 'not json at all'\n")
    qa = IndependentQA.claude(claude_bin=str(fake), timeout_s=60)
    verdict = qa.review(
        objective="tidy a.txt",
        acceptance=["a.txt changes"],
        diff="(empty)",
        gates=_passing_gates(),
        worktree=repo,
    )
    assert verdict.approved is False
    assert verdict.parse_ok is False


def _passing_gates():
    from nexara_prime.rd_factory.qa import GateReport

    return GateReport(passed=True, results=(), checked_at="now")
