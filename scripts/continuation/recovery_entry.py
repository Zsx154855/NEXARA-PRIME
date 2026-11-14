#!/usr/bin/env python3
"""Recovery entry: dispatch the checkpoint's next task once via the existing dsh CLI.

One-shot adapter, no scheduler and no daemon:
  checkpoint JSON {"next_task": {"id": "...", "prompt": "..."}}

Design (CONTINUATION-RELIABILITY-02):
- canonical absolute checkpoint/state paths (no per-cwd lock sets);
- the lock carries pid/host/owner token; a SIGKILLed owner is detected by pid
  liveness and taken over, while a live owner is never displaced (even by --force);
- dsh exit code is NOT task completion: success leaves the lock in
  awaiting_verification; `--verify` marks it done only when the checkpoint
  records status=completed, non-empty evidence, and (by default) QA pass;
- a completed task that is still the checkpoint's next_task is reported as
  next_task_not_advanced instead of being dispatched again.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_TASK_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


# The child must not execute DSH until its pid/pgid have been saved durably.
# If the dispatcher is SIGKILLed before granting the gate, its pipe closes
# and the unapproved child exits without running any tool or model command.
_GATE_CHILD = (
    "import os, sys\n"
    "fd = int(sys.argv[1])\n"
    "try:\n"
    "    permit = os.read(fd, 1)\n"
    "finally:\n"
    "    os.close(fd)\n"
    "if permit != b'1':\n"
    "    sys.exit(125)\n"
    "try:\n"
    "    os.execvp(sys.argv[2], sys.argv[2:])\n"
    "except OSError as exc:\n"
    "    os._exit(127 if getattr(exc, 'errno', None) == 2 else 126)\n"
)


def _spawn_gated(command: list[str]) -> tuple[subprocess.Popen, int]:
    """Start a new process group but hold DSH execution behind a parent pipe."""
    read_fd, write_fd = os.pipe()
    try:
        proc = subprocess.Popen(
            [sys.executable, "-c", _GATE_CHILD, str(read_fd), *command],
            pass_fds=(read_fd,),
            start_new_session=True,
        )
    except BaseException:
        os.close(write_fd)
        raise
    finally:
        os.close(read_fd)
    return proc, write_fd


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_paths(
    checkpoint_arg: str | Path, state_dir_arg: str | Path | None
) -> tuple[Path, Path]:
    checkpoint = Path(checkpoint_arg).expanduser().resolve()
    if state_dir_arg is None:
        state_dir = (checkpoint.parent / ".continuation").resolve()
    else:
        raw = Path(state_dir_arg).expanduser()
        state_dir = raw.resolve() if raw.is_absolute() else (checkpoint.parent / raw).resolve()
    return checkpoint, state_dir


def load_checkpoint(checkpoint_path: Path) -> dict[str, Any]:
    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("checkpoint_must_be_object")
    return data


def load_next_task(checkpoint_path: Path) -> dict[str, str]:
    data = load_checkpoint(checkpoint_path)
    task = data.get("next_task")
    if not isinstance(task, dict):
        raise ValueError("checkpoint_missing_next_task")
    task_id = str(task.get("id") or "")
    prompt = str(task.get("prompt") or "")
    if not _TASK_ID.fullmatch(task_id) or not prompt:
        raise ValueError("next_task_requires_safe_id_and_prompt")
    result = {"id": task_id, "prompt": prompt}
    status = str(task.get("status") or "")
    if status:
        result["status"] = status
        result["reason"] = str(task.get("reason") or "")
    return result


def task_digest(task: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(task, sort_keys=True).encode("utf-8")).hexdigest()


def plan_dispatch(
    task: dict[str, str], dsh_bin: str, session_id: str | None = None
) -> list[str]:
    command = [dsh_bin, "headless", task["prompt"]]
    if session_id:
        command.extend(["--session-id", session_id])
    return command


def _lock_path(state_dir: Path, task_id: str) -> Path:
    return state_dir / f"task-{task_id}.lock"


def _read_lock(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_lock(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _owner_alive(lock: dict[str, Any]) -> bool:
    if lock.get("host") != socket.gethostname():
        return True  # a remote owner cannot be probed locally: treat it as alive
    pid = lock.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_command(pid: int) -> str | None:
    try:
        result = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _is_expected_child(lock: dict[str, Any], pid: int) -> bool:
    """Guard against PID reuse: only kill a process that still runs our command."""
    expected = lock.get("command")
    if not isinstance(expected, list) or not expected:
        return False
    command_line = _process_command(pid)
    if not command_line:
        return False
    executable = str(expected[0])
    return executable in command_line or os.path.basename(executable) in command_line


def _terminate_orphan(lock: dict[str, Any]) -> bool:
    """Terminate the dsh process group left behind by a SIGKILLed dispatcher."""
    pid = lock.get("child_pid")
    pgid = lock.get("child_pgid")
    if not isinstance(pid, int) or not isinstance(pgid, int) or pid <= 0 or pgid <= 0:
        return False
    if pid == os.getpid():
        return False
    if not _is_expected_child(lock, pid):
        return False
    try:
        if os.getpgid(pid) != pgid:
            return False
    except ProcessLookupError:
        return False
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return True
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    return True


def _guarded(state_dir: Path, operation: Callable[[], Any]) -> Any:
    state_dir.mkdir(parents=True, exist_ok=True)
    guard = state_dir / ".lock.guard"
    with open(guard, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            return operation()
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def dispatch(
    task: dict[str, str],
    state_dir: Path,
    *,
    dsh_bin: str = "dsh",
    execute: bool = False,
    timeout_seconds: int = 1800,
    session_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if not _TASK_ID.fullmatch(task["id"]):
        raise ValueError("task_id_must_match_[A-Za-z0-9._-]{1,128}")
    if task.get("status") == "blocked":
        return {
            "status": "blocked",
            "task_id": task["id"],
            "reason": task.get("reason", ""),
        }
    digest = task_digest(task)
    lock_path = _lock_path(state_dir, task["id"])
    command = plan_dispatch(task, dsh_bin, session_id)
    plan = {
        "status": "planned",
        "task_id": task["id"],
        "digest": digest,
        "command": command,
    }
    if not execute:
        return plan

    def claim() -> tuple[str, dict[str, Any] | None]:
        if not lock_path.exists():
            existing = None
        else:
            existing = _read_lock(lock_path)
            if existing is None:
                return "invalid_lock", None
        if existing:
            state = existing.get("state")
            if state == "running":
                if _owner_alive(existing):
                    return "already_running", existing
                # dead owner: terminate its orphaned dsh before takeover
                _terminate_orphan(existing)
            elif state == "done" and not force:
                return "already_completed", existing
            elif state == "awaiting_verification" and not force:
                return "awaiting_verification", existing
            elif state == "failed":
                pass  # retry allowed without force
        payload = {
            "version": 2,
            "task_id": task["id"],
            "digest": digest,
            "state": "running",
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "owner": str(uuid.uuid4()),
            "started_at": _now(),
            "command": command,
            "previous_owner": existing.get("owner") if existing else None,
        }
        _write_lock(lock_path, payload)
        return "claimed", payload

    decision, payload = _guarded(state_dir, claim)
    if decision != "claimed":
        return {
            "status": decision,
            "task_id": task["id"],
            "lock": str(lock_path),
            "lock_state": (payload or {}).get("state"),
        }

    owner = payload["owner"]
    try:
        proc, gate_write = _spawn_gated(command)
    except (OSError, KeyboardInterrupt) as exc:
        error_name = type(exc).__name__

        def settle_spawn_failure() -> None:
            current = _read_lock(lock_path)
            if current and current.get("owner") == owner:
                current.update(state="failed", error=error_name, finished_at=_now())
                _write_lock(lock_path, current)

        _guarded(state_dir, settle_spawn_failure)
        return {
            "status": "failed",
            "task_id": task["id"],
            "returncode": None,
            "error": error_name,
            "lock": str(lock_path),
        }

    def record_child() -> bool:
        current = _read_lock(lock_path)
        if not current or current.get("owner") != owner:
            return False
        current.update(child_pid=proc.pid, child_pgid=os.getpgid(proc.pid))
        _write_lock(lock_path, current)
        return True

    # Persist ownership before allowing the child to exec DSH. A dispatcher
    # SIGKILL before this point closes gate_write; the child exits on EOF.
    registered = False
    release_error = None
    try:
        registered = _guarded(state_dir, record_child)
        if registered:
            os.write(gate_write, b"1")
    except (OSError, KeyboardInterrupt) as exc:
        release_error = type(exc).__name__
    finally:
        os.close(gate_write)

    if not registered or release_error:
        # EOF terminates the still-gated child without running the command.
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _terminate_orphan({"child_pid": proc.pid, "child_pgid": proc.pid})
        if release_error:
            def settle_gate_failure() -> None:
                current = _read_lock(lock_path)
                if current and current.get("owner") == owner:
                    current.update(state="failed", error=release_error, finished_at=_now())
                    _write_lock(lock_path, current)
            _guarded(state_dir, settle_gate_failure)
        return {
            "status": "failed" if release_error else "owner_lost",
            "task_id": task["id"],
            "returncode": None,
            "error": release_error,
            "lock": str(lock_path),
        }

    try:
        returncode: int | None = proc.wait(timeout=timeout_seconds)
        error = None
        if returncode == 127:
            error = "FileNotFoundError"
        elif returncode == 126:
            error = "PermissionError"
    except subprocess.TimeoutExpired:
        _terminate_orphan({"child_pid": proc.pid, "child_pgid": os.getpgid(proc.pid)})
        returncode, error = 124, "timeout"
    except (OSError, KeyboardInterrupt) as exc:
        _terminate_orphan({"child_pid": proc.pid, "child_pgid": os.getpgid(proc.pid)})
        returncode, error = None, type(exc).__name__

    def settle() -> str:
        current = _read_lock(lock_path)
        if not current or current.get("owner") != owner:
            return "owner_lost"
        if returncode == 0:
            current.update(
                state="awaiting_verification",
                returncode=0,
                finished_at=_now(),
                evidence_required=True,
            )
        else:
            current.update(
                state="failed",
                returncode=returncode,
                error=error,
                finished_at=_now(),
            )
        _write_lock(lock_path, current)
        return current["state"]

    state = _guarded(state_dir, settle)
    return {
        "status": state,
        "task_id": task["id"],
        "returncode": returncode,
        "error": error,
        "lock": str(lock_path),
    }


def verify_completion(
    checkpoint_path: Path,
    task_id: str,
    state_dir: Path,
    *,
    require_qa: bool = True,
) -> dict[str, Any]:
    if not _TASK_ID.fullmatch(task_id):
        raise ValueError("task_id_must_match_[A-Za-z0-9._-]{1,128}")
    data = load_checkpoint(checkpoint_path)
    record = (data.get("tasks") or {}).get(task_id) or (data.get("completed") or {}).get(task_id)
    if not isinstance(record, dict) or record.get("status") != "completed":
        return {"status": "not_completed", "task_id": task_id}
    evidence = record.get("evidence") or []
    if not isinstance(evidence, list) or not any(str(item).strip() for item in evidence):
        return {"status": "missing_evidence", "task_id": task_id}
    path_like = [
        item for item in evidence
        if isinstance(item, str) and ("/" in item or item.startswith("."))
    ]
    if path_like and not any(Path(item).expanduser().exists() for item in path_like):
        return {"status": "missing_evidence_file", "task_id": task_id}
    if require_qa:
        qa = record.get("qa") or (data.get("qa") or {}).get(task_id)
        qa_status = qa.get("status") if isinstance(qa, dict) else qa
        if qa_status not in {"passed", "approved", "pass"}:
            return {"status": "missing_qa", "task_id": task_id}

    def mark() -> dict[str, Any]:
        lock_path = _lock_path(state_dir, task_id)
        lock = _read_lock(lock_path)
        if not lock:
            return {"status": "lock_missing", "task_id": task_id}
        if lock.get("state") == "done":
            return {"status": "already_verified", "task_id": task_id}
        if lock.get("state") != "awaiting_verification":
            return {"status": "not_awaiting_verification", "task_id": task_id}
        lock.update(
            state="done",
            verified_at=_now(),
            verification_evidence=evidence,
            qa_status="passed" if require_qa else "not_required",
        )
        _write_lock(lock_path, lock)
        return {"status": "verified", "task_id": task_id, "evidence": evidence}

    return _guarded(state_dir, mark)


def _next_task_not_advanced(checkpoint: dict[str, Any], state_dir: Path, task_id: str) -> bool:
    next_task = checkpoint.get("next_task") or {}
    if str(next_task.get("id") or "") != task_id:
        return False
    lock = _read_lock(_lock_path(state_dir, task_id))
    return bool(lock and lock.get("state") == "done")


def advance(
    checkpoint_path: Path,
    state_dir: Path,
    *,
    dsh_bin: str = "dsh",
    max_tasks: int = 3,
    timeout_seconds: int = 1800,
    session_id: str | None = None,
    require_qa: bool = True,
) -> list[dict[str, Any]]:
    """Dispatch+verify tasks until the checkpoint stops advancing.

    A task advances only when verification passes AND the checkpoint's
    next_task id has changed. max_tasks bounds a single invocation; there is
    still no daemon.
    """
    results: list[dict[str, Any]] = []
    for _ in range(max(1, max_tasks)):
        data = load_checkpoint(checkpoint_path)
        task = load_next_task(checkpoint_path)
        if _next_task_not_advanced(data, state_dir, task["id"]):
            results.append({"status": "next_task_not_advanced", "task_id": task["id"]})
            break
        dispatched = dispatch(
            task, state_dir, dsh_bin=dsh_bin, execute=True,
            timeout_seconds=timeout_seconds, session_id=session_id,
        )
        results.append(dispatched)
        if dispatched["status"] != "awaiting_verification":
            break
        verified = verify_completion(
            checkpoint_path, task["id"], state_dir, require_qa=require_qa
        )
        results.append(verified)
        if verified["status"] not in {"verified", "already_verified"}:
            break
        updated = load_checkpoint(checkpoint_path)
        updated_next = str((updated.get("next_task") or {}).get("id") or "")
        if updated_next == task["id"]:
            results.append({"status": "next_task_not_advanced", "task_id": task["id"]})
            break
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--state-dir", type=Path, default=None,
                        help="default: <checkpoint_dir>/.continuation (canonical absolute)")
    parser.add_argument("--dsh-bin", default="dsh")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--advance", action="store_true",
                        help="dispatch+verify until checkpoint stops advancing")
    parser.add_argument("--max-tasks", type=int, default=3)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-require-qa", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        checkpoint, state_dir = canonical_paths(args.checkpoint, args.state_dir)
        data = load_checkpoint(checkpoint)
        task = load_next_task(checkpoint)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"recovery_entry_error: {exc}", file=sys.stderr)
        return 2

    if args.status:
        target = args.task_id or task["id"]
        lock = _read_lock(_lock_path(state_dir, target))
        print(json.dumps(
            {"task_id": target, "lock": lock, "state_dir": str(state_dir)},
            indent=2, sort_keys=True,
        ))
        return 0

    if args.verify:
        target = args.task_id or task["id"]
        result = verify_completion(
            checkpoint, target, state_dir, require_qa=not args.no_require_qa
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] in {"verified", "already_verified"} else 1

    if args.advance:
        results = advance(
            checkpoint, state_dir, dsh_bin=args.dsh_bin, max_tasks=args.max_tasks,
            session_id=args.session_id, require_qa=not args.no_require_qa,
        )
        print(json.dumps(results, indent=2, sort_keys=True))
        last = results[-1] if results else {"status": "no_task"}
        return 0 if last["status"] in {"verified", "already_verified"} else 1

    if args.execute and _next_task_not_advanced(data, state_dir, task["id"]):
        result = {"status": "next_task_not_advanced", "task_id": task["id"]}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 3

    try:
        result = dispatch(
            task, state_dir, dsh_bin=args.dsh_bin, execute=args.execute,
            session_id=args.session_id, force=args.force,
        )
    except ValueError as exc:
        print(f"recovery_entry_error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result.get("command", result))
    return 0 if result["status"] in {"planned", "awaiting_verification", "already_completed"} else 1


if __name__ == "__main__":
    sys.exit(main())
