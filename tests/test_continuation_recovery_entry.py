"""CONTINUATION-RELIABILITY-02: one-shot recovery entry.

Covers lock ownership/stale takeover, force protection, canonical paths,
completion verification, and next-task advancement.
"""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "scripts" / "continuation" / "recovery_entry.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("recovery_entry", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _checkpoint(
    tmp_path: Path,
    task_id: str = "task-1",
    *,
    tasks: dict | None = None,
    qa: dict | None = None,
) -> Path:
    path = tmp_path / "checkpoint.json"
    payload: dict = {"next_task": {"id": task_id, "prompt": "do the next task"}}
    if tasks is not None:
        payload["tasks"] = tasks
    if qa is not None:
        payload["qa"] = qa
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _stub(tmp_path: Path, returncode: int = 0, sleep: float = 0.0) -> Path:
    args_file = tmp_path / "dsh-args.json"
    script = tmp_path / "stub-dsh.sh"
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > {args_file}\n"
        f"sleep {sleep}\n"
        f"exit {returncode}\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _counting_stub(tmp_path: Path) -> tuple[Path, Path]:
    runs = tmp_path / "runs.log"
    script = tmp_path / "counting-dsh.sh"
    script.write_text(
        "#!/bin/sh\n"
        f"printf 'run\\n' >> {runs}\n"
        "sleep 0.4\n"
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script, runs


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_dry_run_prints_existing_dsh_command_without_lock(tmp_path):
    module = _load_module()
    checkpoint = _checkpoint(tmp_path)
    task = module.load_next_task(checkpoint)
    result = module.dispatch(task, tmp_path / "state", dsh_bin="dsh", execute=False)
    assert result["status"] == "planned"
    assert result["command"][:2] == ["dsh", "headless"]
    assert result["command"][2] == "do the next task"
    assert not (tmp_path / "state" / "task-task-1.lock").exists()


def test_success_requires_verification_not_completion(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    task = {"id": "task-1", "prompt": "do the next task"}
    result = module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    assert result["status"] == "awaiting_verification"
    assert result["returncode"] == 0
    lock = json.loads((tmp_path / "state" / "task-task-1.lock").read_text())
    assert lock["state"] == "awaiting_verification"
    assert lock["owner"]
    assert lock["host"] == socket.gethostname()


def test_duplicate_recovery_is_blocked_after_success(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    task = {"id": "task-1", "prompt": "do the next task"}
    module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    before = (tmp_path / "dsh-args.json").read_text()
    second = module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    assert second["status"] == "awaiting_verification"
    assert (tmp_path / "dsh-args.json").read_text() == before


def test_failure_can_be_retried(tmp_path):
    module = _load_module()
    failing = _stub(tmp_path, returncode=1)
    task = {"id": "task-2", "prompt": "retry me"}
    first = module.dispatch(task, tmp_path / "state", dsh_bin=str(failing), execute=True)
    assert first["status"] == "failed"
    assert first["returncode"] == 1
    second = module.dispatch(task, tmp_path / "state", dsh_bin=str(failing), execute=True)
    assert second["status"] == "failed"


def test_stale_running_lock_from_killed_process_is_taken_over(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    state = tmp_path / "state"
    state.mkdir()
    dead = _dead_pid()
    (state / "task-task-3.lock").write_text(json.dumps({
        "version": 2, "state": "running", "pid": dead,
        "host": socket.gethostname(), "owner": "dead-owner",
    }), encoding="utf-8")
    result = module.dispatch({"id": "task-3", "prompt": "x"}, state,
                             dsh_bin=str(stub), execute=True)
    assert result["status"] == "awaiting_verification"
    lock = json.loads((state / "task-task-3.lock").read_text())
    assert lock["owner"] != "dead-owner"
    assert lock["previous_owner"] == "dead-owner"


def test_force_never_displaces_live_owner(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-task-8.lock").write_text(json.dumps({
        "version": 2, "state": "running", "pid": os.getpid(),
        "host": socket.gethostname(), "owner": "live-owner",
    }), encoding="utf-8")
    result = module.dispatch({"id": "task-8", "prompt": "x"}, state,
                             dsh_bin=str(stub), execute=True, force=True)
    assert result["status"] == "already_running"
    assert not (tmp_path / "dsh-args.json").exists()
    lock = json.loads((state / "task-task-8.lock").read_text())
    assert lock["owner"] == "live-owner"


def test_cli_rejects_unsafe_task_id_without_traceback(tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps({"next_task": {"id": "../evil", "prompt": "x"}}), encoding="utf-8"
    )
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(checkpoint), "--state-dir", str(tmp_path / "state")],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 2
    assert "recovery_entry_error" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_force_can_rerun_done_lock(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path)
    task = {"id": "task-7", "prompt": "x"}
    module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    forced = module.dispatch(
        task, tmp_path / "state", dsh_bin=str(stub), execute=True, force=True
    )
    assert forced["status"] == "awaiting_verification"


def test_corrupted_lock_is_reported_not_overwritten(tmp_path):
    module = _load_module()
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-task-4.lock").write_text("{broken", encoding="utf-8")
    result = module.dispatch({"id": "task-4", "prompt": "x"}, state, execute=True)
    assert result["status"] == "invalid_lock"
    assert (state / "task-task-4.lock").read_text() == "{broken"


def test_session_id_is_forwarded(tmp_path):
    module = _load_module()
    command = module.plan_dispatch(
        {"id": "task-5", "prompt": "resume me"}, "dsh", session_id="sess-1"
    )
    assert command == ["dsh", "headless", "resume me", "--session-id", "sess-1"]


def test_missing_dsh_marks_failed_and_allows_retry(tmp_path):
    module = _load_module()
    task = {"id": "task-6", "prompt": "x"}
    result = module.dispatch(
        task, tmp_path / "state", dsh_bin=str(tmp_path / "missing-dsh"), execute=True
    )
    assert result["status"] == "failed"
    assert result["error"] in {"FileNotFoundError", "PermissionError"}
    retry = module.dispatch(
        task, tmp_path / "state", dsh_bin=str(_stub(tmp_path)), execute=True
    )
    assert retry["status"] == "awaiting_verification"


def test_canonical_state_dir_is_checkpoint_relative(tmp_path):
    module = _load_module()
    checkpoint, state = module.canonical_paths(tmp_path / "checkpoint.json", None)
    assert checkpoint == (tmp_path / "checkpoint.json").resolve()
    assert state == (tmp_path / ".continuation").resolve()
    _, relative = module.canonical_paths(tmp_path / "checkpoint.json", "locks")
    assert relative == (tmp_path / "locks").resolve()


def test_cli_uses_same_state_from_a_different_cwd(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    nested = tmp_path / "nested"
    nested.mkdir()
    checkpoint = _checkpoint(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(MODULE), "../checkpoint.json", "--execute", "--json",
         "--dsh-bin", str(stub)],
        cwd=nested, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "awaiting_verification"
    assert (tmp_path / ".continuation" / "task-task-1.lock").exists()


def test_verify_requires_completed_evidence_and_qa(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    state = tmp_path / "state"
    task = {"id": "task-1", "prompt": "do the next task"}
    module.dispatch(task, state, dsh_bin=str(stub), execute=True)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("done", encoding="utf-8")

    checkpoint = _checkpoint(tmp_path)
    assert module.verify_completion(checkpoint, "task-1", state)["status"] == "not_completed"

    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed", "evidence": [str(evidence)]},
    })
    assert module.verify_completion(checkpoint, "task-1", state)["status"] == "missing_qa"

    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed", "evidence": [str(evidence)], "qa": "passed"},
    })
    result = module.verify_completion(checkpoint, "task-1", state)
    assert result["status"] == "verified"
    lock = json.loads((state / "task-task-1.lock").read_text())
    assert lock["state"] == "done"
    assert lock["verification_evidence"] == [str(evidence)]


