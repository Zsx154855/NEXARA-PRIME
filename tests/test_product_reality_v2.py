from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from nexara_prime.db import SQLiteStore
from nexara_prime.evidence import EvidenceStore
from nexara_prime.events import EventBus
from nexara_prime.governance import ApprovalEngine
from nexara_prime.models import ApprovalStatus, RiskLevel
from nexara_prime.product_reality import (
    DriftType,
    EvolutionPromotionGate,
    EvolutionProposal,
    EvolutionValidation,
    ExperienceGene,
    ExperienceGenomeRegistry,
    ProductSurface,
    ProductTwinEngine,
    ValuePresence,
)


@pytest.fixture
def services(tmp_path):
    store = SQLiteStore(tmp_path / "product-reality-v2.db")
    events = EventBus(store)
    approvals = ApprovalEngine(store, events)
    evidence = EvidenceStore(store, events)
    gate = EvolutionPromotionGate(
        approvals,
        evidence,
        authorized_human_principals={"human_owner"},
    )
    twin = ProductTwinEngine(store)
    yield store, approvals, evidence, gate, twin
    store.close()


def add_evidence(
    evidence: EvidenceStore,
    *,
    mission_id: str,
    title: str,
    verified: bool = True,
) -> str:
    artifact = evidence.add(
        mission_id=mission_id,
        kind="product_reality_verification",
        title=title,
        content=f"evidence:{mission_id}:{title}",
        trace_id="trace_product_reality_v2",
        source="product_reality_test",
        verification_status="unverified",
    )
    if verified:
        assert evidence.verify(artifact.evidence_id) is True
    return artifact.evidence_id


def create_checkpoint(twin: ProductTwinEngine, mission_id: str) -> str:
    checkpoint = twin.capture(
        mission_id=mission_id,
        expected_state={"experience": {"version": 1}},
        observed_state={"experience": {"version": 1}},
        reversible=True,
        rollback_ref="snapshot://before-change",
    )
    return checkpoint.checkpoint_id


def make_proposal(
    *,
    mission_id: str,
    risk: RiskLevel,
    evidence_ref: str,
    checkpoint_id: str | None = None,
    rollback_evidence_ref: str | None = None,
    proposal_id: str = "evolution_test_001",
) -> EvolutionProposal:
    values = {
        "proposal_id": proposal_id,
        "mission_id": mission_id,
        "title": "Improve governed experience",
        "observed_problem": {"metric": "verified_outcome_time"},
        "proposed_changes": ["surface runtime truth earlier"],
        "risk_level": risk,
        "evidence_refs": [evidence_ref],
    }
    if risk in (RiskLevel.R2, RiskLevel.R3, RiskLevel.R4):
        values.update(
            rollback_plan=["restore previous experience projection"],
            rollback_checkpoint_id=checkpoint_id,
            rollback_evidence_refs=[rollback_evidence_ref or evidence_ref],
        )
    return EvolutionProposal(**values)


def complete_validation(**overrides) -> EvolutionValidation:
    values = {
        "simulation_passed": True,
        "verification_passed": True,
        "accessibility_passed": True,
        "governance_passed": True,
        "actor_id": "evolution_executor",
    }
    values.update(overrides)
    return EvolutionValidation(**values)


def create_approved_record(
    approvals: ApprovalEngine,
    *,
    proposal: EvolutionProposal,
    action: str,
    actor_id: str | None = "evolution_executor",
    risk: RiskLevel | None = None,
    decided_by: str = "human_owner",
) -> str:
    approval = approvals.request(
        mission_id=proposal.mission_id,
        action=action,
        risk_level=risk or proposal.risk_level,
        rationale="Authorize one exact product-reality action",
        impact=["product experience projection"],
        trace_id="trace_approval_v2",
        approval_scope="single_action",
        executor_id=actor_id,
        reversible=True,
        rollback_plan={"checkpoint": proposal.rollback_checkpoint_id},
    )
    approvals.decide(
        approval.approval_id,
        approved=True,
        actor=decided_by,
        note="Reviewed exact proposal scope",
        trace_id="trace_approval_decision_v2",
        decision="approve_once",
    )
    return approval.approval_id


