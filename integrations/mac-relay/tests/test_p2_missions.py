from pathlib import Path
import time
import tempfile
import unittest

from durable import Controller
from p2_missions import LocalMissionController, MissionBlocked


class MissionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name).resolve()
        self.binding = "a" * 64
        self.calls = []
        self.allowed = True
        self.expires = time.monotonic() + 60
        self.payload = dict(mission_id="mission-01", task_id="task-01", idempotency_key="idem-01",
                            operation="files.write", arguments={"path": "fixture.txt", "content": "ok"})

    def approve(self, task):
        if not self.allowed:
            raise MissionBlocked("revoked")
        if time.monotonic() >= self.expires:
            raise MissionBlocked("expired")
        if task.workspace != self.binding:
            raise MissionBlocked("wrong_workspace")
        return "fixture-approval"

    def invoke(self, op, args):
        self.calls.append((op, args))
        return {"ok": True}

    def worker(self, invoke=None):
        return LocalMissionController(self.path, self.binding, self.approve, invoke or self.invoke)

    def test_reopen_and_replay_are_idempotent(self):
        with self.worker() as worker:
            self.assertEqual(worker.enqueue(self.payload), "QUEUED")
            self.assertEqual(worker.run("mission-01", "task-01"), "COMPLETED")
        with self.worker() as worker:
            self.assertEqual(worker.enqueue(self.payload), "COMPLETED")
            self.assertEqual(worker.run("mission-01", "task-01"), "COMPLETED")
            status = worker.status("mission-01", "task-01")
            self.assertEqual(status["epoch"], 1)
            self.assertEqual(len(status["evidence_sha256"]), 64)
        self.assertEqual(len(self.calls), 1)

    def test_revoked_after_enqueue_fails_closed(self):
        with self.worker() as worker:
            worker.enqueue(self.payload)
            self.allowed = False
            self.assertEqual(worker.run("mission-01", "task-01"), "BLOCKED")
        self.assertFalse(self.calls)

    def test_expired_and_rebound_workspaces_are_rejected_after_restart(self):
        with self.worker() as worker:
            worker.enqueue(self.payload)
        with LocalMissionController(self.path, "b" * 64, self.approve, self.invoke) as other:
            with self.assertRaisesRegex(MissionBlocked, "workspace_mismatch"):
                other.run("mission-01", "task-01")
        self.expires = time.monotonic()
        with self.worker() as worker:
            self.assertEqual(worker.run("mission-01", "task-01"), "BLOCKED")
        self.assertFalse(self.calls)

    def test_rechecks_revocation_after_committing_claim(self):
        lookups = []

        def approval(task):
            lookups.append(task.task_id)
            if len(lookups) == 3:
                raise MissionBlocked("revoked")
            return self.approve(task)

        with LocalMissionController(self.path, self.binding, approval, self.invoke) as worker:
            worker.enqueue(self.payload)
            self.assertEqual(worker.run("mission-01", "task-01"), "BLOCKED")
            self.assertEqual(worker.status("mission-01", "task-01")["epoch"], 1)
        self.assertFalse(self.calls)

    def test_stop_arriving_during_final_authorization_blocks_dispatch(self):
        lookups = []

        def approval(task):
            lookups.append(task.task_id)
            if len(lookups) == 3:
                (self.path / "STOP").touch()
            return self.approve(task)

        with LocalMissionController(self.path, self.binding, approval, self.invoke) as worker:
            worker.enqueue(self.payload)
            self.assertEqual(worker.run("mission-01", "task-01"), "STOPPED")
            self.assertEqual(worker.status("mission-01", "task-01")["phase"], "QUEUED")
        self.assertFalse(self.calls)

    def test_forged_actor_or_arbitrary_operation_rejected(self):
        with self.worker() as worker:
            with self.assertRaises(MissionBlocked):
                worker.enqueue(dict(self.payload, actor="master"))
            with self.assertRaises(MissionBlocked):
                worker.enqueue(dict(self.payload, operation="shell.exec"))

    def test_attempt_fences_conflicting_payload_and_cancel(self):
        with self.worker() as worker:
            worker.enqueue(self.payload)
            with self.assertRaises(MissionBlocked):
                worker.enqueue(dict(self.payload, arguments={"path": "another"}))
            self.assertEqual(worker.cancel("mission-01", "task-01"), "CANCELLED")
            self.assertEqual(worker.run("mission-01", "task-01"), "CANCELLED")
        self.assertFalse(self.calls)

    def test_reopen_after_interruption_keeps_unknown_outcome(self):
        def interrupt(*_):
            raise KeyboardInterrupt()

        with self.worker(interrupt) as worker:
            worker.enqueue(self.payload)
            with self.assertRaises(KeyboardInterrupt):
                worker.run("mission-01", "task-01")
        with self.worker() as worker:
            self.assertEqual(worker.run("mission-01", "task-01"), "UNKNOWN_OUTCOME")
        self.assertFalse(self.calls)

    def test_write_controller_does_not_open_or_recover_public_ledger(self):
        with Controller(self.path, None, {}) as public:
            with public.db:
                public.db.execute("""
                    INSERT INTO tasks(rid,source_id,source_hash,request,expires,phase)
                    VALUES ('public-unknown',1,'hash','{}','2026-11-09T15:00:00Z','EXECUTING')
                """)
        public_ledger = self.path / Controller.database_name
        before = public_ledger.read_bytes()
        with self.assertRaisesRegex(MissionBlocked, "public_lane_forbidden"):
            with self.worker():
                self.fail("public ledger opened")
        self.assertEqual(public_ledger.read_bytes(), before)
        self.assertFalse((self.path / LocalMissionController.database_name).exists())
