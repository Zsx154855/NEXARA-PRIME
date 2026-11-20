import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import durable
import relay


NOW = dt.datetime(2026, 11, 9, 15, 0, 0, tzinfo=dt.timezone.utc)
RID = "nexara-durable-test-00001"


def request(ident=41, owner=relay.OWNER_ID, tool="nexara_bridge_state", args=None, age=0):
    issued = NOW - dt.timedelta(seconds=age + 1)
    stamp = durable.utc(issued)
    payload = dict(protocol=relay.PROTOCOL, request_id=RID, tool=tool, args=args or {},
                   issued_at=stamp, expires_at=durable.utc(issued + dt.timedelta(minutes=10)))
    return dict(id=ident, user=dict(id=owner, login=relay.OWNER), created_at=stamp,
                updated_at=stamp, body=relay.REQUEST_MARKER + "\n" + relay.json_canonical(payload))


class Mailbox:
    def __init__(self, rows):
        self.rows = {row["id"]: row for row in rows}
        self.calls = []
        self.posts = 0
        self.write_fault = None
        self.read_fault = False
        self.closed = False
        self.actor_id = relay.OWNER_ID

    def assert_open(self):
        if self.closed:
            raise relay.RelayError("issue_closed")

    def assert_actor(self):
        pass

    def comments(self, since=None):
        self.calls.append(since)
        if self.read_fault:
            raise relay.RelayError("network_unavailable")
        return list(self.rows.values())

    def comment(self, ident):
        try:
            return self.rows[ident]
        except KeyError:
            raise relay.GitHubResourceMissing("fixture_comment_deleted")

    def post(self, body):
        self.posts += 1
        if self.write_fault == "definitive":
            raise durable.PublishRejected("github_rejected")
        self.rows[51] = dict(id=51, user=dict(id=relay.OWNER_ID, login=relay.OWNER),
                            body=body, updated_at=durable.utc(NOW))
        if self.write_fault == "lost-response":
            raise relay.RelayError("network_unavailable")
        return self.rows[51]


class DurableTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.api = Mailbox([request()])
        self.invocations = []
        self.cfg = dict(owner=relay.OWNER, mcp_argv=["/fixture"], field_paths={})

    def worker(self, crash=None):
        def invoke(argv, tool):
            self.invocations.append(tool)
            if crash == "mcp":
                raise TimeoutError()
            return {"status": "PASS", "private_fixture": "stays local"}
        return durable.Controller(self.folder, self.api, self.cfg, now=lambda: NOW, invoke=invoke)

    def test_complete_persists_result_and_deduplicates_after_reopen(self):
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "COMPLETED")
            job = worker.job(RID)
            self.assertIn("stays local", job["raw_result"])
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "IDLE")
        self.assertEqual(len(self.invocations), 1)
        self.assertEqual(self.api.posts, 1)
        self.assertNotIn("private_fixture", self.api.rows[51]["body"])
        self.assertEqual(self.api.calls.count(None), 1)

    def test_proven_rejection_resumes_publish_only(self):
        self.api.write_fault = "definitive"
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "RESULT_STAGED")
        self.api.write_fault = None
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "COMPLETED")
        self.assertEqual(len(self.invocations), 1)
        self.assertEqual(self.api.posts, 2)

    def test_lost_post_response_reconciles_without_second_post(self):
        self.api.write_fault = "lost-response"
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "UNKNOWN_OUTCOME")
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "COMPLETED")
        self.assertEqual((len(self.invocations), self.api.posts), (1, 1))

    def test_mcp_timeout_is_quarantined_on_reopen(self):
        with self.worker("mcp") as worker:
            self.assertEqual(worker.tick(), "UNKNOWN_OUTCOME")
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "IDLE")
        self.assertEqual((len(self.invocations), self.api.posts), (1, 0))

    def test_rejects_expired_unauthorized_and_out_of_scope(self):
        for invalid in (request(age=600), request(owner=8), request(tool="shell"),
                        request(args={"path": "/private"})):
            self.api.rows = {41: invalid}
            with self.worker() as worker:
                self.assertEqual(worker.tick(), "IDLE")
        self.assertEqual(self.invocations, [])

    def test_network_read_failure_can_recover(self):
        with self.worker() as worker:
            self.api.read_fault = True
            with self.assertRaises(relay.RelayError):
                worker.tick()
            self.api.read_fault = False
            self.assertEqual(worker.tick(), "COMPLETED")

    def test_only_one_listener_owns_lease(self):
        with self.worker():
            with self.assertRaises(BlockingIOError):
                with self.worker():
                    self.fail("second worker entered")

    def test_changed_source_cannot_run(self):
        self.api.rows[41]["updated_at"] = durable.utc(NOW)
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "IDLE")
        self.assertEqual(self.invocations, [])

    def test_duplicate_comment_id_for_same_request_is_rejected(self):
        self.api.rows[42] = request(ident=42)
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "IDLE")
            self.assertEqual(worker.job(RID)["phase"], "REJECTED")
        self.assertEqual(self.invocations, [])

    def crash_child(self, boundary):
        child = Path(__file__).with_name("durable_crash_child.py")
        result = subprocess.run([sys.executable, "-B", str(child), str(self.folder), boundary],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 73, result.stderr.decode())

    def test_process_exit_in_mcp_does_not_replay(self):
        self.crash_child("mcp")
        with self.worker() as worker:
            self.assertEqual(worker.job(RID)["phase"], "QUARANTINED")
            self.assertEqual(worker.tick(), "IDLE")
        self.assertEqual((len(self.invocations), self.api.posts), (0, 0))

    def test_process_exit_after_remote_acceptance_reconciles(self):
        self.crash_child("post")
        response = json.loads((self.folder / "accepted.json").read_text())
        self.api.rows[response["id"]] = response
        with self.worker() as worker:
            self.assertEqual(worker.job(RID)["phase"], "UNKNOWN_OUTCOME")
            self.assertEqual(worker.tick(), "COMPLETED")
        self.assertEqual((len(self.invocations), self.api.posts), (0, 0))

    def test_process_exit_after_staging_can_only_publish(self):
        self.crash_child("staged")
        with self.worker() as worker:
            self.assertEqual(worker.job(RID)["phase"], "RESULT_STAGED")
            self.assertEqual(worker.tick(), "COMPLETED")
        self.assertEqual((len(self.invocations), self.api.posts), (0, 1))

    def test_stop_switch_and_resume_preserve_ledger(self):
        self.api.write_fault = "definitive"
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "RESULT_STAGED")
            stop = self.folder / "STOP"
            stop.touch()
            self.api.write_fault = None
            self.assertEqual(worker.tick(), "STOPPED")
            self.assertEqual(self.api.posts, 1)
            stop.unlink()
            self.assertEqual(worker.tick(), "COMPLETED")
        self.assertEqual(len(self.invocations), 1)

    def test_non_owner_cannot_spoof_receipt(self):
        body = relay.receipt_body(relay.redacted_receipt({"request_id": RID}, True, {}, {}))
        self.api.rows[52] = dict(id=52, user=dict(id=9, login="external"), body=body)
        with self.worker() as worker:
            self.assertEqual(worker.tick(), "COMPLETED")
            self.assertEqual(worker.receipt_ids(RID), [])
        self.assertEqual((len(self.invocations), self.api.posts), (1, 1))

    def test_deleted_source_is_terminal(self):
        with self.worker() as worker:
            worker.sync()
            del self.api.rows[41]
            self.assertEqual(worker.tick(), "REJECTED")
            self.assertEqual(worker.tick(), "IDLE")
        self.assertEqual((len(self.invocations), self.api.posts), (0, 0))

    def test_second_process_cannot_acquire_live_lease(self):
        with self.worker():
            self.assertFalse((self.folder / "accepted.json").exists())
            child = Path(__file__).with_name("durable_crash_child.py")
            result = subprocess.run([sys.executable, "-B", str(child), str(self.folder), "mcp"],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 75, result.stderr.decode())
            self.assertFalse((self.folder / "accepted.json").exists())
