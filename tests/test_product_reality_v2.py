from __future__ import annotations

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
    gate = EvolutionPromotionGate(approvals, evidence)
    yield store, approvals, evidence, gate
    store.close()


def add_verified_evidence(
    evidence: EvidenceStore,
    *,
    mission_id: str,
    title: str = "verification",
) -> str:
    artifact = evidence.add(
        mission_id=mission_id,
        kind="product_reality_verification",
        title=title,
        content=f"verified evidence for {mission_id}: {title}",
        trace_id="trace_product_reality_v2",
        source="product_reality_test",
        verification_status="verified",
    )
    assert evidence.verify(artifact.evidence_id) is True
    return artifact.evidence_id


def make_proposal(
    *,
    mission_id: str,
    risk: RiskLevel,
    evidence_ref: str,
    rollback_evidence_ref: str | None = None,
    proposal_id: str = "evolution_test_001",
) -> EvolutionProposal:
    kwargs = {
        "proposal_id": proposal_id,
        "mission_id": mission_id,
        "title": "Improve governed experience",
        "observed_problem": {"metric": "verified_outcome_time", "change_pct": 12},
        "proposed_changes": ["surface runtime truth earlier"],
        "risk_level": risk,
        "evidence_refs": [evidence_ref],
    }
    if risk in (RiskLevel.R2, RiskLevel.R3, RiskLevel.R4):
        kwargs.update(
            rollback_plan=["restore previous experience projection"],
            rollback_checkpoint_id="checkpoint_before_change",
            rollback_evidence_refs=[rollback_evidence_ref or evidence_ref],
        )
    return EvolutionProposal(**kwargs)


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
    actor_id: str = "evolution_executor",
) -> str:
    approval = approvals.request(
        mission_id=proposal.mission_id,
        action=action,
        risk_level=proposal.risk_level,
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
        actor="human_owner",
        note="Reviewed exact proposal scope",
        trace_id="trace_approval_decision_v2",
        decision="approve_once",
    )
    return approval.approval_id


class TestExperienceGenomeV2:
    def approval_gene(self) -> ExperienceGene:
        return ExperienceGene(
            gene_id="gene_human_approval_gate_v2",
            name="Human Approval Gate",
            purpose="Keep consequential evolution under explicit human authority.",
            activates_when={
                "risk_tier": ["R3", "R4"],
                "execution_environment": "live_external",
            },
            must_show=[
                "action_summary",
                "execution_environment",
                "rollback_availability",
            ],
            controls=["approve", "modify", "reject", "safe_mode"],
            prohibited=["implicit_approval"],
            platform_expression={
                "macOS": "inspector_and_control_plane",
                "iPadOS": "split_review_and_bottom_control",
                "iOS": "focused_approval_surface",
            },
            verification_rules=["stored_approval_is_bound"],
        )

    def test_resolves_matching_gene(self) -> None:
        registry = ExperienceGenomeRegistry()
        gene = self.approval_gene()
        registry.register(gene)

        resolved = registry.resolve(
            {"risk_tier": "R3", "execution_environment": "live_external"}
        )

        assert [item.gene_id for item in resolved] == [gene.gene_id]

    def test_rejects_non_increasing_version(self) -> None:
        registry = ExperienceGenomeRegistry()
        registry.register(self.approval_gene())

        with pytest.raises(ValueError):
            registry.register(self.approval_gene())

    def test_projection_validation_detects_missing_and_prohibited_objects(self) -> None:
        registry = ExperienceGenomeRegistry()
        gene = self.approval_gene()

        errors = registry.validate_projection(
            gene,
            surface=ProductSurface.IOS,
            visible_objects={"action_summary", "implicit_approval"},
            available_controls={"approve"},
        )

        assert any("missing required objects" in item for item in errors)
        assert any("missing required controls" in item for item in errors)
        assert any("prohibited objects present" in item for item in errors)


