import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import relay
from p2_missions import task_from
from p3_private import Admission, Denied, Identity, verify_receipt
from p3_control import freeze


def sign(path, namespace, value):
    return subprocess.check_output(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(path), "-n", namespace],
        input=relay.json_canonical(value).encode(), stderr=subprocess.DEVNULL, env={},
    ).decode()


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.key = self.root / "fixture-sign"
        subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)],
                       env={}, check=True, timeout=10)
        public = " ".join(self.key.with_suffix(".pub").read_text().split()[:2])
        self.now = dt.datetime(2026, 11, 9, 14, tzinfo=dt.timezone.utc)
        self.head = "a" * 40
        self.workspace = "b" * 64
        self.task = dict(mission_id="mission-01", task_id="task-01", idempotency_key="idem-01",
                         operation="repo.apply_patch", arguments={"path": "test.py", "content": "ok",
                                                                  "old_sha256": "c" * 64})
        self.contract = dict(contract_id="contract-01", mission_id="mission-01", requester_uid=os.getuid(),
                             requester="worker-fixture", approver="master-fixture", revision=1,
                             workspace=self.workspace, head=self.head, allowed_operations=["repo.apply_patch"],
                             expires_at="2026-11-09T14:05:00Z", status="active", max_seconds=12,
                             budget_microusd=0, test_id="fixed-test")
        self.file = self.root / "contract.json"
        relay.atomic_store(self.file, self.contract)
        self.grant = dict(approval_id="approval-01", principal="master-fixture",
                          task_sha256=task_from(self.task, self.workspace).request_hash,
                          contract_sha256=relay.json_canonical(self.contract), issued_at="2026-11-09T13:59:58Z")
        from durable import digest
        self.grant["contract_sha256"] = digest(self.grant["contract_sha256"])
        worker_key = self.root / "fixture-worker"
        subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(worker_key)],
                       env={}, check=True, timeout=10)
        worker_public = " ".join(worker_key.with_suffix(".pub").read_text().split()[:2])
        self.identities = {"master-fixture": Identity(public, "approver"),
                           "worker-fixture": Identity(worker_public, "worker")}

    def gate(self):
        return Admission(self.file, self.identities, self.workspace, lambda: self.head, now=lambda: self.now)

    def request(self, grant=None):
        grant = self.grant.copy() if grant is None else grant
        return {"task": self.task.copy(), "grant": grant,
                "signature": sign(self.key, "nexara-p3-approval", grant)}

    def test_signed_grant_matches_pinned_role_task_head_and_contract(self):
        req = self.request()
        self.assertEqual(self.gate().check(req, os.getuid())["approval_id"], "approval-01")
        for change in (dict(req, actor="master-fixture"), dict(req, signature="forged"),
                       dict(req, task=dict(self.task, task_id="other-01"))):
            with self.assertRaises(Denied):
                self.gate().check(change, os.getuid())
        with self.assertRaises(Denied):
            self.gate().check(req, os.getuid() + 1)

    def test_worker_signature_and_revoked_contract_cannot_authorize(self):
        req = self.request()
        with self.assertRaises(Denied):
            self.gate().check(self.request(dict(self.grant, principal="worker-fixture")), os.getuid())
        relay.atomic_store(self.file, dict(self.contract, revision=2, status="revoked"))
        with self.assertRaises(Denied):
            self.gate().check(req, os.getuid())

    def test_git_head_change_and_expiry_are_rejected(self):
        req = self.request()
        self.head = "d" * 40
        with self.assertRaises(Denied):
            self.gate().check(req, os.getuid())
        self.head = self.contract["head"]
        self.now += dt.timedelta(minutes=10)
        with self.assertRaises(Denied):
            self.gate().check(req, os.getuid())

    def test_receipt_integrity_rejects_tampering_and_wrong_role(self):
        from p3_private import receipt_envelope
        evidence = {"scope": "local", "approval_sha256": "d" * 64, "test_exit": 0}
        envelope = receipt_envelope(evidence, "audit-fixture")
        envelope["signature"] = sign(self.key, "nexara-p3-receipt", envelope)
        pub = self.identities["master-fixture"].public_key
        self.assertEqual(verify_receipt(envelope, {"audit-fixture": Identity(pub, "attester")}), evidence)
        mutated = json.loads(json.dumps(envelope))
        mutated["evidence"]["test_exit"] = 1
        for candidate, role in ((mutated, "attester"), (envelope, "worker")):
            with self.assertRaises(Denied):
                verify_receipt(candidate, {"audit-fixture": Identity(pub, role)})

    def test_freeze_cannot_touch_a_p2_ledger(self):
        lane = self.root / "p2-missions.sqlite3"
        lane.touch(mode=0o600)
        with self.assertRaises(relay.RelayError):
            freeze(self.root)
        self.assertFalse((self.root / "STOP").exists())
