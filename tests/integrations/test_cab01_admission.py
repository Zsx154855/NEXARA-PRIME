"""CAB-01 real canonical SQLite/ApprovalEngine contract tests.

OpenMausBot itself is replaced by an inert deterministic transport. These
are NOT a real provider, paid model, OS sandbox or live three-Agent tests.
"""
from datetime import datetime, timedelta, timezone
import pytest

from nexara_prime.contract_engine import ContractEngine
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.governance import ApprovalEngine, PolicyEngine
from nexara_prime.integrations.cab01_admission import (
    CAB01AdmissionDenied, CAB01TrustedAdmission, _digest,
)
from nexara_prime.integrations.openmausbot_execution import ExecutionProof, ProofError, TaskLedger
from nexara_prime.kernel_boundary import KernelAdmissionContext, KernelExecutionGuard
from nexara_prime.models import MissionSpec, RiskLevel, now_iso


PROJECT = "nexara-cab01-synthetic"
PROPOSAL = "coggoal-cab01-synthetic"
MISSION = "mission-cab01-synthetic"
BOT = "research-lead"
THREAD = "dedicated-cab01-thread"
IDENTITY = "isolated-nexara-executor"
ENGINE = "offline-fixture"
OWNER = "trusted-cab-lab-owner"
OBJECTIVE = "Investigate and fix a synthetic local test failure"


class OfflineCLI:
    """Records OS-facing calls without starting OpenMausBot or any model."""
    def __init__(self):
        self.calls = []

    def call(self, verb, *args, **kwargs):
        self.calls.append((verb, args))
        if verb == "run":
            return 0, {"ok": True, "threadId": THREAD, "messageId": "msg-cab01",
                       "sendId": args[args.index("--send-id") + 1],
                       "since": 1000, "at": 1001}
        if verb == "wait":
            return 0, {"ok": True, "state": "completed", "taskId": THREAD,
                       "job": {"threadId": THREAD, "since": 1000, "counts": {"failed": 0},
                               "nodes": [{"id": "lead", "botId": BOT, "status": "completed"}]}}
        raise AssertionError(f"unrecognized fake I/O: {verb}")


