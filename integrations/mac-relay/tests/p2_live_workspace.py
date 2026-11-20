"""Local Mac write and crash experiment with a disposable Git repository."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from p2_missions import LocalMissionController, MissionBlocked, task_from
from p2_workspace import FixtureCheck, Workspace


FILENAME = "test_fixture.py"
ORIGINAL = "EXPECTED = 'BTC'\n"
UPDATED = "EXPECTED = 'btc'\n"
FINAL = "EXPECTED = 'eth'\n"


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def task(number, operation, arguments):
    return dict(mission_id="p2-local-fixture", task_id=f"task-{number}",
                idempotency_key=f"fixture-idem-{number}", operation=operation, arguments=arguments)


def experiment(base, crash=False):
    worktree = base / "repo"
    ledger = base / "ledger"
    st = worktree.stat()
    workspace_id = sha(f"{worktree}:{st.st_dev}:{st.st_ino}")
    backend = Workspace(worktree, fixture_checks={"verify-fixed-source": FixtureCheck(FILENAME, sha(UPDATED))})
    inspect = task("inspect", "repo.inspect", {})
    patch = task("patch", "repo.apply_patch", {"path": FILENAME, "old_sha256": sha(ORIGINAL), "content": UPDATED})
    test = task("test", "test.run", {"command_id": "verify-fixed-source"})
    interrupted = task("interrupt", "repo.apply_patch", {
        "path": FILENAME, "old_sha256": sha(UPDATED), "content": FINAL})
    grants = {}
    now = dt.datetime.now(dt.timezone.utc)
    for payload in (inspect, patch, test, interrupted):
        approved = task_from(payload, workspace_id)
        grants[approved.task_id] = (approved.request_hash, now + dt.timedelta(seconds=60))

    def authorize(candidate):
        grant = grants.get(candidate.task_id)
        if (candidate.workspace != workspace_id or grant is None
                or candidate.request_hash != grant[0] or dt.datetime.now(dt.timezone.utc) >= grant[1]):
            raise MissionBlocked("fixture_grant_denied")
        return "local-fixture-approval"

    def run(operation, args):
        result = backend.execute(operation, args)
        if crash:
            os._exit(73)
        return result

    with LocalMissionController(ledger, workspace_id, authorize, run) as worker:
        if crash:
            worker.enqueue(interrupted)
            worker.run(interrupted["mission_id"], interrupted["task_id"])
            raise AssertionError("crash point not reached")
        results = {}
        for payload in (inspect, patch, test):
            if worker.enqueue(payload) == "QUEUED":
                assert worker.run(payload["mission_id"], payload["task_id"]) == "COMPLETED"
            status = worker.status(payload["mission_id"], payload["task_id"])
            assert status["phase"] == "COMPLETED" and status["epoch"] == 1
            results[payload["task_id"]] = status["evidence_sha256"]
        try:
            worker.enqueue(task("unapproved", "files.write", {"path": "outside.txt", "content": "x"}))
        except MissionBlocked:
            pass
        else:
            raise AssertionError("task without approved scope was admitted")
        if (worktree / FILENAME).read_text() == FINAL:
            assert worker.run(interrupted["mission_id"], interrupted["task_id"]) == "UNKNOWN_OUTCOME"
            results["crash_phase"] = "UNKNOWN_OUTCOME"
        return results


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--crash-child":
        experiment(Path(sys.argv[2]), crash=True)
        return
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory).resolve()
        worktree = base / "repo"
        worktree.mkdir(mode=0o700)
        (base / "ledger").mkdir(mode=0o700)
        subprocess.run(["/usr/bin/git", "init", "--quiet", "--template=", str(worktree)],
                       env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1",
                            "GIT_CONFIG_GLOBAL": "/dev/null"}, check=True, timeout=10)
        (worktree / FILENAME).write_text(ORIGINAL)
        result = experiment(base)
        assert (worktree / FILENAME).read_text() == UPDATED
        child = subprocess.run([sys.executable, "-B", __file__, "--crash-child", str(base)],
                               capture_output=True, timeout=20)
        assert child.returncode == 73, child.stderr.decode()
        assert (worktree / FILENAME).read_text() == FINAL
        resumed = experiment(base)
        assert resumed["crash_phase"] == "UNKNOWN_OUTCOME" and (worktree / FILENAME).read_text() == FINAL
        assert {key: resumed[key] for key in result} == result
        print(json.dumps({"disposable_git_workspace": True, "fixture_authority": True,
                          "production_cab": "BLOCKED", "isolated_test": "PASS",
                          "evidence_hashes": result, "write_crash_recovery": "UNKNOWN_OUTCOME",
                          "reexecuted_unknown_write": False, "paid_model_api_calls": 0}))


if __name__ == "__main__":
    main()
