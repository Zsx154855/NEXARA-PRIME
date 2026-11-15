"""B1 acceptance: the dsh.task.run operation and its refusals. No model is ever called."""
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import relay
from durable import digest
from p2_missions import task_from
from p2_workspace import FixtureCheck, Workspace
from p3_dsh import MAX_TASK_SECONDS, DshError, dsh_evidence, run_task, verify_dsh_evidence
from p3_private import Admission, Denied, Identity

NAME = "test_fixture.py"
BEFORE = "EXPECTED = 'BTC'\n"
AFTER = "EXPECTED = 'btc'\n"
TEST = "p3-fixture-check"
OPERATION = "dsh.task.run"
ROUTE = "ollama:qwen3:4b-omb-32k@127.0.0.1:11434 verified zero-incremental-cost"


def sign(key, namespace, value):
    return subprocess.check_output(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace],
        input=relay.json_canonical(value).encode(), stderr=subprocess.DEVNULL, env={}, timeout=5,
    ).decode()


def ephemeral_key(path):
    subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
                   env={}, check=True, timeout=5)
    return " ".join(path.with_suffix(".pub").read_text().split()[:2])


def build(root, *, operation=OPERATION, budget=0, max_seconds=MAX_TASK_SECONDS,
          kind="readonly-inspect", instruction="report status only",
          instruction_sha=None, contract_patch=None, grant_patch=None, signature_patch=False):
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
                     "instruction_sha256": instruction_sha or digest(instruction)}
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
    signature = "-----BEGIN SSH SIGNATURE-----\nforged\n-----END SSH SIGNATURE-----\n" if signature_patch \
        else sign(approver_key, "nexara-p3-approval", grant)
    request = {"task": payload, "grant": grant, "signature": signature}
    admission = Admission(contract_file, identities, tree.binding(), tree.head)
    return {"tree": tree, "admission": admission, "request": request, "contract": contract,
            "task": task, "identities": identities, "now": now, "contract_file": contract_file}


def fake_adapter(route=ROUTE, exit_code=0, stdout=b'{"status":"readonly-ok"}\n'):
    calls = []

    def adapter(instruction, timeout, workspace):
        calls.append({"instruction": instruction, "timeout": timeout, "workspace": workspace})
        return {"exit_code": exit_code, "stdout": stdout, "stderr": b"", "zero_cost_route": route}

    adapter.calls = calls
    return adapter


def state():
    return {"attempt_id": "a" * 32, "epoch": 1}


def test_valid_dsh_task_is_admitted_executed_and_attested(tmp_path):
    ctx = build(tmp_path)
    approved = ctx["admission"].check(ctx["request"], os.geteuid())
    assert approved["contract"]["allowed_operations"] == [OPERATION]
    adapter = fake_adapter()
    now = dt.datetime.now(dt.timezone.utc)
    outcome = run_task(workspace=ctx["tree"].binding(), instruction="report status only",
                       timeout=approved["contract"]["max_seconds"], adapter=adapter)
    assert outcome["exit_code"] == 0 and outcome["zero_cost_route"] == ROUTE
    times = (now.isoformat(), now.isoformat())
    evidence = dsh_evidence(approved, ctx["task"], state(), outcome, times)
    assert evidence["operation"] == OPERATION
    assert evidence["result_sha256"] == outcome["result_sha256"]
    assert evidence["model_calls"] == 0
    assert verify_dsh_evidence(evidence, approved, ctx["task"], state()) == evidence
    assert adapter.calls[0]["timeout"] == MAX_TASK_SECONDS


def test_repo_apply_patch_rules_are_unchanged(tmp_path):
    ctx = build(tmp_path, operation="repo.apply_patch")
    approved = ctx["admission"].check(ctx["request"], os.geteuid())
    assert approved["contract"]["allowed_operations"] == ["repo.apply_patch"]
    patch = ctx["tree"].execute("repo.apply_patch",
                                {"path": NAME, "old_sha256": digest(BEFORE), "content": AFTER})
    assert ctx["tree"].execute("files.read", {"path": NAME})["content"] == AFTER
    assert patch["sha256"] == digest(AFTER)


@pytest.mark.parametrize("operation", ["files.read", "files.write", "test.run", "repo.inspect"])
def test_unauthorized_operation_is_refused(tmp_path, operation):
    ctx = build(tmp_path, operation=operation)
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_forged_signature_is_refused(tmp_path):
    ctx = build(tmp_path, signature_patch=True)
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_wrong_principal_is_refused(tmp_path):
    ctx = build(tmp_path, grant_patch={"principal": "b1-worker"})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_over_budget_is_refused(tmp_path):
    ctx = build(tmp_path, budget=1)
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_over_time_is_refused(tmp_path):
    ctx = build(tmp_path, max_seconds=MAX_TASK_SECONDS + 1)
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_workspace_escape_is_refused(tmp_path):
    ctx = build(tmp_path, contract_patch={"workspace": "/tmp/not-the-workspace"})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_expired_contract_is_refused(tmp_path):
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=60)).isoformat()
    ctx = build(tmp_path, contract_patch={"expires_at": past})
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_instruction_digest_mismatch_is_refused(tmp_path):
    ctx = build(tmp_path, instruction_sha="b" * 64)
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_task_kind_not_allowlisted_is_refused(tmp_path):
    ctx = build(tmp_path, kind="shell-anything")
    with pytest.raises(Denied):
        ctx["admission"].check(ctx["request"], os.geteuid())


def test_execution_without_proven_zero_cost_route_is_refused(tmp_path):
    ctx = build(tmp_path)
    approved = ctx["admission"].check(ctx["request"], os.geteuid())
    with pytest.raises(DshError) as exc:
        run_task(workspace=ctx["tree"].binding(), instruction="report status only",
                 timeout=MAX_TASK_SECONDS, adapter=fake_adapter(route=""))
    assert "model_cost_unverified" in str(exc.value)


def test_missing_adapter_is_refused(tmp_path):
    ctx = build(tmp_path)
    with pytest.raises(DshError):
        run_task(workspace=ctx["tree"].binding(), instruction="x", timeout=5, adapter=None)


def test_adapter_timeout_is_refused(tmp_path):
    def adapter(instruction, timeout, workspace):
        raise subprocess.TimeoutExpired(cmd="dsh", timeout=timeout)

    with pytest.raises(DshError) as exc:
        run_task(workspace=str(tmp_path), instruction="x", timeout=5, adapter=adapter)
    assert "task_timeout" in str(exc.value)


def test_tampered_evidence_is_detected(tmp_path):
    ctx = build(tmp_path)
    approved = ctx["admission"].check(ctx["request"], os.geteuid())
    now = dt.datetime.now(dt.timezone.utc)
    outcome = run_task(workspace=ctx["tree"].binding(), instruction="report status only",
                       timeout=MAX_TASK_SECONDS, adapter=fake_adapter())
    evidence = dsh_evidence(approved, ctx["task"], state(), outcome, (now.isoformat(), now.isoformat()))
    forged = dict(evidence, exit_code=1)
    with pytest.raises(DshError):
        verify_dsh_evidence(forged, approved, ctx["task"], state())
    forged2 = dict(evidence, budget_microusd=1)
    with pytest.raises(DshError):
        verify_dsh_evidence(forged2, approved, ctx["task"], state())


def test_admission_is_replay_stable(tmp_path):
    ctx = build(tmp_path)
    first = ctx["admission"].check(ctx["request"], os.geteuid())
    second = ctx["admission"].check(ctx["request"], os.geteuid())
    assert first["approval_id"] == second["approval_id"]
    assert first["signed_grant_sha256"] == second["signed_grant_sha256"]