def lab(tmp_path, *, engine=ENGINE, expires_seconds=900,
        approval_scope="mission", status="approved", cost_limit=0.0,
        bot=BOT, thread=THREAD, allowed_actions=None, approval_present=True):
    root = tmp_path / "authorized_root"
    root.mkdir()
    workspace = root / "sandbox"
    workspace.mkdir()
    store = SQLiteStore(tmp_path / "canonical.db")
    events = EventBus(store)
    approvals = ApprovalEngine(store, events)
    policy = PolicyEngine()
    proposal = {"proposal_id": PROPOSAL, "project_id": PROJECT, "status": "HYPOTHESIS",
                "objective": "Investigate observed failing tests", "execution_authorized": False,
                "event_ids": ["evt1"], "evidence_refs": [], "risk_level": "R0",
                "source": "fix_failing_tests", "cost_limit": 0}
    assert store.save_record_if_absent(PROPOSAL, "cognitive_goal_proposal_v1", proposal, now_iso(), PROJECT)
    spec = MissionSpec(mission_id=MISSION, title="CAB-01 synthetic", objective=OBJECTIVE,
                       risk_level=RiskLevel.R2)
    contract = ContractEngine().create(spec)
    if status == "approved":
        contract = ContractEngine().approve(contract)
    contract = contract.model_copy(update={
        "status": status, "provenance": PROPOSAL, "project_id": PROJECT,
        "authorized_workspace": str(workspace), "allowed_actions": (
            allowed_actions if allowed_actions is not None else ["openmausbot.run"]),
        "execution_backend": "openmausbot", "execution_bot_id": bot,
        "execution_thread_id": thread, "execution_identity": IDENTITY,
        "execution_engine": engine, "cost_limit": cost_limit,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)).isoformat(),
    })
    assert store.save_record_if_absent(
        contract.contract_id, "work_contract", contract.model_dump(mode="json"),
        now_iso(), MISSION)
    approval_id = None
    if approval_present:
        approval = approvals.request(
            mission_id=MISSION, action="openmausbot.run", risk_level=RiskLevel.R2,
            rationale="Owner-approved confined synthetic lab", impact=[],
            trace_id="cab01-test", affected_resources=[str(workspace)],
            external_effect=True, estimated_cost=0.0, approval_scope=approval_scope,
            executor_id=IDENTITY, proposal_sha256=_digest(contract.model_dump(mode="json")),
            expires_in_seconds=900,
        )
        approvals.decide(approval.approval_id, approved=True, actor=OWNER,
                         note="Approved only for this temporary lab", trace_id="cab01-test")
        approval_id = approval.approval_id
    # This is a TEST-ONLY trusted controller claim. It does not authenticate
    # a real host principal; CAB01TrustedAdmission still validates canonical
    # SQLite contract, ApprovalEngine transitions, scope and revocation.
    guard = KernelExecutionGuard(
        _live_admission_validator=lambda ctx: ctx.caller == "trusted_cab_controller"
    )
    guard.admit(KernelAdmissionContext(
        mission_id=MISSION, caller="trusted_cab_controller",
        contract_verified=True, authority_verified=True,
        state_valid=True, governance_approved=True,
        evidence_chain_initialized=True,
        metadata={"contract_id": contract.contract_id, "contract_version": contract.version},
    ))
    authority = CAB01TrustedAdmission(
        store, approvals, policy, workspace_root=root,
        execution_identity=IDENTITY,
        verified_zero_cost_engines=frozenset({ENGINE}),
        trusted_deciders=frozenset({OWNER}), guard=guard,
    )
    cli = OfflineCLI()
    proof = ExecutionProof(TaskLedger(tmp_path / "transport.db"), cli, authority=authority)
    return {"proof": proof, "cli": cli, "contract": contract, "store": store,
            "events": events, "approvals": approvals, "approval_id": approval_id,
            "workspace": workspace, "root": root, "authority": authority, "proposal": proposal}


def send(s):
    return s["proof"].submit(MISSION, BOT, THREAD, OBJECTIVE)


def test_authorized_durable_mission_runs_and_reports_only(tmp_path):
    s = lab(tmp_path)
    assert s["authority"].authorize(MISSION, BOT, THREAD, OBJECTIVE).contract_id == s["contract"].contract_id
    record = send(s)
    assert record["status"] == "SENT"
    assert record["since_ms"] == 1000
    assert s["proof"].reconcile(MISSION)["status"] == "REPORTED"
    assert [v[0] for v in s["cli"].calls] == ["run", "wait"]
    assert s["proof"].team_evidence(MISSION)["qa_verified"] is False


def test_restart_uses_identical_mission_without_resending(tmp_path):
    s = lab(tmp_path)
    first = send(s)
    reopened = ExecutionProof(TaskLedger(tmp_path / "transport.db"),
                              s["cli"], authority=s["authority"])
    assert reopened.submit(MISSION, BOT, THREAD, OBJECTIVE)["send_id"] == first["send_id"]
    assert reopened.reconcile(MISSION)["status"] == "REPORTED"
    assert len([c for c in s["cli"].calls if c[0] == "run"]) == 1


def test_model_flag_does_not_grant_execution(tmp_path):
    s = lab(tmp_path, approval_present=False)
    claimed = dict(s["proposal"], execution_authorized=True)
    with pytest.raises(ProofError, match="kernel_admission_required"):
        s["proof"].submit_proposal(claimed, BOT, THREAD, contract=s["contract"], guard=None)
    # The low-level path is protected, too.
    with pytest.raises(ProofError, match="missing_unique_trusted_approval"):
        send(s)
    assert not s["cli"].calls
    assert s["proof"].ledger.get(MISSION) is None


