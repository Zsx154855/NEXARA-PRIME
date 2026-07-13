from __future__ import annotations

import threading
from pathlib import Path

from nexara_prime.db import SQLiteStore
from nexara_prime.evidence import EvidenceStore
from nexara_prime.events import EventBus
from nexara_prime.governance import ApprovalEngine
from nexara_prime.models import ApprovalStatus, RiskLevel
from nexara_prime.product_reality import (
    EvolutionPromotionGate,
    EvolutionProposal,
    EvolutionValidation,
    ProductTwinEngine,
    ValuePresence,
)


def runtime(tmp_path: Path):
    store = SQLiteStore(tmp_path / "nexara.sqlite3")
    events = EventBus(store)
    evidence = EvidenceStore(store, events)
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    gate = EvolutionPromotionGate(
        approvals,
        evidence,
        authorized_human_principals={"human:owner"},
    )
    return store, evidence, approvals, twin, gate


def verified_evidence(evidence: EvidenceStore, mission_id: str, title: str = "proof"):
    return evidence.add(
        mission_id,
        "verification",
        title,
        "digest-bound proof",
        "trace-1",
        source="test",
        verification_status="verified",
    )


def proposal(
    evidence: EvidenceStore,
    twin: ProductTwinEngine,
    *,
    mission_id: str = "mission-1",
    risk: RiskLevel = RiskLevel.R3,
):
    proof = verified_evidence(evidence, mission_id)
    rollback = verified_evidence(evidence, mission_id, "rollback")
    checkpoint = twin.capture(
        mission_id=mission_id,
        expected_state={"version": 1},
        observed_state={"version": 1},
        evidence_refs=[rollback.evidence_id],
        reversible=True,
    )
    return EvolutionProposal(
        mission_id=mission_id,
        title="Harden promotion",
        observed_problem={"kind": "review"},
        proposed_changes=["bind authorization"],
        risk_level=risk,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore checkpoint"],
        rollback_checkpoint_id=checkpoint.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )


def validation_for(
    approvals: ApprovalEngine,
    item: EvolutionProposal,
    *,
    actor_id: str = "executor-1",
    executor_id: str | None = "executor-1",
    decided_by: str = "human:owner",
    risk: RiskLevel | None = None,
):
    approval = approvals.request(
        item.mission_id,
        item.promotion_action,
        risk or item.risk_level,
        "approve promotion",
        ["product reality"],
        "trace-approval",
        executor_id=executor_id,
        approval_scope="single_action",
    )
    approvals.decide(
        approval.approval_id,
        True,
        decided_by,
        "approved",
        "trace-decision",
    )
    return EvolutionValidation(
        simulation_passed=True,
        verification_passed=True,
        accessibility_passed=True,
        governance_passed=True,
        approval_id=approval.approval_id,
        actor_id=actor_id,
    ), approval.approval_id


def test_unverified_evidence_is_rejected_without_mutation(tmp_path: Path) -> None:
    store, evidence, approvals, twin, gate = runtime(tmp_path)
    item = proposal(evidence, twin, risk=RiskLevel.R0)
    raw = store.get_record(item.evidence_refs[0])
    raw["verification_status"] = "unverified"
    raw["envelope_sha256"] = evidence._envelope_sha256(raw)
    store.save_record(raw["evidence_id"], "evidence", raw, raw["created_at"], raw["mission_id"])

    decision = gate.assess(
        item,
        EvolutionValidation(verification_passed=True),
    )

    assert decision.allowed is False
    assert any("not pre-verified" in action for action in decision.required_actions)
    assert store.get_record(item.evidence_refs[0])["verification_status"] == "unverified"


def test_evidence_mission_metadata_tamper_breaks_envelope(tmp_path: Path) -> None:
    store, evidence, approvals, twin, gate = runtime(tmp_path)
    item = proposal(evidence, twin, mission_id="mission-1", risk=RiskLevel.R0)
    raw = store.get_record(item.evidence_refs[0])
    raw["mission_id"] = "mission-2"
    store.save_record(raw["evidence_id"], "evidence", raw, raw["created_at"], "mission-2")
    item.mission_id = "mission-2"

    decision = gate.assess(item, EvolutionValidation(verification_passed=True))

    assert decision.allowed is False
    assert any("envelope verification" in action for action in decision.required_actions)


def test_executor_must_be_non_empty_and_exact(tmp_path: Path) -> None:
    _, evidence, approvals, twin, gate = runtime(tmp_path)
    item = proposal(evidence, twin)
    validation, _ = validation_for(approvals, item, executor_id=None)

    decision = gate.assess(item, validation)

    assert decision.allowed is False
    assert "stored promotion approval executor mismatch" in decision.required_actions


def test_approval_risk_must_match_proposal(tmp_path: Path) -> None:
    _, evidence, approvals, twin, gate = runtime(tmp_path)
    item = proposal(evidence, twin, risk=RiskLevel.R3)
    validation, _ = validation_for(approvals, item, risk=RiskLevel.R1)

    decision = gate.assess(item, validation)

    assert decision.allowed is False
    assert "stored promotion approval risk mismatch" in decision.required_actions


def test_decision_actor_must_be_authorized_human(tmp_path: Path) -> None:
    _, evidence, approvals, twin, gate = runtime(tmp_path)
    item = proposal(evidence, twin)
    validation, _ = validation_for(approvals, item, decided_by="runtime")

    decision = gate.assess(item, validation)

    assert decision.allowed is False
    assert any("authorized human" in action for action in decision.required_actions)


def test_checkpoint_must_exist_and_match_mission(tmp_path: Path) -> None:
    _, evidence, approvals, twin, gate = runtime(tmp_path)
    item = proposal(evidence, twin, risk=RiskLevel.R2)
    item.rollback_checkpoint_id = "twin_missing"

    decision = gate.assess(
        item,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
        ),
    )

    assert decision.allowed is False
    assert "stored rollback checkpoint not found" in decision.required_actions


def test_nested_list_preserves_missing_vs_null(tmp_path: Path) -> None:
    _, _, _, twin, _ = runtime(tmp_path)

    findings = twin.detect_drift(
        mission_id="mission-1",
        expected={"components": [{}]},
        observed={"components": [{"subtitle": None}]},
    )

    assert len(findings) == 1
    assert findings[0].path == "$.components[0].subtitle"
    assert findings[0].expected.presence == ValuePresence.MISSING
    assert findings[0].observed.presence == ValuePresence.PRESENT
    assert findings[0].observed.value is None


def test_single_action_approval_is_consumed_once_under_concurrency(tmp_path: Path) -> None:
    store, evidence, approvals, twin, gate = runtime(tmp_path)
    item = proposal(evidence, twin)
    validation, approval_id = validation_for(approvals, item)
    barrier = threading.Barrier(2)
    results: list[bool] = []

    def assess() -> None:
        barrier.wait()
        results.append(gate.assess(item, validation).allowed)

    threads = [threading.Thread(target=assess) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [False, True]
    assert store.get_record(approval_id)["status"] == ApprovalStatus.CONSUMED.value