def test_verify_rejects_missing_or_absent_evidence(tmp_path):
    module = _load_module()
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-task-1.lock").write_text(json.dumps({
        "version": 2, "state": "awaiting_verification", "pid": os.getpid(),
        "host": socket.gethostname(), "owner": "o",
    }), encoding="utf-8")
    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed", "evidence": [], "qa": "passed"},
    })
    assert module.verify_completion(checkpoint, "task-1", state)["status"] == "missing_evidence"
    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed",
                   "evidence": [str(tmp_path / "nope.txt")], "qa": "passed"},
    })
    assert module.verify_completion(
        checkpoint, "task-1", state
    )["status"] == "missing_evidence_file"


def test_cli_blocks_dispatch_when_next_task_not_advanced(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    state = tmp_path / "state"
    module.dispatch({"id": "task-1", "prompt": "do the next task"}, state,
                    dsh_bin=str(stub), execute=True)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("done", encoding="utf-8")
    _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed", "evidence": [str(evidence)], "qa": "passed"},
    })
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(tmp_path / "checkpoint.json"),
         "--state-dir", str(state), "--verify", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "verified"

    before = (tmp_path / "dsh-args.json").read_text()
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(tmp_path / "checkpoint.json"),
         "--state-dir", str(state), "--execute", "--json", "--dsh-bin", str(stub)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 3, proc.stderr
    assert json.loads(proc.stdout)["status"] == "next_task_not_advanced"
    assert (tmp_path / "dsh-args.json").read_text() == before


