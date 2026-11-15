"""Exercise the private socket, real patch, independent checks and local signature."""

import datetime as dt
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay
from durable import digest, utc
from p2_broker import broker_call
from p2_missions import task_from
from p2_workspace import FixtureCheck, Workspace
from p3_control import freeze
from p3_private import Admission, Denied, Identity, PrivateMissionController, PrivateWrite, receipt_envelope, serve_one
from p3_private import verify_execution_evidence, verify_receipt, verify_receipt_bundle


NAME = "test_fixture.py"
BEFORE = "EXPECTED = 'BTC'\n"
AFTER = "EXPECTED = 'btc'\n"
TEST = "p3-fixture-check"


def sign(key, namespace, value):
    return subprocess.check_output(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace],
        input=relay.json_canonical(value).encode(), stderr=subprocess.DEVNULL, env={}, timeout=5,
    ).decode()


def ephemeral_key(path):
    subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
                   env={}, check=True, timeout=5)
    return " ".join(path.with_suffix(".pub").read_text().split()[:2])


def workspace(root):
    return Workspace(root, fixture_checks={TEST: FixtureCheck(NAME, digest(AFTER))})


def child(root, identities, ready):
    tree = workspace(root / "repo")
    admission = Admission(root / "authority" / "contract.json", identities, tree.binding(), tree.head)
    serve_one(root / "ipc" / "write.sock", PrivateWrite(root / "ledger", tree, admission), os.geteuid(),
              on_ready=ready.set)


def socket_request(root, identities, request):
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(target=child, args=(root, identities, ready))
    process.start()
    endpoint = root / "ipc" / "write.sock"
    try:
        assert ready.wait(4)
        result = broker_call(endpoint, request, broker_uid=os.geteuid(), timeout=10)
        process.join(4)
        assert process.exitcode == 0
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join()


