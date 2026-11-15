"""B1.1 acceptance: operation dispatch, route-before-execution, OS-enforced deadline."""
import datetime as dt
import multiprocessing
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import relay
from durable import digest
from p2_broker import broker_call
from p2_missions import task_from
from p2_workspace import FixtureCheck, Workspace
from p3_dsh import MAX_TASK_SECONDS, DshError, ProcessAdapter, dsh_evidence, run_task, verify_dsh_evidence
from p3_dsh_route import RouteError, verify_route
from p3_private import Admission, Denied, Identity, PrivateMissionController, PrivateWrite, serve_one

NAME = "test_fixture.py"
BEFORE = "EXPECTED = 'BTC'\n"
AFTER = "EXPECTED = 'btc'\n"
TEST = "p3-fixture-check"
OPERATION = "dsh.task.run"
METERING = {"model_calls": 0, "source": "test-double"}


def sign(key, namespace, value):
    return subprocess.check_output(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace],
        input=relay.json_canonical(value).encode(), stderr=subprocess.DEVNULL, env={}, timeout=5,
    ).decode()


def ephemeral_key(path):
    subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
                   env={}, check=True, timeout=5)
    return " ".join(path.with_suffix(".pub").read_text().split()[:2])


def listener(root=None):
    """A real local unix socket on a short path, so route verification has a live endpoint."""
    base = Path(tempfile.mkdtemp(prefix="b1s-", dir="/private/tmp"))
    path = base / "m.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(8)
    return path, server


def build(root, *, operation=OPERATION, budget=0, max_seconds=MAX_TASK_SECONDS,
          kind="readonly-inspect", instruction="report status only", route=None,
          instruction_sha=None, contract_patch=None, grant_patch=None, forged=False):
    repo = root / "repo"
    repo.mkdir(mode=0o700)
    os.chmod(repo, 0o700)
    git_env = {"PATH": "/usr/bin:/bin", "HOME": str(root), "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": "/dev/null"}
    subprocess.run(["/usr/bin/git", "init", "--quiet", "--template="], env=git_env, cwd=repo, check=True)
    (repo / NAME).write_text(BEFORE)
    subprocess.run(["/usr/bin/git", "add", "--", NAME], env=git_env, cwd=repo, check=True)
    subprocess.run(["/usr/bin/git", "-c", "user.name=B1", "-c", "user.email=b1@example.invalid",
                    "commit", "-qm", "baseline"], env=git_env, cwd=repo, check=True)
    tree = Workspace(repo, fixture_checks={TEST: FixtureCheck(NAME, digest(AFTER))})
    authority = root / "authority"
    authority.mkdir(mode=0o700)
    os.chmod(authority, 0o700)
    approver_key = authority / "approver"
    identities = {"b1-approver": Identity(ephemeral_key(approver_key), "approver"),
                  "b1-worker": Identity(ephemeral_key(authority / "worker"), "worker")}
    now = dt.datetime.now(dt.timezone.utc)
    contract = {
        "contract_id": "contract-b1-dsh", "mission_id": "mission-b1-dsh",
        "requester_uid": os.geteuid(), "requester": "b1-worker", "approver": "b1-approver",
        "revision": 1, "workspace": tree.binding(), "head": tree.head(),
        "allowed_operations": [operation], "expires_at": (now + dt.timedelta(seconds=120)).isoformat(),
        "status": "active", "max_seconds": max_seconds, "budget_microusd": budget, "test_id": TEST,
    }
    contract.update(contract_patch or {})
    contract_file = authority / "contract.json"
    relay.atomic_store(contract_file, contract)
    if operation == "dsh.task.run":
        arguments = {"task_kind": kind, "instruction": instruction,
                     "instruction_sha256": instruction_sha or digest(instruction),
                     "route": route}
    else:
        arguments = {"path": NAME, "old_sha256": digest(BEFORE), "content": AFTER}
    payload = {"mission_id": contract["mission_id"], "task_id": "task-b1-1",
               "idempotency_key": "idem-b1-1", "operation": operation, "arguments": arguments}
    task = task_from(payload, tree.binding())
    grant = {"approval_id": "approval-b1-dsh", "principal": "b1-approver",
             "task_sha256": task.request_hash,
             "contract_sha256": digest(relay.json_canonical(contract)),
             "issued_at": now.isoformat()}
    grant.update(grant_patch or {})
    signature = "-----BEGIN SSH SIGNATURE-----\nforged\n-----END SSH SIGNATURE-----\n" if forged \
        else sign(approver_key, "nexara-p3-approval", grant)
    request = {"task": payload, "grant": grant, "signature": signature}
    admission = Admission(contract_file, identities, tree.binding(), tree.head)
    return {"tree": tree, "admission": admission, "request": request, "contract": contract,
            "task": task, "now": now, "contract_file": contract_file}


def fake_adapter(exit_code=0, stdout=b'{"status":"readonly-ok"}\n', metering=METERING):
    calls = []

    def adapter(instruction, timeout, workspace):
        calls.append({"instruction": instruction, "timeout": timeout, "workspace": workspace})
        return {"exit_code": exit_code, "stdout": stdout, "stderr": b"", "metering": dict(metering)}

    adapter.calls = calls
    return adapter


