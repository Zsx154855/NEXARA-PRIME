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
    stub = _stub(tmp_path, returncode=0)
    nested = tmp_path / "nested"
    nested.mkdir()
    _checkpoint(tmp_path)
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
    assert module.verify_completion(
        checkpoint, "task-1", state
    )["status"] == "qa_identity_missing"

    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed", "evidence": [str(evidence)],
                   "qa": {"reviewer": "qa-bot", "verdict": "passed"}},
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
        "task-1": {"status": "completed", "evidence": [],
                   "qa": {"reviewer": "qa-bot", "verdict": "passed"}},
    })
    assert module.verify_completion(checkpoint, "task-1", state)["status"] == "missing_evidence"
    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed",
                   "evidence": [str(tmp_path / "nope.txt")],
                   "qa": {"reviewer": "qa-bot", "verdict": "passed"}},
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
        "task-1": {"status": "completed", "evidence": [str(evidence)],
                   "qa": {"reviewer": "qa-bot", "verdict": "passed"}},
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
        "    'status': 'completed', 'evidence': [evidence], "
        "'qa': {'reviewer': 'stub-qa', 'verdict': 'passed'}}\n"
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
        "task-1": {"status": "completed", "evidence": [str(evidence)],
                   "qa": {"reviewer": "qa-bot", "verdict": "passed"}},
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


def test_gate_pipe_closing_without_grant_never_runs_command(tmp_path):
    """A child never execs DSH unless its dispatcher explicitly permits it."""
    module = _load_module()
    marker = tmp_path / "unapproved-ran"
    command = [
        sys.executable, "-c",
        f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')",
    ]
    proc, permit_fd = module._spawn_gated(command)
    try:
        time.sleep(0.1)
        assert not marker.exists()
    finally:
        os.close(permit_fd)  # dispatcher died before persisting child pid
    assert proc.wait(timeout=5) == 125
    time.sleep(0.8)  # allow any erroneously ungated child to execute
    assert not marker.exists()


def test_sigkill_before_child_pid_recorded_does_not_run_dsh(tmp_path):
    """Real SIGKILL in the Popen -> lock-write gap cannot execute DSH."""
    _checkpoint(tmp_path)
    stub = _stub(tmp_path, returncode=0)
    state = tmp_path / "state"
    paused = tmp_path / "child_spawned_waiting_for_registration"
    launcher = (
        "import importlib.util, time\n"
        "from pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('gated_recovery', {str(MODULE)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "original = mod._guarded\n"
        "def pause_before_register(state_dir, operation):\n"
        "    if operation.__name__ == 'record_child':\n"
        f"        Path({str(paused)!r}).write_text('spawned')\n"
        "        time.sleep(30)\n"
        "    return original(state_dir, operation)\n"
        "mod._guarded = pause_before_register\n"
        f"mod.dispatch({{'id': 'task-1', 'prompt': 'do the next task'}}, "
        f"Path({str(state)!r}), dsh_bin={str(stub)!r}, execute=True)\n"
    )
    dispatcher = subprocess.Popen([sys.executable, "-c", launcher])
    try:
        deadline = time.monotonic() + 10
        while not paused.exists() and time.monotonic() < deadline:
            if dispatcher.poll() is not None:
                raise AssertionError("dispatcher exited before the injection point")
            time.sleep(0.02)
        assert paused.exists(), "dispatcher never reached post-spawn injection"
        assert not (tmp_path / "dsh-args.json").exists()
        os.kill(dispatcher.pid, 9)
        dispatcher.wait(timeout=5)
        time.sleep(0.3)
        assert not (tmp_path / "dsh-args.json").exists()
        # Reclaiming stale owner runs the task only once, not concurrently
        # with an orphan from the killed dispatcher.
        module = _load_module()
        outcome = module.dispatch(
            {"id": "task-1", "prompt": "do the next task"},
            state, dsh_bin=str(stub), execute=True,
        )
        assert outcome["status"] == "awaiting_verification"
        assert (tmp_path / "dsh-args.json").exists()
    finally:
        if dispatcher.poll() is None:
            dispatcher.kill()
            dispatcher.wait(timeout=5)


def test_pid_reuse_is_not_killed_on_takeover(tmp_path):
    module = _load_module()
    unrelated = subprocess.Popen(["sleep", "5"])
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-task-9.lock").write_text(json.dumps({
        "version": 2, "state": "running", "pid": 999999,
        "host": socket.gethostname(), "owner": "dead-owner",
        "child_pid": unrelated.pid, "child_pgid": os.getpgid(unrelated.pid),
        "command": ["/definitely-not-this-process"],
    }), encoding="utf-8")
    try:
        result = module.dispatch(
            {"id": "task-9", "prompt": "x"}, state,
            dsh_bin=str(_stub(tmp_path)), execute=True,
        )
        assert result["status"] == "awaiting_verification"
        assert unrelated.poll() is None, "unrelated PID was killed"
    finally:
        unrelated.kill()
        unrelated.wait(timeout=5)


def test_verify_requires_named_qa_and_hashes_evidence(tmp_path):
    module = _load_module()
    state = tmp_path / "state"
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("done", encoding="utf-8")
    import hashlib
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    (state / "task-task-1.lock").parent.mkdir(parents=True, exist_ok=True)
    (state / "task-task-1.lock").write_text(json.dumps({
        "version": 2, "state": "awaiting_verification", "pid": os.getpid(),
        "host": socket.gethostname(), "owner": "o",
    }), encoding="utf-8")
    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {
            "status": "completed",
            "evidence": [{"path": str(evidence), "sha256": digest}],
            "qa": {"reviewer": "independent-qa", "verdict": "approved"},
        },
    })
    result = module.verify_completion(checkpoint, "task-1", state)
    assert result["status"] == "verified"
    lock = json.loads((state / "task-task-1.lock").read_text())
    proof = lock["verification_proof"]
    assert proof["qa"]["reviewer"] == "independent-qa"
    assert proof["evidence"][0]["sha256"] == digest


def test_verify_rejects_qa_string_and_bad_hash(tmp_path):
    module = _load_module()
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-task-1.lock").write_text(json.dumps({
        "version": 2, "state": "awaiting_verification", "pid": os.getpid(),
        "host": socket.gethostname(), "owner": "o",
    }), encoding="utf-8")
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("done", encoding="utf-8")
    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {"status": "completed", "evidence": [str(evidence)], "qa": "passed"},
    })
    assert module.verify_completion(
        checkpoint, "task-1", state
    )["status"] == "qa_identity_missing"
    checkpoint = _checkpoint(tmp_path, tasks={
        "task-1": {
            "status": "completed",
            "evidence": [{"path": str(evidence), "sha256": "0" * 64}],
            "qa": {"reviewer": "qa", "verdict": "passed"},
        },
    })
    assert module.verify_completion(
        checkpoint, "task-1", state
    )["status"] == "evidence_hash_mismatch"
