"""Real subprocess contract tests using a fake CLI, not real OpenMausBot Agents."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from nexara_prime.integrations.openmausbot_execution import (
    ExecutionProof,
    OMBCLI,
    ProofError,
    TaskLedger,
)


@pytest.fixture
def probe(tmp_path, monkeypatch):
    state = tmp_path / "fake.json"
    monkeypatch.setenv("AEP_TEST_STATE", str(state))
    for name in ("AEP_SEND_UNREACHABLE", "AEP_WAIT_STATUS", "AEP_TEAM", "AEP_MISMATCH"):
        monkeypatch.delenv(name, raising=False)
    fixture = Path(__file__).parent / "fixtures" / "fake_openmausbot.py"
    ledger = TaskLedger(tmp_path / "missions.db")

    def run_fake(argv, **kwargs):
        return subprocess.run([sys.executable, str(fixture), *argv[1:]], **kwargs)

    cli = OMBCLI(runner=run_fake)
    return ExecutionProof(ledger, cli), state, tmp_path


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
    restarted = ExecutionProof(TaskLedger(path / "missions.db"), proof.cli)
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
    assert proof.reconcile("m-1")["status"] == "RUNNING"
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


def test_cognitive_goal_proposal_to_cli_contract(probe):
    proof, _, _ = probe
    proposal = {"proposal_id": "coggoal-42",
                "objective": "Find and repair failing test", "status": "HYPOTHESIS"}
    result = proof.submit_proposal(proposal, "research-lead", "thread-fixed")
    assert result["status"] == "SENT"
    assert proof.ledger.get("coggoal-42")["objective"] == "Find and repair failing test"
    with pytest.raises(ProofError, match="invalid_cognitive_proposal"):
        proof.submit_proposal({"proposal_id": "bad", "objective": "x", "status": "REJECTED"},
                              "lead", "unused-thread")