class TestProductTwinV2:
    def test_identical_states_have_no_drift(self) -> None:
        checkpoint = ProductTwinEngine().capture(
            mission_id="mission_twin_1",
            expected_state={"runtime": {"status": "running"}},
            observed_state={"runtime": {"status": "running"}},
        )

        assert checkpoint.drift_findings == []
        assert checkpoint.expected.state_sha256 == checkpoint.observed.state_sha256

    def test_missing_and_present_null_remain_distinct(self) -> None:
        findings = ProductTwinEngine().detect_drift(
            mission_id="mission_twin_2",
            expected={},
            observed={"optional_field": None},
        )

        assert len(findings) == 1
        finding = findings[0]
        assert finding.expected.presence == ValuePresence.MISSING
        assert finding.observed.presence == ValuePresence.PRESENT
        assert finding.observed.value is None

    def test_present_null_and_missing_remain_distinct_in_reverse(self) -> None:
        findings = ProductTwinEngine().detect_drift(
            mission_id="mission_twin_3",
            expected={"optional_field": None},
            observed={},
        )

        finding = findings[0]
        assert finding.expected.presence == ValuePresence.PRESENT
        assert finding.expected.value is None
        assert finding.observed.presence == ValuePresence.MISSING

    def test_policy_drift_is_r3(self) -> None:
        finding = ProductTwinEngine().detect_drift(
            mission_id="mission_twin_4",
            expected={"approval": {"required": True}},
            observed={"approval": {"required": False}},
        )[0]

        assert finding.drift_type == DriftType.POLICY_VIOLATION
        assert finding.severity == RiskLevel.R3

    def test_diff_order_is_deterministic(self) -> None:
        findings = ProductTwinEngine().detect_drift(
            mission_id="mission_twin_5",
            expected={"z": 1, "a": 1},
            observed={"z": 2, "a": 2},
        )

        assert [finding.path for finding in findings] == ["$.a", "$.z"]


class TestEvolutionEvidenceV2:
    def test_proposal_requires_evidence_for_every_risk(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionProposal(
                mission_id="mission_evidence_1",
                title="No evidence",
                observed_problem={},
                proposed_changes=["change"],
                risk_level=RiskLevel.R0,
                evidence_refs=[],
            )

    def test_r0_passes_only_with_verified_bound_evidence(self, services) -> None:
        _, _, evidence, gate = services
        mission_id = "mission_evidence_2"
        evidence_ref = add_verified_evidence(evidence, mission_id=mission_id)
        proposal = make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R0,
            evidence_ref=evidence_ref,
        )

        decision = gate.assess(
            proposal,
            EvolutionValidation(verification_passed=True),
        )

        assert decision.allowed is True
        assert decision.verified_evidence_refs == [evidence_ref]

    def test_cross_mission_evidence_is_rejected(self, services) -> None:
        _, _, evidence, gate = services
        evidence_ref = add_verified_evidence(evidence, mission_id="another_mission")
        proposal = make_proposal(
            mission_id="mission_evidence_3",
            risk=RiskLevel.R0,
            evidence_ref=evidence_ref,
        )

        decision = gate.assess(
            proposal,
            EvolutionValidation(verification_passed=True),
        )

        assert decision.allowed is False
        assert any("mission mismatch" in item for item in decision.required_actions)

    def test_corrupt_evidence_is_rejected(self, services) -> None:
        store, _, evidence, gate = services
        mission_id = "mission_evidence_4"
        evidence_ref = add_verified_evidence(evidence, mission_id=mission_id)
        raw = store.get_record(evidence_ref)
        assert raw is not None
        raw["content"] = "tampered"
        store.save_record(evidence_ref, "evidence", raw, raw["created_at"], mission_id)
        proposal = make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R0,
            evidence_ref=evidence_ref,
        )

        decision = gate.assess(
            proposal,
            EvolutionValidation(verification_passed=True),
        )

        assert decision.allowed is False
        assert any("digest verification" in item for item in decision.required_actions)

    def test_r2_requires_evidenced_recovery_path_at_contract_boundary(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionProposal(
                mission_id="mission_evidence_5",
                title="No recovery path",
                observed_problem={},
                proposed_changes=["change"],
                risk_level=RiskLevel.R2,
                evidence_refs=["evidence_placeholder"],
            )

    def test_r2_passes_with_verified_promotion_and_rollback_evidence(self, services) -> None:
        _, _, evidence, gate = services
        mission_id = "mission_evidence_6"
        promotion_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="promotion"
        )
        rollback_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="rollback"
        )
        proposal = make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R2,
            evidence_ref=promotion_ref,
            rollback_evidence_ref=rollback_ref,
        )

        decision = gate.assess(proposal, complete_validation())

        assert decision.allowed is True
        assert set(decision.verified_evidence_refs) == {promotion_ref, rollback_ref}


