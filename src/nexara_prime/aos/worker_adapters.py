"""Real worker adapters for Claude Code, Codex, and local shell execution."""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from ..models import WorkerResult, WorkerType, FailureClass


@dataclass
class WorkerSession:
    session_id: str
    worker_type: str
    pid: int
    started_at: float
    last_output: str = ""
    exit_code: int | None = None


class LocalShellWorker:
    """Executes shell commands as a worker with structured output capture."""

    worker_id: str = "local_shell"
    worker_type: WorkerType = WorkerType.LOCAL_TOOL

    def __init__(self) -> None:
        self._sessions: dict[str, WorkerSession] = {}

    def execute(
        self, mission_id: str, input_data: dict[str, Any],
        *, timeout_s: float = 300.0,
    ) -> WorkerResult:
        command = input_data.get("command", "")
        cwd = input_data.get("cwd", os.getcwd())
        started = time.time()

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout_s, cwd=str(cwd),
            )
            duration_ms = int((time.time() - started) * 1000)
            success = result.returncode == 0

            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=success,
                failure_class=None if success else FailureClass.CODE_FAILURE,
                output={
                    "stdout": result.stdout[-5000:],
                    "stderr": result.stderr[-2000:],
                    "exit_code": result.returncode,
                },
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired as e:
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.WORKER_FAILURE,
                output={"error": f"timeout after {timeout_s}s", "stdout": e.stdout or ""},
                duration_ms=int(timeout_s * 1000),
            )

    def resume(self, session_id: str) -> WorkerResult:
        return WorkerResult(
            worker_id=self.worker_id, mission_id=session_id,
            success=False, failure_class=FailureClass.WORKER_FAILURE,
            output={"error": "shell workers cannot resume"},
        )

    def is_alive(self) -> bool:
        return True

    def health(self) -> dict[str, Any]:
        return {"status": "healthy", "sessions": len(self._sessions)}


class ClaudeCodeWorker:
    """Claude Code CLI worker adapter with session resume and structured output.

    Requires: claude CLI available in PATH.
    Uses: headless mode, JSON output, session resume via session ID.
    """

    worker_id: str = "claude_code"
    worker_type: WorkerType = WorkerType.CLAUDE

    def __init__(self, claude_bin: str = "claude") -> None:
        self._claude = claude_bin
        self._sessions: dict[str, WorkerSession] = {}
        self._default_timeout_s = 600.0

    def execute(
        self, mission_id: str, input_data: dict[str, Any],
        *, timeout_s: float | None = None,
    ) -> WorkerResult:
        timeout = timeout_s or self._default_timeout_s
        prompt = input_data.get("prompt", "")
        session_id = input_data.get("session_id", "")
        started = time.time()

        cmd = [self._claude]
        if session_id:
            cmd.extend(["--resume", session_id])
        cmd.extend(["--print", "--output-format", "text"])
        cmd.append(prompt)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=input_data.get("cwd", os.getcwd()),
                env={**os.environ, "CLAUDE_CODE_HEADLESS": "1"},
            )
            duration_ms = int((time.time() - started) * 1000)
            output = result.stdout

            # Detect common Claude patterns
            permission_block = "permission" in output.lower() and "approve" in output.lower()
            context_exhausted = "context" in output.lower() and "exhaust" in output.lower()
            completed = not permission_block and not context_exhausted

            failure = None
            if result.returncode != 0:
                if permission_block:
                    failure = FailureClass.PERMISSION_BLOCK
                elif context_exhausted:
                    failure = FailureClass.ENVIRONMENT_FAILURE
                else:
                    failure = FailureClass.CODE_FAILURE

            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=completed and result.returncode == 0,
                failure_class=failure,
                output={
                    "stdout": output[-10000:],
                    "exit_code": result.returncode,
                    "permission_block": permission_block,
                    "context_exhausted": context_exhausted,
                },
                duration_ms=duration_ms,
                next_action="complete" if completed else "review",
            )
        except subprocess.TimeoutExpired:
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.WORKER_FAILURE,
                output={"error": f"claude timeout after {timeout}s"},
                duration_ms=int(timeout * 1000),
            )
        except FileNotFoundError:
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.ENVIRONMENT_FAILURE,
                output={"error": f"claude binary not found: {self._claude}"},
            )

    def resume(self, session_id: str) -> WorkerResult:
        return self.execute(session_id, {"prompt": "continue", "session_id": session_id})

    def is_alive(self) -> bool:
        try:
            subprocess.run([self._claude, "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        return {"status": "healthy" if self.is_alive() else "unavailable", "binary": self._claude}


class DeterministicFakeWorker:
    """Deterministic fake worker for E2E testing — simulates Claude/Codex behavior."""

    worker_id: str = "fake_e2e_worker"
    worker_type: WorkerType = WorkerType.LOCAL_TOOL

    def __init__(
        self, succeed: bool = True, fail_mode: str = "",
        output_text: str = "mission executed successfully",
    ) -> None:
        self.succeed = succeed
        self.fail_mode = fail_mode
        self.output_text = output_text
        self._call_count = 0
        self._resume_count = 0

    def execute(
        self, mission_id: str, input_data: dict[str, Any],
        **kwargs: Any,
    ) -> WorkerResult:
        self._call_count += 1
        # Simulate failure modes
        if self.fail_mode == "crash" and self._call_count == 1:
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.WORKER_FAILURE,
                output={"error": "simulated crash", "attempt": self._call_count},
            )
        if self.fail_mode == "timeout" and self._call_count == 1:
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.LEASE_EXPIRED,
                output={"error": "simulated timeout"},
            )
        if self.fail_mode == "test_failure":
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.TEST_FAILURE,
                output={"error": "simulated test failure", "failing_tests": 3},
            )

        return WorkerResult(
            worker_id=self.worker_id, mission_id=mission_id,
            success=self.succeed,
            output={"text": self.output_text, "attempt": self._call_count},
            duration_ms=100,
        )

    def resume(self, session_id: str) -> WorkerResult:
        self._resume_count += 1
        return WorkerResult(
            worker_id=self.worker_id, mission_id=session_id,
            success=True,
            output={"text": f"resumed session {session_id}", "resume_count": self._resume_count},
        )

    def is_alive(self) -> bool:
        return self._call_count < 10

    def health(self) -> dict[str, Any]:
        return {"status": "healthy", "calls": self._call_count}
