"""NAEOS actual subprocess double-task checkpoints, no Mock Worker.

These tests run safe local Python scripts and temporary SQLite only.
No permanent worker service, cross-device recovery or production queue.
"""

import base64
import fcntl
import hashlib
import json

import pytest

from nexara_prime.brain.runtime.continuous_worker import (
    ContinuousLocalWorker, LocalWorkerTask,
)
from nexara_prime.brain.runtime.persistent_runtime import StateManager


class EvidenceDouble:
    def __init__(self, *, valid=True):
        self.records = {}
        self.valid = valid

    def add(self, mid, kind, title, content, trace, **kw):
        from types import SimpleNamespace
        eid = f"ev-{len(self.records)+1}"
        r = SimpleNamespace(evidence_id=eid, mission_id=mid, kind=kind, content=content, task_id=kw["task_id"])
        self.records[eid] = r
        return r

    def verify(self, eid):
        return self.valid

    def is_preverified_and_integrity_bound(self, eid):
        return self.valid

    def get_by_id(self, eid):
        return self.records[eid]


def setup(tmp_path, *, script_a=None, script_b=None, evidence=None, timeout=20):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "a.py").write_text(script_a or (
        "from pathlib import Path\nPath('done-a').write_text('A')\nprint('finished A')\n"
    ))
    (root / "b.py").write_text(script_b or (
        "from pathlib import Path\nassert Path('done-a').read_text() == 'A'\n"
        "Path('done-b').write_text('B')\nprint('finished B')\n"
    ))
    dbpath = str(tmp_path / "runtime.db")
    state = StateManager(dbpath)
    ev = evidence or EvidenceDouble()
    kw = dict(
        state=state, evidence_store=ev, workdir=root,
        mission_id="mission-naeos", project_id="nexara-prime",
        tasks=(LocalWorkerTask("task-A", "a.py"), LocalWorkerTask("task-B", "b.py")),
        timeout_s=timeout,
    )
    return ContinuousLocalWorker(**kw), kw, root, dbpath, ev


def test_two_real_os_worker_processes_run_sequentially(tmp_path):
    worker, kw, root, _, ev = setup(tmp_path)
    result = worker.run()
    assert result["status"] == "completed", result
    assert result["completed"] == ["task-A", "task-B"]
    assert (root / "done-b").read_text() == "B"
    assert len(ev.records) == 2
    for rec in ev.records.values():
        p = json.loads(rec.content)
        raw = base64.b64decode(p["stdout_b64"])
        assert hashlib.sha256(raw).hexdigest() == p["stdout_sha256"]
        assert p["exit_code"] == 0


def test_restart_recovers_checkpoint_and_runs_second_process(tmp_path):
    worker, kw, root, dbpath, ev = setup(tmp_path)
    first = worker.run(max_steps=1)
    assert first["completed"] == ["task-A"]
    assert first["status"] == "paused"
    assert not (root / "done-b").exists()
    restored_state = StateManager(dbpath)
    second = ContinuousLocalWorker(**{**kw, "state": restored_state}).run()
    assert second["status"] == "completed"
    assert second["completed"] == ["task-A", "task-B"]
    assert first["run_id"] == second["run_id"]


def test_worker_failure_blocks_dependent_task(tmp_path):
    worker, _, root, _, ev = setup(tmp_path, script_a="raise RuntimeError('broken task A')\n")
    result = worker.run()
    assert result["status"] == "failed"
    assert not (root / "done-b").exists()
    assert len(ev.records) == 1
    p = json.loads(next(iter(ev.records.values())).content)
    assert p["exit_code"] != 0


def test_missing_valid_evidence_stops_after_first_process(tmp_path):
    worker, _, root, _, ev = setup(tmp_path, evidence=EvidenceDouble(valid=False))
    result = worker.run()
    assert result["status"] == "blocked"
    assert result["error"] == "worker_evidence_unverified"
    assert not (root / "done-b").exists()


def test_timeout_stops_sequence(tmp_path):
    worker, _, root, _, _ = setup(
        tmp_path, script_a="import time\ntime.sleep(4)\n", timeout=1,
    )
    result = worker.run()
    assert result["status"] == "blocked"
    assert result["error"] == "worker_process_error:TimeoutExpired"
    assert not (root / "done-b").exists()


