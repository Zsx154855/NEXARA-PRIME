"""Real worker adapters for Claude Code, Codex, and local shell execution.

Each adapter is built against the actual CLI version installed on the host.
"""
from __future__ import annotations

import json
import os
import signal
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


# ── Failure detection helpers ──

def _detect_context_exhaustion(stderr: str, stdout: str) -> bool:
    combined = (stderr + stdout).lower()
    markers = [
        "context length", "context window", "token limit",
        "context limit exceeded", "maximum context",
        "input length exceeds", "too many tokens",
        "context_length_exceeded",
    ]
    return any(m in combined for m in markers)


def _detect_permission_block(stderr: str, stdout: str) -> bool:
    combined = (stderr + stdout).lower()
    markers = [
        "permission denied", "permission block",
        "requires approval", "do you want to proceed",
        "i need your permission", "i'll need approval",
        "permission required",
    ]
    return any(m in combined for m in markers)


def _detect_credential_failure(stderr: str, stdout: str) -> bool:
    combined = (stderr + stdout).lower()
    markers = [
        "authentication", "unauthorized", "invalid api key",
        "not authenticated", "login required", "credential",
        "auth error", "please sign in", "api key not",
    ]
    return any(m in combined for m in markers)


def _detect_network_failure(stderr: str, stdout: str) -> bool:
    combined = (stderr + stdout).lower()
    markers = [
        "network", "connection refused", "connection reset",
        "timeout", "dns", "name resolution", "unreachable",
        "econnrefused", "econnreset", "etimedout",
        "cannot connect", "no route to host",
    ]
    return any(m in combined for m in markers)


def _classify_failure(
    exit_code: int, stderr: str, stdout: str,
) -> FailureClass | None:
    """Classify the failure mode from stderr/stdout/exit_code.

    Returns None if no failure detected.
    """
    if exit_code == 0:
        return None
    if _detect_permission_block(stderr, stdout):
        return FailureClass.PERMISSION_BLOCK
    if _detect_credential_failure(stderr, stdout):
        return FailureClass.ENVIRONMENT_FAILURE
    if _detect_context_exhaustion(stderr, stdout):
        return FailureClass.ENVIRONMENT_FAILURE
    if _detect_network_failure(stderr, stdout):
        return FailureClass.EXTERNAL_SERVICE_FAILURE
    return FailureClass.CODE_FAILURE


# ═══════════════════════════════════════════════════════════════════
# Local Shell Worker
# ═══════════════════════════════════════════════════════════════════

class LocalShellWorker:
    """Executes shell commands as a worker with structured output capture."""

    worker_id: str = "local_shell"
    worker_type: WorkerType = WorkerType.LOCAL_TOOL

    def __init__(self) -> None:
        self._sessions: dict[str, WorkerSession] = {}

    def execute(
        self, mission_id: str, input_data: dict[str, Any],
        **kwargs: Any,
    ) -> WorkerResult:
        command = input_data.get("command", "")
        cwd = input_data.get("cwd", "") or os.getcwd()
        timeout_s = float(input_data.get("timeout_s", kwargs.get("timeout_s", 300.0)))
        started = time.time()

        # ── Thread 39: Fail closed on empty or whitespace-only command ──
        if not command or not command.strip():
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.CODE_FAILURE,
                output={
                    "error": "empty command — cannot execute on LocalShellWorker",
                    "hint": "prompt-only missions must use an LLM worker (Claude, Codex), not a shell worker",
                },
                duration_ms=0,
            )

        # Thread 9 (Codex V8): Use process group to ensure complete cleanup
        # on timeout.  start_new_session=True puts the process in its own
        # session with PGID == PID.  On timeout we kill the entire group
        # with os.killpg() so children and grandchildren cannot escape.
        proc = None
        try:
            proc = subprocess.Popen(
                command, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=str(cwd),
                start_new_session=True,  # own process group
            )
            stdout, stderr = proc.communicate(timeout=timeout_s)
            duration_ms = int((time.time() - started) * 1000)
            exit_code = proc.returncode
            success = exit_code == 0
            failure = _classify_failure(exit_code, stderr, stdout)

            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=success,
                failure_class=failure,
                output={
                    "stdout": (stdout or "")[-5000:],
                    "stderr": (stderr or "")[-2000:],
                    "exit_code": exit_code,
                },
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            # Kill the entire process group — children and grandchildren
            # cannot survive the timeout.
            if proc is not None:
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    # Brief grace period then SIGKILL
                    try:
                        proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        os.killpg(pgid, signal.SIGKILL)
                        proc.wait(timeout=2.0)
                except (OSError, ProcessLookupError):
                    pass  # Process already gone
            # Collect any remaining output
            try:
                out, err = proc.communicate(timeout=2.0) if proc else ("", "")
            except Exception:
                out, _err = "", ""
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.WORKER_FAILURE,
                output={
                    "error": f"timeout after {timeout_s}s — process group killed",
                    "stdout": (out or "")[-2000:] if out else "",
                },
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