def state():
    return {"attempt_id": "a" * 32, "epoch": 1}


def run_socket(root, ctx, adapter, request=None):
    context = multiprocessing.get_context("fork")
    ready = context.Event()

    def child():
        tree = ctx["tree"]
        admission = Admission(ctx["contract_file"], ctx["admission"].identities, tree.binding(), tree.head)
        serve_one(ipc / "write.sock", PrivateWrite(root / "ledger", tree, admission, dsh_adapter=adapter),
                  os.geteuid(), on_ready=ready.set)

    ipc = Path(tempfile.mkdtemp(prefix="b1i-", dir="/private/tmp"))
    ledger = root / "ledger"
    ledger.mkdir(mode=0o700, exist_ok=True)
    os.chmod(ledger, 0o700)
    process = context.Process(target=child)
    process.start()
    try:
        assert ready.wait(6)
        return broker_call(ipc / "write.sock", request or ctx["request"], broker_uid=os.geteuid(), timeout=15)
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)


def test_valid_dsh_task_is_admitted_executed_and_attested(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)})
    approved = ctx["admission"].check(ctx["request"], os.geteuid())
    adapter = fake_adapter()
    now = dt.datetime.now(dt.timezone.utc)
    outcome = run_task(workspace=ctx["tree"].binding(), instruction="report status only",
                       timeout=approved["contract"]["max_seconds"],
                       route={"kind": "unix-socket", "endpoint": str(sock)}, adapter=adapter)
    assert outcome["route"]["billable"] is False and outcome["route"]["probe"] == "connected"
    assert outcome["metering"] == METERING
    times = (now.isoformat(), now.isoformat())
    evidence = dsh_evidence(approved, ctx["task"], state(), outcome, times)
    assert evidence["operation"] == OPERATION
    assert evidence["route"]["route_kind"] == "unix-socket"
    assert "model_calls" not in evidence
    assert verify_dsh_evidence(evidence, approved, ctx["task"], state()) == evidence
    server.close()


def test_socket_end_to_end_dsh_task_completes(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)})
    result = run_socket(tmp_path, ctx, fake_adapter())
    assert result["phase"] == "COMPLETED", result
    assert result["evidence"]["operation"] == OPERATION
    assert result["evidence"]["metering"]["model_calls"] == 0
    server.close()


def test_socket_end_to_end_rejects_bad_dsh_arguments(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)})
    broken = {"task": dict(ctx["request"]["task"],
                           arguments={"task_kind": "readonly-inspect", "instruction": "x"}),
              "grant": ctx["request"]["grant"], "signature": ctx["request"]["signature"]}
    result = run_socket(tmp_path, ctx, fake_adapter(), broken)
    assert result.get("status") == "DENIED", result
    assert "phase" not in result
    server.close()


def test_repo_apply_patch_rules_are_unchanged(tmp_path):
    ctx = build(tmp_path, operation="repo.apply_patch")
    approved = ctx["admission"].check(ctx["request"], os.geteuid())
    assert approved["contract"]["allowed_operations"] == ["repo.apply_patch"]
    patch = ctx["tree"].execute("repo.apply_patch",
                                {"path": NAME, "old_sha256": digest(BEFORE), "content": AFTER})
    assert ctx["tree"].execute("files.read", {"path": NAME})["content"] == AFTER
    assert patch["sha256"] == digest(AFTER)


def test_socket_end_to_end_apply_patch_still_works(tmp_path):
    ctx = build(tmp_path, operation="repo.apply_patch")
    result = run_socket(tmp_path, ctx, None)
    assert result["phase"] == "COMPLETED", result
    assert ctx["tree"].execute("files.read", {"path": NAME})["content"] == AFTER


@pytest.mark.parametrize("operation", ["files.read", "files.write", "test.run", "repo.inspect"])
def test_unauthorized_operation_is_refused(tmp_path, operation):
    ctx = build(tmp_path, operation=operation)
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_forged_signature_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)}, forged=True)
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_wrong_principal_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)},
                grant_patch={"principal": "b1-worker"})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_over_budget_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, budget=1, route={"kind": "unix-socket", "endpoint": str(sock)})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_over_time_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, max_seconds=MAX_TASK_SECONDS + 1,
                route={"kind": "unix-socket", "endpoint": str(sock)})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_workspace_escape_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, contract_patch={"workspace": "/tmp/not-the-workspace"},
                route={"kind": "unix-socket", "endpoint": str(sock)})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_expired_contract_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=60)).isoformat()
    ctx = build(tmp_path, contract_patch={"expires_at": past},
                route={"kind": "unix-socket", "endpoint": str(sock)})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_instruction_digest_mismatch_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, instruction_sha="b" * 64, route={"kind": "unix-socket", "endpoint": str(sock)})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_task_kind_not_allowlisted_is_refused(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, kind="shell-anything", route={"kind": "unix-socket", "endpoint": str(sock)})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())
    server.close()


