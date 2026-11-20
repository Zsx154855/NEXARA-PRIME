from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import multiprocessing
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

import relay


ISSUE_PATH = "repos/Zsx154855/NEXARA-PRIME/issues/56"
COMMENTS_PATH = ISSUE_PATH + "/comments"
ISSUE_URL = "https://api.github.com/" + ISSUE_PATH
SOURCE_PATH = "repos/Zsx154855/NEXARA-PRIME/issues/comments/901"
OWNER = {"id": 170140270, "login": "Zsx154855"}
PUBLISHER = {"id": 734, "login": "fixture-broker"}
NOW = dt.datetime(2026, 11, 9, 15, 0, 10, tzinfo=dt.timezone.utc)
RID = "nexara-p2-fixture-001"
RECEIPT = {
    "request_id": RID, "tool_invoked": True, "bridge_job_inflight": False,
    "receipt_ready": "unknown", "manifest_present": True, "error_code": "NONE",
    "source": "local_mac_mcp_relay_v01",
}


class FixtureTransport:
    def __init__(self):
        self.source = {
            "id": 901, "issue_url": ISSUE_URL, "user": OWNER.copy(),
            "created_at": "2026-11-09T15:00:01Z", "updated_at": "2026-11-09T15:00:01Z",
            "body": relay.REQUEST_MARKER + "\n" + relay.json_canonical({
                "protocol": relay.PROTOCOL, "request_id": RID, "tool": "nexara_bridge_state",
                "args": {}, "issued_at": "2026-11-09T15:00:00Z", "expires_at": "2026-11-09T15:02:00Z",
            }),
            "unfiltered_fixture_field": "must not cross socket",
        }
        self.rows = []
        self.calls = []
        self.source_override = None
        self.lose_post = False
        self.open = True

    def request(self, method, path, payload, *, deadline, max_bytes):
        self.calls.append((method, path))
        if (method, path, payload) == ("GET", ISSUE_PATH, None):
            return {"number": 56, "state": "open" if self.open else "closed",
                    "repository_url": "https://api.github.com/repos/Zsx154855/NEXARA-PRIME"}
        if (method, path, payload) == ("GET", COMMENTS_PATH + "?per_page=100&page=1", None):
            return [self.source, *self.rows]
        if (method, path, payload) == ("GET", SOURCE_PATH, None):
            return self.source_override if self.source_override is not None else self.source
        if (method, path) == ("POST", COMMENTS_PATH):
            if self.lose_post:
                raise TimeoutError("fixture transport details must stay private")
            row = {"id": 902, "issue_url": ISSUE_URL, "user": PUBLISHER.copy(), "body": payload["body"]}
            self.rows.append(row)
            return row
        raise AssertionError("unexpected transport request")


def fixture_broker(socket_path, state_path, transport, worker_uid=None, timeout=1):
    from p2_broker import GitHubBroker

    return GitHubBroker(
        socket_path, state_path, transport, worker_uid=os.geteuid() if worker_uid is None else worker_uid,
        publisher=(PUBLISHER["login"], PUBLISHER["id"]), now=lambda: NOW, timeout=timeout,
    )


def child_fixture(socket_path, state_path, ready):
    with fixture_broker(socket_path, state_path, FixtureTransport()) as broker:
        ready.set()
        for _ in range(2):
            broker.serve_one()