def test_cli_advance_claims_new_next_task_only_after_verification(tmp_path):
    checkpoint = _checkpoint(tmp_path)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("done", encoding="utf-8")
    counter = tmp_path / "counter.txt"
    stub = tmp_path / "advancing-dsh.py"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib\n"
        f"checkpoint = pathlib.Path({str(checkpoint)!r})\n"
        f"counter = pathlib.Path({str(counter)!r})\n"
        f"evidence = {str(evidence)!r}\n"
        "n = int(counter.read_text()) + 1 if counter.exists() else 1\n"
        "counter.write_text(str(n))\n"
        "data = json.loads(checkpoint.read_text())\n"
        "data.setdefault('tasks', {})[f'task-{n}'] = {\n"
        "    'status': 'completed', 'evidence': [evidence], 'qa': 'passed'}\n"
        "data['next_task'] = {'id': f'task-{n + 1}', 'prompt': f'next {n + 1}'}\n"
        "checkpoint.write_text(json.dumps(data))\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(checkpoint), "--advance", "--max-tasks", "2",
         "--state-dir", str(tmp_path / "state"), "--dsh-bin", str(stub)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    results = json.loads(proc.stdout)
    statuses = [item["status"] for item in results]
    assert statuses == ["awaiting_verification", "verified",
                        "awaiting_verification", "verified"], results
    assert counter.read_text() == "2"
    assert json.loads(checkpoint.read_text())["next_task"]["id"] == "task-3"


def test_advance_stops_without_checkpoint_advance(tmp_path):
    checkpoint = _checkpoint(tmp_path)
    stub = _stub(tmp_path, returncode=0)
    state = tmp_path / "state"
    # Dispatch once and verify manually; checkpoint still points at the same task.
    module = _load_module()
    task = module.load_next_task(checkpoint)
    module.dispatch(task, state, dsh_bin=str(stub), execute=True)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("done", encoding="utf-8")
    _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed", "evidence": [str(evidence)], "qa": "passed"},
    })
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(checkpoint), "--verify", "--json",
         "--state-dir", str(state)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    before = (tmp_path / "dsh-args.json").read_text()
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(checkpoint), "--advance",
         "--state-dir", str(state), "--dsh-bin", str(stub)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 1
    results = json.loads(proc.stdout)
    assert results[0]["status"] == "next_task_not_advanced"
    assert (tmp_path / "dsh-args.json").read_text() == before


def test_sigkill_owner_lock_is_recovered(tmp_path):
    checkpoint = _checkpoint(tmp_path)
    slow = _stub(tmp_path, returncode=0, sleep=1.5)
    state = tmp_path / "state"
    proc = subprocess.Popen(
        [sys.executable, str(MODULE), str(checkpoint), "--execute", "--json",
         "--state-dir", str(state), "--dsh-bin", str(slow)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    lock_path = state / "task-task-1.lock"
    deadline = time.time() + 10
    lock = {}
    while time.time() < deadline:
        if lock_path.exists():
            lock = json.loads(lock_path.read_text())
            if lock.get("pid") and lock.get("child_pid"):
                break
        time.sleep(0.05)
    assert lock.get("child_pid"), "dispatch never recorded its child"
    os.kill(lock["pid"], 9)
    proc.wait(timeout=10)
    assert not module_owner_alive(lock_path)

    module = _load_module()
    fast = _stub(tmp_path, returncode=0)
    result = module.dispatch({"id": "task-1", "prompt": "do the next task"}, state,
                             dsh_bin=str(fast), execute=True)
    assert result["status"] == "awaiting_verification"
    recovered = json.loads(lock_path.read_text())
    assert recovered["previous_owner"] != recovered["owner"]
    time.sleep(0.1)
    try:
        os.kill(lock["child_pid"], 0)
    except ProcessLookupError:
        pass
    else:
        raise AssertionError("orphaned dsh process was not terminated")


def module_owner_alive(lock_path: Path) -> bool:
    module = _load_module()
    return module._owner_alive(json.loads(lock_path.read_text()))


def test_blocked_next_task_is_not_dispatched(tmp_path):
    module = _load_module()
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"next_task": {
        "id": "blocked-1", "prompt": "needs approval",
        "status": "blocked", "reason": "requires user approval",
    }}), encoding="utf-8")
    stub = _stub(tmp_path, returncode=0)
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(checkpoint), "--execute", "--json",
         "--state-dir", str(tmp_path / "state"), "--dsh-bin", str(stub)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["status"] == "blocked"
    assert not (tmp_path / "dsh-args.json").exists()


def test_concurrent_execute_runs_exactly_once(tmp_path):
    stub, runs = _counting_stub(tmp_path)
    checkpoint = _checkpoint(tmp_path)
    state = tmp_path / "state"
    procs = [
        subprocess.Popen(
            [sys.executable, str(MODULE), str(checkpoint), "--state-dir", str(state),
             "--execute", "--json", "--dsh-bin", str(stub)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for _ in range(4)
    ]
    statuses = []
    for proc in procs:
        out, err = proc.communicate(timeout=30)
        payload = json.loads(out) if out.strip() else {"stderr": err}
        statuses.append(payload.get("status"))
    assert runs.read_text().splitlines() == ["run"]
    assert statuses.count("awaiting_verification") == 1
    assert all(
        status in {"awaiting_verification", "already_running"} for status in statuses
    ), statuses


def test_cli_status_reports_lock_state(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    state = tmp_path / "state"
    _checkpoint(tmp_path)
    module.dispatch({"id": "task-1", "prompt": "do the next task"}, state,
                    dsh_bin=str(stub), execute=True)
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(tmp_path / "checkpoint.json"),
         "--state-dir", str(state), "--status"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["task_id"] == "task-1"
    assert payload["lock"]["state"] == "awaiting_verification"