class TestExperienceGenome:
    def test_registry_and_projection_contract(self) -> None:
        registry = ExperienceGenomeRegistry()
        gene = ExperienceGene(
            gene_id="gene_approval",
            name="Human Approval Gate",
            purpose="Keep consequential evolution under human authority.",
            activates_when={"risk_tier": ["R3", "R4"]},
            must_show=["action_summary", "rollback_availability"],
            controls=["approve", "reject"],
            prohibited=["implicit_approval"],
            platform_expression={"iOS": "focused_approval_surface"},
        )
        registry.register(gene)
        assert registry.resolve({"risk_tier": "R3"}) == [gene]
        errors = registry.validate_projection(
            gene,
            surface=ProductSurface.IOS,
            visible_objects={"action_summary", "implicit_approval"},
            available_controls={"approve"},
        )
        assert len(errors) == 3
        with pytest.raises(ValueError):
            registry.register(gene)


class TestProductTwin:
    def test_missing_null_inside_list_is_field_level(self) -> None:
        findings = ProductTwinEngine().detect_drift(
            mission_id="mission_list_drift",
            expected={"components": [{}]},
            observed={"components": [{"accessibility_label": None}]},
        )
        assert len(findings) == 1
        finding = findings[0]
        assert finding.path == "$.components[0].accessibility_label"
        assert finding.expected.presence == ValuePresence.MISSING
        assert finding.observed.presence == ValuePresence.PRESENT
        assert finding.observed.value is None
        assert finding.drift_type == DriftType.ACCESSIBILITY_REGRESSION

    def test_checkpoint_is_persisted_and_integrity_bound(self, services) -> None:
        store, _, _, _, twin = services
        checkpoint_id = create_checkpoint(twin, "mission_checkpoint")
        envelope = store.get_record_envelope(checkpoint_id)
        assert envelope is not None
        assert envelope["record_type"] == "product_twin_checkpoint"
        assert envelope["mission_id"] == "mission_checkpoint"


