import datetime as dt
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

import durable
import relay
import test_durable


class BoundaryTests(unittest.TestCase):
    def test_github_output_and_wait_are_bounded_while_child_runs(self):
        with self.assertRaisesRegex(relay.RelayError, "github_response_limit"):
            relay.bounded_github_output([sys.executable, "-c", "print('x' * 10000)"], b"", limit=4096)
        with self.assertRaisesRegex(relay.RelayError, "github_request_timeout"):
            relay.bounded_github_output([sys.executable, "-c", "import time; time.sleep(2)"], b"", timeout=.1)

    def test_github_write_capability_rejects_other_routes_and_data(self):
        api = object.__new__(relay.GitHubAPI)
        api.base = f"repos/{relay.REPO}/issues/{relay.ISSUE}/comments"
        receipt = relay.receipt_body(relay.redacted_receipt({"request_id": "nexara-p1-test-001"}, True, {}, {}))
        for endpoint, data in (
            (api.base.replace("/comments", ""), {"body": receipt}),
            (f"repos/{relay.REPO}/actions/workflows/1/dispatches", {"body": receipt}),
            (f"repos/{relay.REPO}/contents/README.md", {"body": receipt}),
            (api.base, {"body": receipt, "extra": True}),
            (api.base, {"body": receipt + "\nprivate log"}),
            (api.base + "?page=999", None),
        ):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(relay.RelayError, "github_policy"):
                api.request(endpoint, data)

    def test_github_environment_drops_secrets_and_overrides(self):
        with patch.dict(os.environ, {"CUSTOM_SECRET": "fixture", "GH_TOKEN": "fixture",
                                     "HOME": "/wrong", "HTTPS_PROXY": "fixture"}, clear=True):
            env = relay.github_environment()
        self.assertNotEqual(env["HOME"], "/wrong")
        self.assertFalse({"CUSTOM_SECRET", "GH_TOKEN", "HTTPS_PROXY"} & set(env))

    def test_snapshot_rejects_symlink_stale_and_unknown_fields(self):
        import snapshot

        now = dt.datetime(2026, 11, 9, 15, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp).resolve()
            row = snapshot.create({"nexara_bridge_state": {"status": "PASS", "known_job_inflight": True,
                                                           "receipt_persisted": False, "local": "secret"}}, now)
            path = folder / snapshot.NAME
            relay.atomic_store(path, row)
            self.assertNotIn("secret", path.read_text())
            self.assertEqual(snapshot.read(folder, os.getuid(), now)["nexara_bridge_state"]["status"], "PASS")
            with self.assertRaises(relay.RelayError):
                snapshot.read(folder, os.getuid(), now + dt.timedelta(seconds=121))
            row["tools"]["nexara_bridge_state"]["unapproved"] = True
            relay.atomic_store(path, row)
            with self.assertRaises(relay.RelayError):
                snapshot.read(folder, os.getuid(), now)
            path.rename(folder / "other.json")
            path.symlink_to(folder / "other.json")
            with self.assertRaises((relay.RelayError, OSError)):
                snapshot.read(folder, os.getuid(), now)

    def test_hourly_mcp_budget_leaves_validated_work_unexecuted(self):
        fixture = test_durable.DurableTest("test_complete_persists_result_and_deduplicates_after_reopen")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with fixture.worker() as worker:
            with worker.db:
                for _ in range(durable.MAX_MCP_PER_HOUR):
                    worker.event("old-validated-request", "EXECUTING")
            self.assertEqual(worker.tick(), "HOURLY_LIMIT")
        self.assertEqual(fixture.invocations, [])
        self.assertEqual(fixture.api.posts, 0)
