"""CONTINUOUS-EXECUTION-01: recovery-entry adapter (one-shot, no daemon)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "scripts" / "continuation" / "recovery_entry.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("recovery_entry", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _checkpoint(tmp_path: Path, task_id: str = "task-1") -> Path:
    path = tmp_path / "checkpoint.json"
    path.write_text(
        json.dumps({"next_task": {"id": task_id, "prompt": "do the next task"}}),
        encoding="utf-8",
    )
    return path


def _stub(tmp_path: Path, returncode: int = 0) -> Path:
    args_file = tmp_path / "dsh-args.json"
    script = tmp_path / "stub-dsh.sh"
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > {args_file}\n"
        f"exit {returncode}\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_dry_run_prints_existing_dsh_command_without_lock(tmp_path):
    module = _load_module()
    checkpoint = _checkpoint(tmp_path)
    task = module.load_next_task(checkpoint)
    result = module.dispatch(task, tmp_path / "state", dsh_bin="dsh", execute=False)
    assert result["status"] == "planned"
    assert result["command"][:2] == ["dsh", "headless"]
    assert result["command"][2] == "do the next task"
    assert not (tmp_path / "state" / "task-task-1.lock").exists()


def test_execute_runs_once_and_marks_done(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    task = {"id": "task-1", "prompt": "do the next task"}
    result = module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    assert result["status"] == "done"
    assert result["returncode"] == 0
    args = (tmp_path / "dsh-args.json").read_text().splitlines()
    assert args == ["headless", "do the next task"]
    lock = json.loads((tmp_path / "state" / "task-task-1.lock").read_text())
    assert lock["state"] == "done"


def test_duplicate_recovery_is_blocked_after_success(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path, returncode=0)
    task = {"id": "task-1", "prompt": "do the next task"}
    module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    before = (tmp_path / "dsh-args.json").read_text()
    second = module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    assert second["status"] == "already_completed"
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


def test_checkpoint_without_next_task_is_rejected(tmp_path):
    module = _load_module()
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps({"next_task": {}}), encoding="utf-8")
    try:
        module.load_next_task(path)
    except ValueError as exc:
        assert "next_task" in str(exc)
    else:
        raise AssertionError("missing next_task must be rejected")


def test_cli_dry_run_json(tmp_path):
    checkpoint = _checkpoint(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(checkpoint), "--json",
         "--state-dir", str(tmp_path / "state")],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "planned"
    assert payload["command"][:2] == ["dsh", "headless"]


def test_task_id_path_traversal_is_rejected(tmp_path):
    module = _load_module()
    try:
        module.dispatch({"id": "../evil", "prompt": "x"}, tmp_path / "state")
    except ValueError as exc:
        assert "task_id" in str(exc)
    else:
        raise AssertionError("unsafe task id must be rejected")


def test_running_lock_blocks_second_dispatch(tmp_path):
    module = _load_module()
    task = {"id": "task-3", "prompt": "x"}
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-task-3.lock").write_text(
        json.dumps({"state": "running", "digest": module.task_digest(task)}),
        encoding="utf-8",
    )
    result = module.dispatch(task, state, dsh_bin="dsh", execute=True)
    assert result["status"] == "already_running"


def test_corrupted_lock_is_reported_not_crashed(tmp_path):
    module = _load_module()
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-task-4.lock").write_text("{broken", encoding="utf-8")
    result = module.dispatch({"id": "task-4", "prompt": "x"}, state)
    assert result["status"] == "invalid_lock"


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
    assert retry["status"] == "done"


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


def test_force_clears_done_lock(tmp_path):
    module = _load_module()
    stub = _stub(tmp_path)
    task = {"id": "task-7", "prompt": "x"}
    module.dispatch(task, tmp_path / "state", dsh_bin=str(stub), execute=True)
    forced = module.dispatch(
        task, tmp_path / "state", dsh_bin=str(stub), execute=True, force=True
    )
    assert forced["status"] == "done"
