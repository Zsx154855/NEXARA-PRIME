"""Isolated execution: one git worktree per task, one headless DSH run per attempt.

The factory never edits the main checkout. Every attempt runs in its own
worktree, under its own process group, so a hung run can be reaped with
SIGTERM/SIGKILL without touching the parent session.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class ExecutorError(RuntimeError):
    """The execution substrate refused to run or could not be inspected."""


@dataclass(frozen=True)
class ExecResult:
    exit_code: int | None
    timed_out: bool
    duration_s: float
    log_path: str
    events: int
    diff_sha256: str | None
    changed_files: list[str]

    def as_receipt(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_s": round(self.duration_s, 3),
            "log_path": self.log_path,
            "events": self.events,
            "diff_sha256": self.diff_sha256,
            "changed_files": self.changed_files,
        }


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise ExecutorError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:400]}")
    return proc.stdout


def changed_files(path: Path) -> list[str]:
    out = _git("status", "--porcelain", cwd=path)
    return [line[3:].strip() for line in out.splitlines() if line.strip()]


def diff(path: Path) -> str:
    return _git("diff", "HEAD", cwd=path)


def diff_sha256(path: Path) -> str:
    tracked = diff(path)
    untracked = ""
    for name in changed_files(path):
        candidate = path / name
        if candidate.is_file():
            untracked += candidate.read_text(errors="replace")
    return hashlib.sha256((tracked + untracked).encode()).hexdigest()


class WorktreeManager:
    """Creates and inspects per-task git worktrees."""

    def __init__(self, repo: str | Path, worktrees_root: str | Path, base_branch: str = "main"):
        self.repo = Path(repo)
        self.worktrees_root = Path(worktrees_root)
        self.base_branch = base_branch

    def prepare(self, task_id: str, branch: str) -> Path:
        path = self.worktrees_root / task_id
        self.worktrees_root.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self.cleanup(path)
        _git(
            "worktree", "add", "--force", "-B", branch, str(path), self.base_branch,
            cwd=self.repo,
        )
        return path

    def cleanup(self, path: str | Path) -> None:
        target = Path(path)
        try:
            _git("worktree", "remove", "--force", str(target), cwd=self.repo)
        except ExecutorError:
            if target.exists():
                _git("worktree", "prune", cwd=self.repo)

    def changed_files(self, path: Path) -> list[str]:
        return changed_files(path)

    def diff(self, path: Path) -> str:
        return diff(path)

    def diff_sha256(self, path: Path) -> str:
        return diff_sha256(path)

    def reset_soft(self, path: Path) -> None:
        """Undo the last factory commit while keeping its changes in the work tree."""
        _git("reset", "--soft", "HEAD~1", cwd=path)

    def diff_against(self, path: Path, base_branch: str | None = None) -> str:
        base = base_branch or self.base_branch
        return _git("diff", base + "...HEAD", cwd=path)

    def commit(self, path: Path, message: str) -> str:
        names = changed_files(path)
        if not names:
            raise ExecutorError("nothing to commit: the attempt produced no changes")
        _git("add", "--", *names, cwd=path)
        _git("-c", "user.name=NEXARA Factory", "-c", "user.email=factory@nexara.local",
             "commit", "-m", message, cwd=path)
        return _git("rev-parse", "HEAD", cwd=path).strip()


class HeadlessExecutor:
    """Runs one unattended DSH headless session inside a worktree."""

    def __init__(
        self,
        *,
        profile: str = "headless",
        dsh_bin: str = "dsh",
        timeout_s: float = 1800.0,
        permission_mode: str = "danger-full-access",
    ):
        self.profile = profile
        self.dsh_bin = dsh_bin
        self.timeout_s = timeout_s
        self.permission_mode = permission_mode

    def execute(self, worktree: Path, prompt: str, log_path: str | Path) -> ExecResult:
        log = Path(log_path)
        log.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "DSH_PERMISSION_MODE": self.permission_mode}
        cmd = [self.dsh_bin, "--profile", self.profile, "--json", "-"]
        started = time.monotonic()
        timed_out = False
        with open(log, "wb") as sink:
            proc = subprocess.Popen(
                cmd,
                cwd=str(worktree),
                stdin=subprocess.PIPE,
                stdout=sink,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            try:
                proc.communicate(input=prompt.encode(), timeout=self.timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._terminate(proc)
        duration = time.monotonic() - started
        events = self._count_events(log)
        try:
            diff_sha = diff_sha256(worktree)
            changed = changed_files(worktree)
        except ExecutorError:
            diff_sha, changed = None, []
        return ExecResult(
            exit_code=None if timed_out else proc.returncode,
            timed_out=timed_out,
            duration_s=duration,
            log_path=str(log),
            events=events,
            diff_sha256=diff_sha,
            changed_files=changed,
        )

    @staticmethod
    def _terminate(proc: subprocess.Popen, grace_s: float = 10.0) -> None:
        try:
            pgid = os.getpgid(proc.pid)
        except ProcessLookupError:
            return
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=grace_s)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            raise ExecutorError("headless run survived SIGKILL")

    @staticmethod
    def _count_events(log: Path) -> int:
        count = 0
        try:
            with log.open("r", errors="replace") as handle:
                for line in handle:
                    stripped = line.strip()
                    if stripped.startswith("{"):
                        try:
                            json.loads(stripped)
                        except json.JSONDecodeError:
                            continue
                        count += 1
        except OSError:
            return 0
        return count