@pytest.mark.parametrize("mutate", [
    "wrong_bot", "wrong_thread", "wrong_mission", "changed_objective",
])
def test_mismatched_execution_identity_cannot_dispatch(tmp_path, mutate):
    s = lab(tmp_path)
    args = [MISSION, BOT, THREAD, OBJECTIVE]
    replacements = {"wrong_bot": (1, "another-bot"), "wrong_thread": (2, "other-thread"),
                    "wrong_mission": (0, "old-mission"), "changed_objective": (3, "other patch")}
    at, replacement = replacements[mutate]
    args[at] = replacement
    with pytest.raises(ProofError, match="admission_denied"):
        s["proof"].submit(*args)
    assert not s["cli"].calls


def test_unknown_or_nonverified_model_cost_fails_closed(tmp_path):
    s = lab(tmp_path, engine="remote-unverified-model")
    s["authority"].verified_zero_cost_engines = frozenset()
    with pytest.raises(ProofError, match="model_budget_not_verified"):
        send(s)
    assert not s["cli"].calls


def test_nonzero_budget_not_allowed_for_zero_incremental_cost_lab(tmp_path):
    s = lab(tmp_path, cost_limit=1.0)
    with pytest.raises(ProofError, match="model_budget_not_verified"):
        send(s)


def test_expired_durable_contract_rejected(tmp_path):
    s = lab(tmp_path, expires_seconds=-1)
    with pytest.raises(ProofError, match="work_contract_not_current"):
        send(s)
    assert not s["cli"].calls


def test_unapproved_durable_contract_rejected(tmp_path):
    s = lab(tmp_path, status="validated")
    with pytest.raises(ProofError, match="work_contract_not_current"):
        send(s)


def test_single_action_approval_not_treated_as_mission_grant(tmp_path):
    s = lab(tmp_path, approval_scope="single_action")
    with pytest.raises(ProofError, match="approval_scope_invalid_or_expired"):
        send(s)


def test_new_contract_status_cannot_be_forged_by_in_memory_model(tmp_path):
    s = lab(tmp_path, status="draft")
    forged = s["contract"].model_copy(update={"status": "approved",
                                             "approved_at": now_iso()})
    assert forged.status == "approved"
    with pytest.raises(ProofError, match="work_contract_not_current"):
        send(s)


def test_workspace_symlink_retargeting_invalidates_prior_approval(tmp_path):
    s = lab(tmp_path)
    existing = s["workspace"]
    old = tmp_path / "old_sandbox"
    existing.rename(old)
    existing.symlink_to(old, target_is_directory=True)
    with pytest.raises(ProofError, match="workspace_scope_invalid"):
        send(s)
    assert not s["cli"].calls


def test_approved_durable_contract_cannot_be_mutated_after_grant(tmp_path):
    s = lab(tmp_path)
    contract = s["contract"]
    changed = contract.model_copy(update={"execution_bot_id": "different-bot"})
    s["store"].save_record(
        contract.contract_id, "work_contract", changed.model_dump(mode="json"), now_iso(), MISSION)
    with pytest.raises(ProofError, match="work_contract_not_current"):
        send(s)


def test_authorization_revoked_prevents_new_side_effects(tmp_path):
    s = lab(tmp_path)
    s["events"].publish("approval.revoked", MISSION, "mission", OWNER, "cab01-test",
                        {"approval_id": s["approval_id"]})
    with pytest.raises(ProofError, match="authorization_revoked"):
        send(s)
    assert not s["cli"].calls


def test_revocation_after_submission_blocks_new_resume_io(tmp_path):
    s = lab(tmp_path)
    assert send(s)["status"] == "SENT"
    s["events"].publish("approval.revoked", MISSION, "mission", OWNER, "cab01-test",
                        {"approval_id": s["approval_id"]})
    with pytest.raises(ProofError, match="authorization_revoked"):
        s["proof"].reconcile(MISSION)
    assert [c[0] for c in s["cli"].calls] == ["run"]
    assert s["proof"].ledger.get(MISSION)["status"] == "SENT"


def test_unexpected_operation_type_rejected(tmp_path):
    s = lab(tmp_path, allowed_actions=["file_read"])
    with pytest.raises(ProofError, match="execution_scope_mismatch"):
        send(s)