# ═══════════════════════════════════════════════════════════════════
# Claude Code Worker (real CLI integration)
# ═══════════════════════════════════════════════════════════════════

class ClaudeCodeWorker:
    """Claude Code CLI worker adapter — built against Claude Code 2.1.207.

    Uses: --print for non-interactive, --output-format json for structured
    output, --json-schema for schema validation, --resume for session resume,
    --session-id for explicit session tracking.
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
        cwd = input_data.get("cwd") or os.getcwd()
        model = input_data.get("model", "")
        json_schema = input_data.get("json_schema", "")
        system_prompt = input_data.get("system_prompt", "")
        started = time.time()

        cmd = [self._claude, "--print"]

        # Session management
        if session_id:
            cmd.extend(["--resume", session_id])
        else:
            new_sid = input_data.get("new_session_id", "")
            if new_sid:
                cmd.extend(["--session-id", new_sid])

        # Output format: prefer JSON for structured parsing
        cmd.extend(["--output-format", "json"])

        # Model selection
        if model:
            cmd.extend(["--model", model])

        # JSON Schema for structured output
        if json_schema:
            cmd.extend(["--json-schema", json_schema])

        # System prompt
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        # Headless mode
        env = {**os.environ, "CLAUDE_CODE_HEADLESS": "1"}

        # Add the prompt
        cmd.append(prompt)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd), env=env,
            )
            duration_ms = int((time.time() - started) * 1000)
            stdout = result.stdout
            stderr = result.stderr

            # Try to parse structured JSON output
            parsed_output: dict[str, Any] = {"stdout": stdout[-10000:], "stderr": stderr[-2000:]}
            extracted_session_id: str = ""
            completion_detected: bool = result.returncode == 0

            if stdout.strip():
                try:
                    parsed = json.loads(stdout)
                    if isinstance(parsed, dict):
                        parsed_output = parsed
                        # Extract session ID from response metadata
                        extracted_session_id = parsed.get("session_id", "")
                        # Completion event detection
                        if parsed.get("type") == "result":
                            completion_detected = True
                        if parsed.get("stop_reason") == "end_turn":
                            completion_detected = True
                except json.JSONDecodeError:
                    pass  # Non-JSON output, use raw stdout

            failure = _classify_failure(result.returncode, stderr, stdout)

            # Session tracking
            if extracted_session_id:
                self._sessions[extracted_session_id] = WorkerSession(
                    session_id=extracted_session_id,
                    worker_type="claude_code",
                    pid=result.pid if hasattr(result, 'pid') else 0,
                    started_at=started,
                    last_output=stdout[:2000],
                    exit_code=result.returncode,
                )

            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=completion_detected and result.returncode == 0,
                failure_class=failure,
                output=parsed_output,
                duration_ms=duration_ms,
                next_action="complete" if completion_detected else "review",
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
        return self.execute(
            session_id,  # mission_id
            {"prompt": "continue", "session_id": session_id},
        )

    def is_alive(self) -> bool:
        try:
            result = subprocess.run(
                [self._claude, "--version"], capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        alive = self.is_alive()
        version = ""
        if alive:
            try:
                v = subprocess.run(
                    [self._claude, "--version"], capture_output=True, text=True, timeout=5,
                )
                version = v.stdout.strip()
            except Exception:
                pass
        return {
            "status": "healthy" if alive else "unavailable",
            "binary": self._claude,
            "version": version,
            "active_sessions": len(self._sessions),
        }


# ═══════════════════════════════════════════════════════════════════
# Codex Worker (real CLI integration)
# ═══════════════════════════════════════════════════════════════════

class CodexWorker:
    """Codex CLI worker adapter — built against codex-cli 0.143.0.

    Uses: `codex exec` for non-interactive execution, --json for JSONL
    output, --output-schema for structured output, --ephemeral for
    stateless runs, --output-last-message for result capture.

    Session/resume is NOT available in `codex exec` as of 0.143.0.
    This worker operates in STATELESS_CODEX_WORKER mode.
    """

    worker_id: str = "codex"
    worker_type: WorkerType = WorkerType.CODE_REVIEWER

    # Known limitation — documented in evidence
    _MODE = "STATELESS_CODEX_WORKER"
    _MODE_NOTE = (
        "codex exec (0.143.0) does not support session resume. "
        "Each execution is stateless. Use codex exec --output-last-message "
        "for result capture and --ephemeral to avoid disk persistence."
    )

    def __init__(self, codex_bin: str = "codex") -> None:
        self._codex = codex_bin
        self._default_timeout_s = 600.0
        self._call_count = 0

    def execute(
        self, mission_id: str, input_data: dict[str, Any],
        *, timeout_s: float | None = None,
    ) -> WorkerResult:
        timeout = timeout_s or self._default_timeout_s
        prompt = input_data.get("prompt", "")
        cwd = input_data.get("cwd") or os.getcwd()
        model = input_data.get("model", "")
        output_schema_file = input_data.get("output_schema_file", "")
        sandbox_mode = input_data.get("sandbox", "workspace-write")
        started = time.time()

        cmd = [self._codex, "exec"]

        # JSONL output for structured parsing
        cmd.append("--json")

        # Ephemeral: don't persist session to disk
        cmd.append("--ephemeral")

        # Sandbox
        cmd.extend(["--sandbox", sandbox_mode])

        # Model
        if model:
            cmd.extend(["--model", model])

        # Structured output schema
        if output_schema_file:
            cmd.extend(["--output-schema", output_schema_file])

        # Working directory
        if cwd:
            cmd.extend(["-C", str(cwd)])

        # Prompt
        if prompt:
            cmd.append(prompt)

        self._call_count += 1

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=str(cwd),
            )
            duration_ms = int((time.time() - started) * 1000)
            stdout = result.stdout
            stderr = result.stderr

            # Parse JSONL output — last line is typically the final result
            parsed_output: dict[str, Any] = {
                "stdout": stdout[-10000:], "stderr": stderr[-2000:],
                "mode": self._MODE,
            }
            completion_detected: bool = result.returncode == 0

            if stdout.strip():
                # Parse JSONL: each line is a JSON event
                lines = stdout.strip().split("\n")
                events = []
                for line in lines:
                    try:
                        evt = json.loads(line)
                        events.append(evt)
                    except json.JSONDecodeError:
                        continue
                if events:
                    parsed_output["events"] = events
                    # Last event typically indicates completion
                    last = events[-1]
                    if isinstance(last, dict):
                        if last.get("type") in ("result", "done", "complete"):
                            completion_detected = True

            failure = _classify_failure(result.returncode, stderr, stdout)

            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=completion_detected and result.returncode == 0,
                failure_class=failure,
                output=parsed_output,
                duration_ms=duration_ms,
                next_action="complete" if completion_detected else "review",
            )

        except subprocess.TimeoutExpired:
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.WORKER_FAILURE,
                output={"error": f"codex timeout after {timeout}s", "mode": self._MODE},
                duration_ms=int(timeout * 1000),
            )
        except FileNotFoundError:
            return WorkerResult(
                worker_id=self.worker_id, mission_id=mission_id,
                success=False, failure_class=FailureClass.ENVIRONMENT_FAILURE,
                output={
                    "error": f"codex binary not found: {self._codex}",
                    "mode": self._MODE,
                },
            )

    def resume(self, session_id: str) -> WorkerResult:
        """Codex exec does not support session resume in 0.143.0."""
        return WorkerResult(
            worker_id=self.worker_id, mission_id=session_id,
            success=False, failure_class=FailureClass.WORKER_FAILURE,
            output={
                "error": "STATELESS_CODEX_WORKER: session resume not available in codex exec 0.143.0",
                "mode": self._MODE,
                "note": self._MODE_NOTE,
            },
        )

    def is_alive(self) -> bool:
        try:
            result = subprocess.run(
                [self._codex, "--version"], capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        alive = self.is_alive()
        version = ""
        if alive:
            try:
                v = subprocess.run(
                    [self._codex, "--version"], capture_output=True, text=True, timeout=5,
                )
                version = v.stdout.strip()
            except Exception:
                pass
        return {
            "status": "healthy" if alive else "unavailable",
            "binary": self._codex,
            "version": version,
            "mode": self._MODE,
            "mode_note": self._MODE_NOTE,
            "calls": self._call_count,
        }


# ═══════════════════════════════════════════════════════════════════
# Deterministic Fake Worker (for testing)
# ═══════════════════════════════════════════════════════════════════

class DeterministicFakeWorker:
    """Deterministic fake worker for testing — simulates Claude/Codex behavior."""

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