def test_external_api_route_is_refused_before_adapter_runs(tmp_path):
    ctx = build(tmp_path, route={"kind": "loopback-http", "endpoint": "http://api.deepseek.com/v1"})
    adapter = fake_adapter()
    with pytest.raises(DshError) as exc:
        run_task(workspace=ctx["tree"].binding(), instruction="x", timeout=5,
                 route={"kind": "loopback-http", "endpoint": "http://api.deepseek.com/v1"}, adapter=adapter)
    assert "egress_denied" in str(exc.value)
    assert adapter.calls == []


def test_billable_credential_blocks_execution(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)})
    adapter = fake_adapter()
    with pytest.raises(DshError) as exc:
        run_task(workspace=ctx["tree"].binding(), instruction="x", timeout=5,
                 route={"kind": "unix-socket", "endpoint": str(sock)}, adapter=adapter,
                 environ={"OPENAI_API_KEY": "sk-test"})
    assert "billable_credential_present" in str(exc.value)
    assert adapter.calls == []
    server.close()


def test_unreachable_route_is_refused_before_adapter_runs(tmp_path):
    adapter = fake_adapter()
    with pytest.raises(DshError) as exc:
        run_task(workspace=str(tmp_path), instruction="x", timeout=5,
                 route={"kind": "unix-socket", "endpoint": str(tmp_path / "missing.sock")},
                 adapter=adapter, environ={})
    assert "route_unverified" in str(exc.value)
    assert adapter.calls == []


def test_route_schema_is_strict():
    with pytest.raises(RouteError):
        verify_route({"kind": "loopback-http"}, environ={})
    with pytest.raises(RouteError):
        verify_route({"kind": "tcp", "endpoint": "http://127.0.0.1:11434"}, environ={})
    with pytest.raises(RouteError):
        verify_route({"kind": "loopback-http", "endpoint": "https://127.0.0.1:11434"}, environ={})


def test_metering_must_be_measured_not_assumed(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)})
    bad = fake_adapter(metering={"model_calls": -1, "source": "x"})
    with pytest.raises(DshError):
        run_task(workspace=ctx["tree"].binding(), instruction="x", timeout=5,
                 route={"kind": "unix-socket", "endpoint": str(sock)}, adapter=bad)
    no_source = fake_adapter(metering={"model_calls": 0, "source": ""})
    with pytest.raises(DshError):
        run_task(workspace=ctx["tree"].binding(), instruction="x", timeout=5,
                 route={"kind": "unix-socket", "endpoint": str(sock)}, adapter=no_source)
    server.close()


def test_process_adapter_kills_a_sleeping_child(tmp_path):
    adapter = ProcessAdapter(["/bin/sh", "-c", "sleep 30"])
    started = time.monotonic()
    with pytest.raises(DshError) as exc:
        run_task(workspace=str(tmp_path), instruction="ignored", timeout=1,
                 route={"kind": "loopback-http", "endpoint": "http://127.0.0.1:1"},
                 adapter=adapter, prober=lambda *a: "connected")
    assert "task_timeout" in str(exc.value)
    assert time.monotonic() - started < 15


def test_process_adapter_reports_real_exit_and_metering(tmp_path):
    adapter = ProcessAdapter(["/bin/echo"])
    outcome = run_task(workspace=str(tmp_path), instruction="hello", timeout=5,
                       route={"kind": "loopback-http", "endpoint": "http://127.0.0.1:1"},
                       adapter=adapter, prober=lambda *a: "connected")
    assert outcome["exit_code"] == 0
    assert outcome["metering"] == {"model_calls": "unknown", "source": "dsh-process"}


def test_terminate_leaves_no_child_behind():
    process = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
    time.sleep(0.2)
    pid = process.pid
    assert ProcessAdapter.terminate(process) is True
    assert process.poll() is not None
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_tampered_evidence_is_detected(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)})
    approved = ctx["admission"].check(ctx["request"], os.geteuid())
    now = dt.datetime.now(dt.timezone.utc)
    outcome = run_task(workspace=ctx["tree"].binding(), instruction="report status only",
                       timeout=MAX_TASK_SECONDS, route={"kind": "unix-socket", "endpoint": str(sock)},
                       adapter=fake_adapter())
    evidence = dsh_evidence(approved, ctx["task"], state(), outcome, (now.isoformat(), now.isoformat()))
    for forged in (dict(evidence, exit_code=1), dict(evidence, budget_microusd=1),
                   dict(evidence, metering={"model_calls": 5, "source": "forged"})):
        with pytest.raises(DshError):
            verify_dsh_evidence(forged, approved, ctx["task"], state())
    server.close()


def test_admission_is_replay_stable(tmp_path):
    sock, server = listener(tmp_path)
    ctx = build(tmp_path, route={"kind": "unix-socket", "endpoint": str(sock)})
    first = ctx["admission"].check(ctx["request"], os.geteuid())
    second = ctx["admission"].check(ctx["request"], os.geteuid())
    assert first["approval_id"] == second["approval_id"]
    assert first["signed_grant_sha256"] == second["signed_grant_sha256"]
    server.close()
