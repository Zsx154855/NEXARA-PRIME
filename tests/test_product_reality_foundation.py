from __future__ import annotations

import pytest

from nexara_prime.models import RiskLevel
from nexara_prime.product_reality import (
    DriftType,
    EvolutionPromotionGate,
    EvolutionProposal,
    EvolutionValidation,
    ExperienceGene,
    ExperienceGenomeRegistry,
    ProductSurface,
    ProductTwinEngine,
)


def approval_gene() -> ExperienceGene:
    return ExperienceGene(
        gene_id="gene_human_approval_gate",
        name="Human Approval Gate",
        purpose="Keep consequential external actions under explicit human authority.",
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
        verification_rules=["control_is_visible", "environment_is_labelled"],
    )


class TestExperienceGenome:
    def test_resolves_matching_gene(self) -> None:
        registry = ExperienceGenomeRegistry()
        gene = approval_gene()
        registry.register(gene)

        resolved = registry.resolve(
            {"risk_tier": "R3", "execution_environment": "live_external"}
        )

        assert [item.gene_id for item in resolved] == [gene.gene_id]

    def test_does_not_resolve_nonmatching_gene(self) -> None:
        registry = ExperienceGenomeRegistry()
        registry.register(approval_gene())

        assert registry.resolve(
            {"risk_tier": "R1", "execution_environment": "local_runtime"}
        ) == []

    def test_requires_monotonic_version(self) -> None:
        registry = ExperienceGenomeRegistry()
        registry.register(approval_gene())

        with pytest.raises(ValueError):
            registry.register(approval_gene())

    def test_projection_validation_detects_missing_contract(self) -> None:
        registry = ExperienceGenomeRegistry()
        gene = approval_gene()

        errors = registry.validate_projection(
            gene,
            surface=ProductSurface.IOS,
            visible_objects={"action_summary", "implicit_approval"},
            available_controls={"approve"},
        )

        assert any("missing required objects" in item for item in errors)
        assert any("missing required controls" in item for item in errors)
        assert any("prohibited objects present" in item for item in errors)


class TestProductTwin:
    def test_identical_states_have_no_drift(self) -> None:
        engine = ProductTwinEngine()
        checkpoint = engine.capture(
            mission_id="mission_1",
            expected_state={"runtime": {"status": "running"}},
            observed_state={"runtime": {"status": "running"}},
        )

        assert checkpoint.drift_findings == []
        assert checkpoint.expected.state_sha256 == checkpoint.observed.state_sha256

    def test_runtime_state_drift_is_r2(self) -> None:
        engine = ProductTwinEngine()
        checkpoint = engine.capture(
            mission_id="mission_2",
            expected_state={"runtime": {"status": "completed"}},
            observed_state={"runtime": {"status": "running"}},
        )

        assert len(checkpoint.drift_findings) == 1
        finding = checkpoint.drift_findings[0]
        assert finding.drift_type == DriftType.RUNTIME_DRIFT
        assert finding.severity == RiskLevel.R2

    def test_policy_drift_is_r3(self) -> None:
        engine = ProductTwinEngine()
        findings = engine.detect_drift(
            mission_id="mission_3",
            expected={"approval": {"required": True}},
            observed={"approval": {"required": False}},
        )

        assert findings[0].drift_type == DriftType.POLICY_VIOLATION
        assert findings[0].severity == RiskLevel.R3

    def test_evidence_gap_classification(self) -> None:
        engine = ProductTwinEngine()
        findings = engine.detect_drift(
            mission_id="mission_4",
            expected={"evidence": {"verified": 3}},
            observed={"evidence": {"verified": 1}},
            evidence_refs=["evidence_1"],
        )

        assert findings[0].drift_type == DriftType.EVIDENCE_GAP
        assert findings[0].evidence_refs == ["evidence_1"]

    def test_diff_order_is_deterministic(self) -> None:
        engine = ProductTwinEngine()
        findings = engine.detect_drift(
            mission_id="mission_5",
            expected={"z": 1, "a": 1},
            observed={"z": 2, "a": 2},
        )

        assert [finding.path for finding in findings] == ["$.a", "$.z"]


class TestEvolutionPromotionGate:
    def proposal(
        self,
        risk: RiskLevel,
        evidence_refs: list[str] | None = None,
    ) -> EvolutionProposal:
        return EvolutionProposal(
            title="Improve approval comprehension",
            observed_problem={"metric": "approval_review_time", "change_pct": 18},
            proposed_changes=["surface execution environment"],
            risk_level=risk,
            evidence_refs=evidence_refs or [],
            rollback_plan=["restore prior projection"],
        )

    def test_r0_requires_verification_only(self) -> None:
        decision = EvolutionPromotionGate().assess(
            self.proposal(RiskLevel.R0),
            EvolutionValidation(verification_passed=True),
        )

        assert decision.allowed is True

    def test_r1_requires_simulation(self) -> None:
        decision = EvolutionPromotionGate().assess(
            self.proposal(RiskLevel.R1),
            EvolutionValidation(verification_passed=True),
        )

        assert decision.allowed is False
        assert "complete simulation" in decision.required_actions

    def test_r2_requires_accessibility_and_governance(self) -> None:
        decision = EvolutionPromotionGate().assess(
            self.proposal(RiskLevel.R2),
            EvolutionValidation(
                simulation_passed=True,
                verification_passed=True,
            ),
        )

        assert decision.allowed is False
        assert "complete accessibility validation" in decision.required_actions
        assert "complete governance validation" in decision.required_actions

    def test_r3_requires_human_approval(self) -> None:
        proposal = self.proposal(RiskLevel.R3, evidence_refs=["evidence_1"])
        decision = EvolutionPromotionGate().assess(
            proposal,
            EvolutionValidation(
                simulation_passed=True,
                verification_passed=True,
                accessibility_passed=True,
                governance_passed=True,
            ),
        )

        assert decision.allowed is False
        assert "obtain explicit human approval" in decision.required_actions

    def test_r3_can_pass_after_approval(self) -> None:
        proposal = self.proposal(RiskLevel.R3, evidence_refs=["evidence_1"])
        decision = EvolutionPromotionGate().assess(
            proposal,
            EvolutionValidation(
                simulation_passed=True,
                verification_passed=True,
                accessibility_passed=True,
                governance_passed=True,
                human_approval_status="approved",
            ),
        )

        assert decision.allowed is True

    def test_r4_requires_manual_release_authorization(self) -> None:
        proposal = self.proposal(RiskLevel.R4, evidence_refs=["evidence_1"])
        decision = EvolutionPromotionGate().assess(
            proposal,
            EvolutionValidation(
                simulation_passed=True,
                verification_passed=True,
                accessibility_passed=True,
                governance_passed=True,
                human_approval_status="approved",
            ),
        )

        assert decision.allowed is False
        assert "obtain manual release authorization" in decision.required_actions

    def test_r3_r4_require_evidence(self) -> None:
        with pytest.raises(ValueError):
            self.proposal(RiskLevel.R3)