def experiment(evidence_dir):
    bridge = Path.home() / ".nexara_mac_bridge_v04/state.json"
    bridge_sha = hashlib.sha256(bridge.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="p3-live-", dir="/tmp") as tmp:
        root = Path(tmp).resolve()
        for name in ("repo", "authority", "ledger", "ipc"):
            (root / name).mkdir(mode=0o700)
        repo = root / "repo"
        git_env = {"PATH": "/usr/bin:/bin", "HOME": str(root), "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_CONFIG_GLOBAL": "/dev/null"}
        for args in (("init", "--quiet", "--template="),):
            subprocess.run(["/usr/bin/git", *args], env=git_env, cwd=repo, check=True, timeout=5)
        (repo / NAME).write_text(BEFORE)
        subprocess.run(["/usr/bin/git", "add", "--", NAME], env=git_env, cwd=repo, check=True, timeout=5)
        subprocess.run(["/usr/bin/git", "-c", "user.name=P3 Fixture", "-c", "user.email=p3@example.invalid",
                        "commit", "-qm", "fixture baseline"], env=git_env, cwd=repo, check=True, timeout=5)
        authority = root / "authority"
        key = authority / "sign-approval"
        identities = {"master-fixture": Identity(ephemeral_key(key), "approver"),
                      "worker-fixture": Identity(ephemeral_key(authority / "worker-fixture"), "worker")}
        attester_key = authority / "sign-attestation"
        attester_public = ephemeral_key(attester_key)
        tree = workspace(repo)
        now = dt.datetime.now(dt.timezone.utc)
        contract = {
            "contract_id": "contract-p3-fixture", "mission_id": "mission-p3-fixture", "requester_uid": os.geteuid(),
            "requester": "worker-fixture", "approver": "master-fixture", "revision": 1,
            "workspace": tree.binding(), "head": tree.head(), "allowed_operations": ["repo.apply_patch"],
            "expires_at": utc(now + dt.timedelta(seconds=120)), "status": "active", "max_seconds": 15,
            "budget_microusd": 0, "test_id": TEST,
        }
        contract_file = authority / "contract.json"
        relay.atomic_store(contract_file, contract)
        payload = {"mission_id": contract["mission_id"], "task_id": "task-p3-fixture",
                   "idempotency_key": "idem-p3-fixture", "operation": "repo.apply_patch",
                   "arguments": {"path": NAME, "old_sha256": digest(BEFORE), "content": AFTER}}
        task = task_from(payload, tree.binding())
        grant = {"approval_id": "approval-p3-fixture", "principal": "master-fixture",
                 "task_sha256": task.request_hash, "contract_sha256": digest(relay.json_canonical(contract)),
                 "issued_at": utc(now)}
        request = {"task": payload, "grant": grant, "signature": sign(key, "nexara-p3-approval", grant)}
        assert socket_request(root, identities, dict(request, signature="forged")) == {"status": "DENIED"}
        wrong_path = dict(payload, arguments=dict(payload["arguments"], path="../unauthorized.py"))
        assert socket_request(root, identities, dict(request, task=wrong_path)) == {"status": "DENIED"}
        unknown_test = dict(contract, test_id="not-in-catalog")
        relay.atomic_store(contract_file, unknown_test)
        wrong_grant = dict(grant, contract_sha256=digest(relay.json_canonical(unknown_test)))
        wrong_request = {**request, "grant": wrong_grant,
                         "signature": sign(key, "nexara-p3-approval", wrong_grant)}
        assert socket_request(root, identities, wrong_request) == {"status": "DENIED"}
        relay.atomic_store(contract_file, contract)
        assert (repo / NAME).read_text() == BEFORE
        success = socket_request(root, identities, request)
        assert success["phase"] == "COMPLETED" and (repo / NAME).read_text() == AFTER
        assert socket_request(root, identities, request) == success
        db = root / "ledger" / PrivateMissionController.database_name
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            state = connection.execute("SELECT * FROM p2_missions WHERE mission_id=? AND task_id=?",
                                       (task.mission_id, task.task_id)).fetchone()
            assert state["epoch"] == 1 and state["phase"] == "COMPLETED"
            approved = Admission(contract_file, identities, tree.binding(), tree.head).check(request, os.geteuid())
            evidence = verify_execution_evidence(success["evidence"], approved, task, state, tree)
        envelope = receipt_envelope(evidence, "audit-fixture")
        envelope["signature"] = sign(attester_key, "nexara-p3-receipt", envelope)
        trust = {"audit-fixture": Identity(attester_public, "attester"),
                 "master-fixture": identities["master-fixture"]}
        assert verify_receipt(envelope, trust) == evidence
        proof = {**request, "contract": contract, "test_result": tree.execute("test.run", {"command_id": TEST})}
        assert verify_receipt_bundle(envelope, proof, trust) == evidence
        invalid_time = dict(evidence, finished_at="2099-01-01T00:00:00Z")
        time_forgery = receipt_envelope(invalid_time, "audit-fixture")
        time_forgery["signature"] = sign(attester_key, "nexara-p3-receipt", time_forgery)
        try:
            verify_receipt_bundle(time_forgery, proof, trust)
        except Denied:
            pass
        else:
            raise AssertionError("signed execution outside contract validity accepted")
        tampered = json.loads(json.dumps(envelope))
        tampered["evidence"]["test"]["exit_code"] = 1
        try:
            verify_receipt(tampered, trust)
        except Denied:
            pass
        else:
            raise AssertionError("tampered test exit accepted")
        assert freeze(root / "ledger") == "ADMISSION_FROZEN_LEDGER_AND_FILES_PRESERVED"
        assert (root / "ledger" / "STOP").is_file() and db.is_file() and (repo / NAME).read_text() == AFTER
        assert socket_request(root, identities, request) == {"status": "STOPPED"}
        # Clearing STOP here only affects the disposable test directory.
        (root / "ledger" / "STOP").unlink()
        relay.atomic_store(contract_file, dict(contract, revision=2, status="revoked"))
        assert socket_request(root, identities, request) == {"status": "DENIED"}
        assert (repo / NAME).read_text() == AFTER
    assert hashlib.sha256(bridge.read_bytes()).hexdigest() == bridge_sha
    relay.atomic_store(evidence_dir / "p3-local-signed-receipt.json", envelope)
    relay.atomic_store(evidence_dir / "p3-local-approval-proof.json", proof)
    relay.atomic_store(evidence_dir / "p3-local-public-trust.json",
                       {name: {"public_key": identity.public_key, "role": identity.role}
                        for name, identity in trust.items()})
    print(json.dumps({"fixture": "local_same_uid", "real_unix_socket": True, "git_head_verified": True,
                      "forged_signature_denied": True, "real_patch_and_test": True, "independent_reattest": True,
                      "tampered_receipt_denied": True, "revoked_replay_denied": True, "stop_verified": True,
                      "unauthorized_path_denied": True, "signed_invalid_time_denied": True, "attempts": 1,
                      "old_bridge_unchanged": True, "production_cab": False, "paid_model_api_calls": 0}))


if __name__ == "__main__":
    experiment(Path(sys.argv[1]).absolute())
