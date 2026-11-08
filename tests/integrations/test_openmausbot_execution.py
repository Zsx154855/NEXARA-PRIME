"""Real subprocess contract tests using a fake CLI, not real OpenMausBot Agents."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from nexara_prime.kernel_boundary import KernelAdmissionContext, KernelExecutionGuard, KernelBoundaryViolation
from nexara_prime.models import WorkContract, RiskLevel

from nexara_prime.integrations.cab01_admission import CAB01TrustedAdmission
from nexara_prime.integrations.openmausbot_execution import (
    ExecutionProof,
    OMBCLI,
    ProofError,
    TaskLedger,
)


class _OfflineTransportOnly(CAB01TrustedAdmission):
    """CAB-01 TEST DOUBLE: no external CLI, checks legacy AEP-02 transport only.

    This bypass belongs exclusively in tests; CAB-01 security regressions
    exercise the real durable SQLiteStore + ApprovalEngine path separately.
    """
    def __init__(self):
        pass

    def authorize(self, mission_id, bot_id, thread_id, objective):
        return None


@pytest.fixture
def probe(tmp_path, monkeypatch):
    state = tmp_path / "fake.json"
    monkeypatch.setenv("AEP_TEST_STATE", str(state))
    for name in ("AEP_SEND_UNREACHABLE", "AEP_WAIT_STATUS", "AEP_TEAM", "AEP_MISMATCH",
                 "AEP_ANCHOR_STALE", "AEP_QUEUED", "AEP_STEERED", "AEP_NODE_RUNNING",
                 "AEP_WRONG_JOB", "AEP_STALE_JOB", "AEP_FAILED_COUNTS"):
        monkeypatch.delenv(name, raising=False)
    fixture = Path(__file__).parent / "fixtures" / "fake_openmausbot.py"
    ledger = TaskLedger(tmp_path / "missions.db")

    def run_fake(argv, **kwargs):
        return subprocess.run([sys.executable, str(fixture), *argv[1:]], **kwargs)

    cli = OMBCLI(runner=run_fake)
    return ExecutionProof(ledger, cli, authority=_OfflineTransportOnly()), state, tmp_path


def submit(proof, name="m-1"):
    return proof.submit(
        name, "lead", "thread-fixed",
        "Investigate, repair, independently test; no paid calls",
    )


def test_submit_and_restart_do_not_duplicate(probe):
    proof, state, path = probe
    a = submit(proof)
    b = submit(proof)
    assert a["status"] == b["status"] == "SENT"
    restarted = ExecutionProof(TaskLedger(path / "missions.db"), proof.cli, authority=proof.authority)
    assert submit(restarted)["status"] == "SENT"
    data = json.loads(state.read_text())
    assert len(data["unique_sends"]) == 1
    assert data["send_attempts"] == 1
    assert data["unique_sends"][a["send_id"]]["text"].startswith("Investigate")


def test_offline_send_resumes_with_fixed_id(probe, monkeypatch):
    proof, state, _ = probe
    monkeypatch.setenv("AEP_SEND_UNREACHABLE", "1")
    assert submit(proof)["status"] == "AWAITING_CONNECTIVITY"
    monkeypatch.delenv("AEP_SEND_UNREACHABLE")
    assert proof.reconcile("m-1")["status"] == "SENT"
    data = json.loads(state.read_text())
    assert len(data["unique_sends"]) == 1
    assert data["send_attempts"] == 2


def test_completed_tree_is_reported_not_independent_qa(probe):
    proof, _, _ = probe
    submit(proof)
    assert proof.reconcile("m-1")["status"] == "REPORTED"
    assert proof.team_evidence("m-1") == {
        "delegation_observed": True,
        "qa_verified": False,
        "unique_completed_bots": 3,
        "failed_nodes": [],
        "reason": "team_tree_reported",
    }


def test_completed_one_bot_is_not_three_agent_proof(probe, monkeypatch):
    proof, _, _ = probe
    monkeypatch.setenv("AEP_TEAM", "0")
    submit(proof)
    proof.reconcile("m-1")
    assert proof.team_evidence("m-1")["delegation_observed"] is False


def test_settled_failed_is_not_success(probe, monkeypatch):
    proof, _, _ = probe
    monkeypatch.setenv("AEP_WAIT_STATUS", "failed")
    submit(proof)
    assert proof.reconcile("m-1")["status"] == "EXECUTION_FAILED"
    assert proof.team_evidence("m-1")["delegation_observed"] is False


def test_needs_input_is_not_automatic_authorization(probe, monkeypatch):
    proof, _, _ = probe
    monkeypatch.setenv("AEP_WAIT_STATUS", "needs-input")
    submit(proof)
    assert proof.reconcile("m-1")["status"] == "NEEDS_INPUT"


def test_timeout_is_resumable_and_does_not_duplicate_send(probe, monkeypatch):
    proof, state, _ = probe
    submit(proof)
    monkeypatch.setenv("AEP_WAIT_STATUS", "timed-out")
    assert proof.reconcile("m-1")["status"] == "RUNNING"
    monkeypatch.setenv("AEP_WAIT_STATUS", "completed")
    assert proof.reconcile("m-1")["status"] == "REPORTED"
    assert json.loads(state.read_text())["send_attempts"] == 1


def test_network_drop_after_send_does_not_resend(probe, monkeypatch):
    proof, state, _ = probe
    submit(proof)
    monkeypatch.setenv("AEP_WAIT_STATUS", "offline")
    assert proof.reconcile("m-1")["status"] == "WAITING_FOR_DEVICE"
    monkeypatch.setenv("AEP_WAIT_STATUS", "completed")
    assert proof.reconcile("m-1")["status"] == "REPORTED"
    assert json.loads(state.read_text())["send_attempts"] == 1


def test_reject_duplicate_mission_with_different_objective(probe):
    proof, _, _ = probe
    submit(proof)
    with pytest.raises(ProofError, match="mission_id_conflict"):
        proof.submit("m-1", "lead", "thread-fixed", "a different task")


def test_reject_mismatched_ack(probe, monkeypatch):
    proof, _, _ = probe
    monkeypatch.setenv("AEP_MISMATCH", "1")
    with pytest.raises(ProofError, match="send_ack_mismatch"):
        submit(proof)


def test_no_arbitrary_server_and_no_unknown_mission(probe):
    with pytest.raises(ProofError, match="explicit_loopback_or_https_required"):
        OMBCLI(url="http://evil.example.com")
    proof, _, _ = probe
    with pytest.raises(ProofError, match="mission_not_found"):
        proof.reconcile("absent")


def test_secret_only_file_and_never_command_line(probe, tmp_path):
    proof, state, _ = probe
    file = tmp_path / "token"
    file.write_text("secretXYZ")
    proof.cli.token_file = str(file)
    submit(proof)
    cmd = json.loads(state.read_text())["calls"][0]
    assert "--token-file" in cmd and "secretXYZ" not in cmd


def test_dedicated_thread_cannot_run_two_missions(probe):
    proof, _, _ = probe
    submit(proof)
    with pytest.raises(ProofError, match="thread_already_bound_to_mission"):
        submit(proof, name="m-2")


def authorized_cognitive_dispatch(proposal, *, contract_status="approved", contract_source=None,
                                  mission_id="mission-42", admitted_mission=None, admitted_contract=None,
                                  approved_at="2026-11-08T00:00:00Z"):
    contract = WorkContract(
        mission_id=mission_id, objective="Patch a disposable synthetic repository",
        provenance=proposal["proposal_id"] if contract_source is None else contract_source,
        status=contract_status, approved_at=approved_at, risk_level=RiskLevel.R2,
        boundaries=["Only inside a disposable test directory"],
    )
    guard = KernelExecutionGuard()
    ctx = KernelAdmissionContext(
        mission_id=mission_id if admitted_mission is None else admitted_mission,
        caller="trusted_test_controller", contract_verified=True,
        authority_verified=True, state_valid=True, governance_approved=True,
        evidence_chain_initialized=True,
        metadata={"contract_id": contract.contract_id if admitted_contract is None else admitted_contract},
    )
    # This test only verifies the adapter gate, NOT the controller's trust
    # in real external authorization or actual physical OS sandbox.
    guard.admit(ctx)
    return contract, guard


def test_cognitive_goal_proposal_to_cli_contract(probe):
    proof, state, _ = probe
    proposal = {"proposal_id": "coggoal-42", "project_id": "nexara-aep03",
                "objective": "Investigate observed failing tests (read-only)", "status": "HYPOTHESIS",
                "execution_authorized": False}
    contract, guard = authorized_cognitive_dispatch(proposal)
    result = proof.submit_proposal(proposal, "research-lead", "thread-fixed",
                                   contract=contract, guard=guard)
    assert result["status"] == "SENT"
    assert proof.ledger.get(contract.mission_id)["objective"] == contract.objective
    assert proof.ledger.get(contract.mission_id)["id"] != proposal["proposal_id"]
    assert len(json.loads(state.read_text())["unique_sends"]) == 1
    assert proof.submit_proposal(proposal, "research-lead", "thread-fixed",
                                 contract=contract, guard=guard)["status"] == "SENT"
    assert json.loads(state.read_text())["send_attempts"] == 1


def test_cognitive_goal_cannot_dispatch_by_self_claim(probe):
    proof, state, _ = probe
    proposal = {"proposal_id": "coggoal-42", "status": "HYPOTHESIS",
                "objective": "Investigate synthetic failing tests", "execution_authorized": True}
    with pytest.raises(ProofError, match="kernel_admission_required"):
        proof.submit_proposal(proposal, "lead", "thread-fixed")
    assert proof.ledger.get("coggoal-42") is None
    assert not state.exists()


def test_cognitive_goal_rejects_wrong_admission_and_contract(probe):
    proof, state, _ = probe
    proposal = {"proposal_id": "coggoal-42", "status": "EVIDENCE_BACKED",
                "objective": "Analyze a failing test"}
    params = [
        {"contract_status": "draft"},
        {"approved_at": ""},
        {"contract_source": "other-source"},
        {"admitted_mission": "other-mission"},
        {"admitted_contract": "other-contract"},
    ]
    for kwargs in params:
        contract, guard = authorized_cognitive_dispatch(proposal, **kwargs)
        with pytest.raises(ProofError, match="cognitive_contract_not_authorized|kernel_admission_required|contract_admission_mismatch"):
            proof.submit_proposal(proposal, "lead", "thread-fixed", contract=contract, guard=guard)
    assert proof.ledger.get("mission-42") is None
    assert not state.exists()


def test_cognitive_goal_rejects_incomplete_admission(probe):
    proof, state, _ = probe
    proposal = {"proposal_id": "coggoal-42", "status": "HYPOTHESIS",
                "objective": "Analyze synthetic failing test"}
    contract, _ = authorized_cognitive_dispatch(proposal)
    guard = KernelExecutionGuard()
    with pytest.raises(KernelBoundaryViolation):
        guard.admit(KernelAdmissionContext(
            mission_id=contract.mission_id, caller="test",
            contract_verified=True, authority_verified=True,
            state_valid=True, governance_approved=False,
            evidence_chain_initialized=True,
            metadata={"contract_id": contract.contract_id},
        ))
    with pytest.raises(ProofError, match="kernel_admission_required"):
        proof.submit_proposal(proposal, "lead", "thread-fixed", contract=contract, guard=guard)
    assert not state.exists()


def test_cognitive_goal_rejects_invalid_proposal_even_with_admission(probe):
    proof, state, _ = probe
    valid = {"proposal_id": "coggoal-42", "status": "HYPOTHESIS",
             "objective": "Read synthetic repository"}
    contract, guard = authorized_cognitive_dispatch(valid)
    for bad in (
        {"proposal_id": "bad", "objective": "x", "status": "REJECTED"},
        {"proposal_id": "coggoal-42", "objective": "", "status": "HYPOTHESIS"},
        {"proposal_id": "", "objective": "x", "status": "HYPOTHESIS"},
        {"proposal_id": "coggoal-42", "objective": "x", "status": "PERMISSION_GRANTED"},
    ):
        with pytest.raises(ProofError, match="invalid_cognitive_proposal"):
            proof.submit_proposal(bad, "lead", "thread-fixed", contract=contract, guard=guard)
    assert not state.exists()



def test_cross_connection_thread_binding_is_database_unique(probe):
    proof, _, path = probe
    second = TaskLedger(path / "missions.db")
    proof.ledger.create("first", "lead", "shared-thread", "first task")
    with pytest.raises(ProofError, match="thread_already_bound_to_mission"):
        second.create("second", "lead", "shared-thread", "second task")
    assert second.get("second") is None
    assert second.get("first")["thread_id"] == "shared-thread"


def test_late_state_update_cannot_erase_terminal_receipt(probe):
    proof, _, path = probe
    submit(proof)
    reported = proof.reconcile("m-1")
    assert reported["status"] == "REPORTED"
    original = json.loads(reported["report"])
    from_another_worker = TaskLedger(path / "missions.db")
    late = from_another_worker.transition("m-1", "RUNNING", report={"state": "old"})
    assert late["status"] == "REPORTED"
    assert json.loads(late["report"]) == original


def test_send_cli_timeout_must_be_resumable_with_identical_send_id(probe):
    proof, state, _ = probe
    original = proof.cli.runner

    def timeout(_argv, **_kwargs):
        raise subprocess.TimeoutExpired("openmausbot", 75)

    proof.cli.runner = timeout
    assert submit(proof)["status"] == "AWAITING_CONNECTIVITY"
    record_id = proof.ledger.get("m-1")["send_id"]
    proof.cli.runner = original
    assert proof.reconcile("m-1")["status"] == "SENT"
    assert json.loads(state.read_text())["unique_sends"].keys() == {record_id}


def test_wait_cli_timeout_does_not_resend_or_mark_failed(probe):
    proof, state, _ = probe
    submit(proof)
    original = proof.cli.runner

    def timeout(_argv, **_kwargs):
        raise subprocess.TimeoutExpired("openmausbot", 75)

    proof.cli.runner = timeout
    assert proof.reconcile("m-1")["status"] == "WAITING_FOR_DEVICE"
    proof.cli.runner = original
    assert proof.reconcile("m-1")["status"] == "REPORTED"
    assert json.loads(state.read_text())["send_attempts"] == 1


def test_completion_without_job_tree_is_not_success(probe):
    proof, _, _ = probe
    submit(proof)

    def incomplete(_argv, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=json.dumps({
            "ok": True, "state": "completed", "job": {"nodes": []}
        }), stderr="")

    proof.cli.runner = incomplete
    assert proof.reconcile("m-1")["status"] == "EXECUTION_FAILED"
    assert proof.team_evidence("m-1")["qa_verified"] is False


# AEP-02: fresh server-clock anchoring and strict receipt validation.

def test_server_clock_persisted_and_wait_uses_since(probe):
    proof, state, _ = probe
    record = submit(proof)
    assert record["since_ms"] == 1000
    assert proof.reconcile("m-1")["status"] == "REPORTED"
    calls = json.loads(state.read_text())["calls"]
    assert calls[0][0] == "run" and calls[0][calls[0].index("--wait") + 1] == "none"
    assert calls[1][0] == "wait" and calls[1][calls[1].index("--since") + 1] == "1000"


def test_ambiguous_retry_does_not_accept_unanchored_job(probe, monkeypatch):
    proof, state, _ = probe
    monkeypatch.setenv("AEP_ANCHOR_STALE", "1")
    record = submit(proof)
    assert record["status"] == "NEEDS_INPUT" and record["since_ms"] is None
    assert json.loads(record["report"])["reason"] == "ambiguous_job_anchor"
    assert proof.reconcile("m-1")["status"] == "NEEDS_INPUT"
    assert len(json.loads(state.read_text())["calls"]) == 1


def test_stale_job_receipt_is_rejected(probe, monkeypatch):
    proof, _, _ = probe
    submit(proof)
    monkeypatch.setenv("AEP_STALE_JOB", "1")
    assert proof.reconcile("m-1")["status"] == "EXECUTION_FAILED"


def test_wrong_thread_receipt_is_rejected(probe, monkeypatch):
    proof, _, _ = probe
    submit(proof)
    monkeypatch.setenv("AEP_WRONG_JOB", "1")
    assert proof.reconcile("m-1")["status"] == "EXECUTION_FAILED"


def test_nonterminal_child_rejects_completed_root(probe, monkeypatch):
    proof, _, _ = probe
    submit(proof)
    monkeypatch.setenv("AEP_NODE_RUNNING", "1")
    assert proof.reconcile("m-1")["status"] == "EXECUTION_FAILED"


def test_failed_count_rejects_completed_root(probe, monkeypatch):
    proof, _, _ = probe
    submit(proof)
    monkeypatch.setenv("AEP_FAILED_COUNTS", "1")
    assert proof.reconcile("m-1")["status"] == "EXECUTION_FAILED"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8799@evil.example", "http://localhost:8799@evil.example",
    "http://127.0.0.1:8799/x", "https://user:secret@example.com", "https://example.com/#fragment",
    "http://127.0.0.1:0", "http://localhost", "https://example.com/path",
])
def test_url_validation_rejects_authority_confusion(url):
    with pytest.raises(ProofError, match="explicit_loopback_or_https_required"):
        OMBCLI(url=url)


def test_legacy_ledger_schema_migrates_and_does_not_accept_old_job(tmp_path):
    path = tmp_path / "legacy.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE missions (id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, thread_id TEXT NOT NULL, "
               "objective TEXT NOT NULL, send_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL, "
               "message_id TEXT, report TEXT)")
    db.execute("INSERT INTO missions VALUES ('old','lead','thread-fixed','x','nexa-old','SENT','m1',NULL)")
    db.commit()
    db.close()
    ledger = TaskLedger(path)
    assert ledger.get("old")["since_ms"] is None
    class NoCall:
        def call(self, *args, **kwargs):
            raise AssertionError("must not trust an unanchored historical job")
    proof = ExecutionProof(ledger, NoCall(), authority=_OfflineTransportOnly())
    result = proof.reconcile("old")
    assert result["status"] == "NEEDS_INPUT"
    assert json.loads(result["report"])["reason"] == "missing_job_anchor"


def test_busy_thread_queue_not_accepted_as_exclusive_execution(probe, monkeypatch):
    proof, _, _ = probe
    monkeypatch.setenv("AEP_QUEUED", "1")
    result = submit(proof)
    assert result["status"] == "NEEDS_INPUT"
    assert json.loads(result["report"])["reason"] == "nonexclusive_thread_send"
    assert proof.reconcile("m-1")["status"] == "NEEDS_INPUT"


def test_steered_message_not_accepted_as_independent_job(probe, monkeypatch):
    proof, _, _ = probe
    monkeypatch.setenv("AEP_STEERED", "1")
    result = submit(proof)
    assert result["status"] == "NEEDS_INPUT"
    assert json.loads(result["report"])["reason"] == "nonexclusive_thread_send"


def test_standalone_json_submit_fails_closed_before_ledger_creation(tmp_path, capsys):
    from scripts.proofs.openmausbot_execution_proof import main
    database = tmp_path / "should-not-exist.db"
    status = main([
        "submit", "--db", str(database),
        "--proposal-json", str(tmp_path / "forged.json"),
        "--bot-id", "lead", "--thread-id", "thread-fixed",
    ])
    result = json.loads(capsys.readouterr().out)
    assert status == 3
    assert result["ok"] is False
    assert result["status"] == "BLOCKED"
    assert result["error"] == "trusted_admission_gateway_required"
    assert not database.exists()


def test_standalone_resume_requires_trusted_gateway(tmp_path, capsys):
    from scripts.proofs.openmausbot_execution_proof import main
    database = tmp_path / "no-resume.db"
    status = main(["resume", "--db", str(database), "--mission-id", "unknown"])
    result = json.loads(capsys.readouterr().out)
    assert status == 3
    assert result["error"] == "trusted_admission_gateway_required"
    assert not database.exists()


def test_missing_admission_prevents_real_send_even_when_ledger_is_empty(tmp_path):
    class NeverCall:
        def call(self, *args, **kwargs):
            raise AssertionError("CLI must never execute without CAB01")
    proof = ExecutionProof(TaskLedger(tmp_path / "missions.db"), NeverCall())
    with pytest.raises(ProofError, match="trusted_admission_required"):
        proof.submit("m1", "bot1", "thread1", "send a message")
    assert proof.ledger.get("m1") is None