class TestEvolutionApprovalBindingV2:
    def r3_proposal(self, evidence: EvidenceStore, mission_id: str) -> EvolutionProposal:
        promotion_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="promotion"
        )
        rollback_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="rollback"
        )
        return make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R3,
            evidence_ref=promotion_ref,
            rollback_evidence_ref=rollback_ref,
        )

    def test_bare_approval_status_is_not_a_supported_contract(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionValidation(human_approval_status="approved")

    def test_r3_without_stored_approval_is_blocked(self, services) -> None:
        _, _, evidence, gate = services
        proposal = self.r3_proposal(evidence, "mission_approval_1")

        decision = gate.assess(proposal, complete_validation())

        assert decision.allowed is False
        assert "obtain stored promotion approval" in decision.required_actions

    def test_wrong_proposal_scope_is_blocked(self, services) -> None:
        _, approvals, evidence, gate = services
        proposal = self.r3_proposal(evidence, "mission_approval_2")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action="product_reality.promote:another_proposal",
        )

        decision = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )

        assert decision.allowed is False
        assert any("proposal scope mismatch" in item for item in decision.required_actions)

    def test_valid_r3_approval_is_consumed(self, services) -> None:
        _, approvals, evidence, gate = services
        proposal = self.r3_proposal(evidence, "mission_approval_3")
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

    def test_consumed_approval_cannot_be_reused(self, services) -> None:
        _, approvals, evidence, gate = services
        proposal = self.r3_proposal(evidence, "mission_approval_4")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
        )
        validation = complete_validation(approval_id=approval_id)
        assert gate.assess(proposal, validation).allowed is True

        second = gate.assess(proposal, validation)

        assert second.allowed is False
        assert any("is not approved" in item for item in second.required_actions)

    def test_expired_approval_is_blocked(self, services) -> None:
        store, approvals, evidence, gate = services
        proposal = self.r3_proposal(evidence, "mission_approval_5")
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
        )
        raw = store.get_record(approval_id)
        assert raw is not None
        raw["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        store.save_record(approval_id, "approval", raw, raw["created_at"], proposal.mission_id)

        decision = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )

        assert decision.allowed is False
        assert any("expired" in item for item in decision.required_actions)

    def test_r4_requires_separate_manual_release_approval(self, services) -> None:
        _, approvals, evidence, gate = services
        mission_id = "mission_approval_6"
        promotion_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="promotion"
        )
        rollback_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="rollback"
        )
        proposal = make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R4,
            evidence_ref=promotion_ref,
            rollback_evidence_ref=rollback_ref,
        )
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
        )

        blocked = gate.assess(
            proposal,
            complete_validation(approval_id=approval_id),
        )

        assert blocked.allowed is False
        assert "obtain stored manual release approval" in blocked.required_actions

    def test_r4_passes_with_two_exact_stored_approvals(self, services) -> None:
        _, approvals, evidence, gate = services
        mission_id = "mission_approval_7"
        promotion_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="promotion"
        )
        rollback_ref = add_verified_evidence(
            evidence, mission_id=mission_id, title="rollback"
        )
        proposal = make_proposal(
            mission_id=mission_id,
            risk=RiskLevel.R4,
            evidence_ref=promotion_ref,
            rollback_evidence_ref=rollback_ref,
        )
        approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.promotion_action,
        )
        release_approval_id = create_approved_record(
            approvals,
            proposal=proposal,
            action=proposal.release_action,
        )

        decision = gate.assess(
            proposal,
            complete_validation(
                approval_id=approval_id,
                release_approval_id=release_approval_id,
            ),
        )

        assert decision.allowed is True
        assert set(decision.consumed_approval_ids) == {
            approval_id,
            release_approval_id,
        }