@unittest.skipUnless(sys.platform == "darwin", "the broker authenticates with macOS getpeereid")
class BrokerTests(unittest.TestCase):
    def setUp(self):
        scratch = self.enterContext(tempfile.TemporaryDirectory(prefix="p2gb-", dir="/tmp"))
        self.state_path = Path(scratch).resolve()
        self.socket_path = self.state_path / "gh.sock"
        self.transport = FixtureTransport()

    @contextmanager
    def running(self, count, *, worker_uid=None, timeout=1):
        with fixture_broker(self.socket_path, self.state_path, self.transport, worker_uid, timeout) as broker:
            server = threading.Thread(target=lambda: [broker.serve_one() for _ in range(count)], daemon=True)
            server.start()
            try:
                yield
            finally:
                server.join(4)
                self.assertFalse(server.is_alive())

    def exchange(self, request):
        from p2_broker import broker_call

        return broker_call(self.socket_path, request, broker_uid=os.geteuid(), timeout=2)

    def raw_exchange(self, payload):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(self.socket_path))
            client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            return relay.strict_json(client.makefile("rb").read())

    def publication(self):
        row = self.exchange({"op": "read_requests"})["requests"][0]
        return {"op": "publish_receipt", "source_id": row["comment_id"],
                "source_sha256": row["source_sha256"], "receipt": RECEIPT.copy()}

    def test_separate_process_checks_kernel_peer_and_posts_only_fixed_receipt(self):
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        child = context.Process(target=child_fixture, args=(self.socket_path, self.state_path, ready))
        child.start()
        try:
            self.assertTrue(ready.wait(4))
            publication = self.publication()
            self.assertEqual(publication["source_id"], 901)
            self.assertEqual(self.exchange(publication), {"status": "published", "receipt_id": 902})
            child.join(4)
            self.assertEqual(child.exitcode, 0)
        finally:
            if child.is_alive():
                child.terminate()
                child.join()

    def test_read_projects_allowlisted_fields_and_rejects_unverified_owner(self):
        with self.running(2):
            result = self.exchange({"op": "read_requests"})
            row, = result["requests"]
            self.assertEqual(set(row), {"protocol", "request_id", "tool", "args", "issued_at",
                                        "expires_at", "comment_id", "source_sha256"})
            self.transport.source["user"]["id"] += 1
            self.assertEqual(self.exchange({"op": "read_requests"}), {"requests": []})

    def test_expired_previous_use_of_same_request_id_blocks_new_source(self):
        stale = self.transport.source.copy()
        stale["id"] = 890
        stale["created_at"] = stale["updated_at"] = "2026-11-09T14:55:01Z"
        stale["body"] = stale["body"].replace("15:00:00", "14:55:00").replace("15:02:00", "14:57:00")
        self.transport.rows.append(stale)
        with self.running(1):
            self.assertEqual(self.exchange({"op": "read_requests"}), {"requests": []})

    def test_unknown_comment_id_never_reaches_upstream_direct_get(self):
        with self.running(1):
            reply = self.exchange({"op": "publish_receipt", "source_id": 999,
                                   "source_sha256": "a" * 64, "receipt": RECEIPT})
            self.assertEqual(reply, {"error": "source_unverified"})
        self.assertFalse(any(path.endswith("/999") for _, path in self.transport.calls))

    def test_peer_uid_mismatch_denies_access_before_transport(self):
        socket_dir = self.state_path / "share"
        socket_dir.mkdir(mode=0o710)
        self.socket_path = socket_dir / "gh.sock"
        with self.running(1, worker_uid=os.geteuid() + 1):
            self.assertEqual(self.exchange({"op": "read_requests"}), {"error": "peer_denied"})
        self.assertEqual(self.transport.calls, [])

    def test_broker_rejects_state_under_replaceable_ancestor(self):
        from p2_broker import BrokerError

        shared = self.state_path / "shared"
        shared.mkdir()
        shared.chmod(0o777)
        state = shared / "state"
        state.mkdir(mode=0o700)
        with self.assertRaisesRegex(BrokerError, "broker_directory_unverified"):
            with fixture_broker(self.socket_path, state, self.transport):
                pass

    def test_request_schema_rejects_raw_routes_and_duplicate_keys(self):
        with self.running(3):
            for request in ({"op": "GET", "path": ISSUE_PATH}, {"op": "read_requests", "issue": 57}):
                self.assertEqual(self.exchange(request), {"error": "invalid_request"})
            self.assertEqual(self.raw_exchange(b'{"op":"read_requests","op":"read_requests"}'),
                             {"error": "invalid_request"})
        self.assertEqual(self.transport.calls, [])

    def test_socket_byte_limit_and_deadline_prevent_transport_access(self):
        with self.running(2, timeout=.15):
            self.assertEqual(self.raw_exchange(b"x" * 4097), {"error": "invalid_request"})
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect(str(self.socket_path))
                client.sendall(b'{"op"')
                self.assertEqual(relay.strict_json(client.makefile("rb").read()), {"error": "deadline"})
        self.assertEqual(self.transport.calls, [])

    def test_publish_rejects_edited_expired_or_wrong_issue_source_and_nonreceipt(self):
        with self.running(6):
            publication = self.publication()
            for key, value in (
                ("updated_at", "2026-11-09T15:00:02Z"),
                ("issue_url", ISSUE_URL.replace("/56", "/57")),
                ("body", self.transport.source["body"].replace("15:02:00", "15:00:09")),
            ):
                with self.subTest(key=key):
                    self.transport.source_override = {**self.transport.source, key: value}
                    self.assertEqual(self.exchange(publication), {"error": "source_unverified"})
            self.transport.source_override = None
            wrong_rid = {**publication, "receipt": {**RECEIPT, "request_id": "nexara-p2-other-001"}}
            self.assertEqual(self.exchange(wrong_rid), {"error": "source_unverified"})
            extra_field = {**publication, "receipt": {**RECEIPT, "message": "fixture"}}
            self.assertEqual(self.exchange(extra_field), {"error": "invalid_request"})
        self.assertNotIn(("POST", COMMENTS_PATH), self.transport.calls)

    def test_duplicate_preflight_accepts_canonical_existing_receipt_without_posting(self):
        with self.running(3):
            publication = self.publication()
            self.transport.rows.append({"id": 903, "issue_url": ISSUE_URL, "user": OWNER.copy(),
                                        "body": relay.receipt_body(RECEIPT)})
            self.assertEqual(self.exchange(publication), {"status": "legacy_owner_receipt", "receipt_id": 903})
            self.assertEqual(self.exchange({"op": "read_requests"}), {"requests": []})
        self.assertNotIn(("POST", COMMENTS_PATH), self.transport.calls)

    def test_lost_post_is_never_retried_after_broker_reopens(self):
        self.transport.lose_post = True
        with self.running(2):
            publication = self.publication()
            self.assertEqual(self.exchange(publication), {"error": "unknown_outcome"})
        self.transport.lose_post = False
        with self.running(1):
            self.assertEqual(self.exchange(publication), {"error": "unknown_outcome"})
        self.assertEqual(self.transport.calls.count(("POST", COMMENTS_PATH)), 1)