class TestEvidenceAndRollback:
    def test_unverified_evidence_is_rejected_without_self_verification(self, services) -> None:
        _, _, evidence, gate, _ = services
        ref = add_evidence(
            evidence,
            mission_id="mission_unverified",
            title="unverified",
            verified=False,
        )
        proposal = make_proposal(
            mission_id="mission_unverified",
            risk=RiskLevel.R0,
            evidence_ref=ref,
        )
        decision = gate.assess(
            proposal,
            EvolutionValidation(verification_passed=True),
        )
        assert decision.allowed is False
        assert any("not pre-verified" in item for item in decision.required_actions)
        assert evidence.store.get_record(ref)["verification_status"] == "unverified"

    def test_mission_metadata_tampering_breaks_integrity(self, services) -> None:
        store, _, evidence, gate, _ = services
        ref = add_evidence(evidence, mission_id="mission_a", title="bound")
        with store._lock, store._conn:
            row = store._conn.execute(
                "SELECT payload FROM records WHERE record_id=?", (ref,)
            ).fetchone()
            payload = json.loads(row["payload"])
            payload["mission_id"] = "mission_b"
            store._conn.execute(
                "UPDATE records SET mission_id=?, payload=? WHERE record_id=?",
                ("mission_b", json.dumps(payload), ref),
            )
        proposal = make_proposal(
            mission_id="mission_b",
            risk=RiskLevel.R0,
            evidence_ref=ref,
        )
        decision = gate.assess(
            proposal,
            EvolutionValidation(verification_passed=True),
        )
        assert decision.allowed is False
        assert any("integrity envelope invalid" in item for item in decision.required_actions)

    def test_arbitrary_checkpoint_id_is_rejected(self, services) -> None:
        _, _, evidence, gate, _ = services
        mission_id = "mission_missing_checkpoint"
        promotion = add_evidence(evidence, mission_id=mission_id, title="promotion")
        rollback = add_evidence(evidence, mission_id=mission_id, title="rollback")
        proposal = make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R2,
            evidence_ref=promotion,
            rollback_evidence_ref=rollback,
            checkpoint_id="not_a_real_checkpoint",
        )
        decision = gate.assess(proposal, complete_validation())
        assert decision.allowed is False
        assert any("checkpoint not found" in item for item in decision.required_actions)

    def test_r2_passes_with_persisted_checkpoint(self, services) -> None:
        _, _, evidence, gate, twin = services
        mission_id = "mission_r2_valid"
        promotion = add_evidence(evidence, mission_id=mission_id, title="promotion")
        rollback = add_evidence(evidence, mission_id=mission_id, title="rollback")
        checkpoint = create_checkpoint(twin, mission_id)
        proposal = make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R2,
            evidence_ref=promotion,
            rollback_evidence_ref=rollback,
            checkpoint_id=checkpoint,
        )
        assert gate.assess(proposal, complete_validation()).allowed is True

    def test_contract_rejects_missing_recovery_path(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionProposal(
                mission_id="mission_no_recovery",
                title="Unsafe change",
                observed_problem={},
                proposed_changes=["change"],
                risk_level=RiskLevel.R2,
                evidence_refs=["evidence_placeholder"],
            )


class TestApprovalBinding:
    def r3_proposal(self, services, mission_id: str) -> EvolutionProposal:
        _, _, evidence, _, twin = services
        promotion = add_evidence(evidence, mission_id=mission_id, title="promotion")
        rollback = add_evidence(evidence, mission_id=mission_id, title="rollback")
        checkpoint = create_checkpoint(twin, mission_id)
        return make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R3,
            evidence_ref=promotion,
            rollback_evidence_ref=rollback,
            checkpoint_id=checkpoint,
        )

    def test_executor_binding_is_mandatory(self, services) -> None:
        _, approvals, _, gate, _ = services
        proposal = self.r3_proposal(services, "mission_executor")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
            actor_id=None,
        )
        decision = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )
        assert decision.allowed is False
        assert any("executor binding" in item for item in decision.required_actions)

    def test_approval_risk_must_match(self, services) -> None:
        _, approvals, _, gate, _ = services
        proposal = self.r3_proposal(services, "mission_risk")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
            risk=RiskLevel.R1,
        )
        decision = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )
        assert decision.allowed is False
        assert any("risk mismatch" in item for item in decision.required_actions)

    def test_decider_must_be_authorized_human(self, services) -> None:
        _, approvals, _, gate, _ = services
        proposal = self.r3_proposal(services, "mission_human")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
            decided_by="runtime",
        )
        decision = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )
        assert decision.allowed is False
        assert any("authorized human" in item for item in decision.required_actions)

    def test_expired_approval_is_rejected(self, services) -> None:
        store, approvals, _, gate, _ = services
        proposal = self.r3_proposal(services, "mission_expired")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
        )
        raw = store.get_record(approval_id)
        raw["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        store.save_record(
            approval_id, "approval", raw, raw["created_at"], proposal.mission_id
        )
        decision = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )
        assert decision.allowed is False
        assert any("expired" in item for item in decision.required_actions)

    def test_single_action_approval_is_consumed_once_under_concurrency(self, services) -> None:
        _, approvals, _, gate, _ = services
        proposal = self.r3_proposal(services, "mission_concurrent")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
        )
        validation = complete_validation(approval_id=approval_id)
        barrier = threading.Barrier(2)
        decisions = []

        def run_assessment() -> None:
            barrier.wait()
            decisions.append(gate.assess(proposal, validation))

        threads = [threading.Thread(target=run_assessment) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sum(decision.allowed for decision in decisions) == 1
        assert approvals.get(approval_id).status == ApprovalStatus.CONSUMED

    def test_valid_r3_approval_passes_and_is_consumed(self, services) -> None:
        _, approvals, _, gate, _ = services
        proposal = self.r3_proposal(services, "mission_valid_r3")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
        )
        decision = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )
        assert decision.allowed is True
        assert decision.consumed_approval_ids == [approval_id]
        assert approvals.get(approval_id).status == ApprovalStatus.CONSUMED