def test_replay_claim_never_executes_task_again(tmp_path):
    worker, kw, root, _, _ = setup(tmp_path)
    assert kw["state"].record_effect(
        "nexara-prime", "mission-naeos", "naeos_task", "task-A", "seed",
    )
    result = worker.run()
    assert result["status"] == "blocked"
    assert result["error"] == "idempotency_replay_requires_reconciliation"
    assert not (root / "done-a").exists()


def test_multiple_runs_after_completion_are_idempotent(tmp_path):
    worker, _, _, _, ev = setup(tmp_path)
    assert worker.run()["status"] == "completed"
    assert worker.run()["status"] == "completed"
    assert len(ev.records) == 2


def test_invalid_external_script_is_not_allowed(tmp_path):
    _, kw, root, _, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="worker_script_not_in_authorized_workspace"):
        ContinuousLocalWorker(**{
            **kw,
            "tasks": (
                LocalWorkerTask("task-A", "../outside.py"),
                LocalWorkerTask("task-B", "b.py"),
            ),
        })



def test_missing_workspace_script_fails_closed(tmp_path):
    _, kw, _, _, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="worker_script_not_in_authorized_workspace"):
        ContinuousLocalWorker(**{
            **kw,
            "tasks": (
                LocalWorkerTask("task-A", "does-not-exist.py"),
                LocalWorkerTask("task-B", "b.py"),
            ),
        })


def test_symlink_to_external_script_fails_closed(tmp_path):
    _, kw, root, _, _ = setup(tmp_path)
    outside = tmp_path / "external.py"
    outside.write_text("raise RuntimeError('should_not_execute')\n")
    (root / "linked.py").symlink_to(outside)
    with pytest.raises(ValueError, match="worker_script_not_in_authorized_workspace"):
        ContinuousLocalWorker(**{
            **kw,
            "tasks": (
                LocalWorkerTask("task-A", "linked.py"),
                LocalWorkerTask("task-B", "b.py"),
            ),
        })


def test_concurrent_process_lock_prevents_duplicate_claim(tmp_path):
    worker, _, root, _, _ = setup(tmp_path)
    with (root / ".naeos-worker.lock").open("a+b") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with pytest.raises(RuntimeError, match="worker_lease_busy"):
                worker.run()
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)



def test_revoked_task_a_receipt_blocks_task_b_on_restart(tmp_path):
    ev = EvidenceDouble(valid=True)
    worker, kw, root, _, _ = setup(tmp_path, evidence=ev)
    assert worker.run(max_steps=1)["status"] == "paused"
    ev.valid = False
    resumed = ContinuousLocalWorker(**kw).run()
    assert resumed["status"] == "blocked"
    assert resumed["error"] == "prior_receipt_unverified"
    assert not (root / "done-b").exists()


def test_tampered_prior_log_prevents_success_claim(tmp_path):
    worker, kw, root, _, ev = setup(tmp_path)
    assert worker.run()["status"] == "completed"
    ev.records["ev-1"].content = json.dumps({
        **json.loads(ev.records["ev-1"].content),
        "stdout_sha256": "0" * 64,
    })
    result = ContinuousLocalWorker(**kw).run()
    assert result["status"] == "blocked"
    assert result["error"] == "prior_receipt_unverified"


def test_crash_in_running_checkpoint_never_reexecutes_side_effect(tmp_path):
    worker, kw, root, _, _ = setup(
        tmp_path, script_a=(
            "from pathlib import Path\n"
            "p = Path('counter')\n"
            "p.write_text(str(int(p.read_text()) + 1 if p.exists() else 1))\n"
        ),
    )
    (root / "counter").write_text("1")
    cp = worker._load_or_create()
    cp.state = "running"
    kw["state"].save_checkpoint(cp)
    result = ContinuousLocalWorker(**kw).run()
    assert result["status"] == "blocked"
    assert result["error"] == "interrupted_execution_requires_reconciliation"
    assert (root / "counter").read_text() == "1"
    assert not (root / "done-b").exists()


def test_false_completed_checkpoint_cannot_claim_success(tmp_path):
    worker, kw, root, _, _ = setup(tmp_path)
    cp = worker._load_or_create()
    cp.state = "completed"
    kw["state"].save_checkpoint(cp)
    result = ContinuousLocalWorker(**kw).run()
    assert result["status"] == "blocked"
    assert result["error"] == "checkpoint_integrity_invalid"
    assert not (root / "done-a").exists()