def test_mismatched_approval_signature_rejected(tmp_path):
    s = lab(tmp_path)
    s["store"].save_record("some_unrelated_key", "work_contract",
                           {"not": "a valid contract"}, now_iso(), "another-mission")
    with pytest.raises(ProofError, match="admission_denied"):
        s["proof"].submit("another-mission", BOT, THREAD, OBJECTIVE)
    assert not s["cli"].calls


def test_approved_hypothesis_remains_non_executable_by_itself(tmp_path):
    s = lab(tmp_path)
    assert s["proposal"]["status"] == "HYPOTHESIS"
    assert s["proposal"]["execution_authorized"] is False
    assert s["store"].get_record_envelope(PROPOSAL)["payload"] == s["proposal"]
    # Executable authority comes from independent durable approval, not this
    # record's epistemic status.
    assert s["authority"].authorize(MISSION, BOT, THREAD, OBJECTIVE).mission_id == MISSION


def test_fake_full_kernel_context_cannot_invent_missing_durable_approval(tmp_path):
    s = lab(tmp_path, approval_present=False)
    contract = s["contract"]
    # Explicitly admit a forged model context ONLY inside this isolated
    # negative fixture to prove that it cannot create a missing durable
    # CAB approval. This lambda must never be wired into product Runtime.
    guard = KernelExecutionGuard(
        _live_admission_validator=lambda ctx: ctx.caller == "model_supplied"
    )
    guard.admit(KernelAdmissionContext(
        mission_id=MISSION, caller="model_supplied", contract_verified=True,
        authority_verified=True, state_valid=True, governance_approved=True,
        evidence_chain_initialized=True,
        metadata={"contract_id": contract.contract_id},
    ))
    with pytest.raises(ProofError, match="missing_unique_trusted_approval"):
        s["proof"].submit_proposal(s["proposal"], BOT, THREAD, contract=contract, guard=guard)
    assert not s["cli"].calls


def test_older_contract_grant_does_not_authorize_new_version(tmp_path):
    s = lab(tmp_path)
    newer = s["contract"].model_copy(update={
        "contract_id": "cab-newer-contract",
        "version": s["contract"].version + 1,
        "status": "draft",
    })
    assert s["store"].save_record_if_absent(
        newer.contract_id, "work_contract", newer.model_dump(mode="json"),
        now_iso(), MISSION)
    with pytest.raises(ProofError, match="work_contract_not_current"):
        send(s)
    assert not s["cli"].calls


def test_revoking_inflight_contract_still_allows_inspection_not_new_wait(tmp_path):
    s = lab(tmp_path)
    send(s)
    s["events"].publish("cab.contract.revoked", MISSION, "mission", OWNER,
                        "cab01-test", {"approval_id": s["approval_id"]})
    with pytest.raises(ProofError, match="authorization_revoked"):
        s["proof"].reconcile(MISSION)
    assert s["proof"].ledger.get(MISSION)["status"] == "SENT"
    assert [x[0] for x in s["cli"].calls] == ["run"]


def test_current_contract_with_tampered_project_id_fails(tmp_path):
    s = lab(tmp_path)
    contract = s["contract"]
    mutated = contract.model_copy(update={"project_id": "other-project"})
    s["store"].save_record(contract.contract_id, "work_contract",
                           mutated.model_dump(mode="json"), now_iso(), MISSION)
    with pytest.raises(ProofError, match="work_contract_not_current"):
        send(s)


def test_guard_missing_admission_blocks_even_with_persisted_approval(tmp_path):
    s = lab(tmp_path)
    s["authority"].guard.clear()
    with pytest.raises(ProofError, match="kernel_admission_required"):
        send(s)
    assert not s["cli"].calls


def test_guard_wrong_contract_version_blocks_even_if_flags_are_true(tmp_path):
    s = lab(tmp_path)
    s["authority"].guard.assert_admitted(MISSION).metadata["contract_version"] = 99
    with pytest.raises(ProofError, match="kernel_contract_binding_invalid"):
        send(s)
    assert not s["cli"].calls
