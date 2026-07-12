from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from nexara_prime.models import NModel, RiskLevel, new_id, now_iso


class ProductSurface(str, Enum):
    MACOS = "macOS"
    IPADOS = "iPadOS"
    IOS = "iOS"
    WEB = "web"
    VISIONOS = "visionOS"
    FIGMA = "figma"
    CANVA = "canva"


class DriftType(str, Enum):
    DESIGN_DRIFT = "design_drift"
    CODE_DRIFT = "code_drift"
    RUNTIME_DRIFT = "runtime_drift"
    EVIDENCE_GAP = "evidence_gap"
    POLICY_VIOLATION = "policy_violation"
    ACCESSIBILITY_REGRESSION = "accessibility_regression"
    METRIC_REGRESSION = "metric_regression"


class ValuePresence(str, Enum):
    MISSING = "missing"
    PRESENT = "present"


class DriftValue(NModel):
    """A drift operand that preserves absent-vs-present-null semantics."""

    presence: ValuePresence
    value: Any = None

    @classmethod
    def missing(cls) -> "DriftValue":
        return cls(presence=ValuePresence.MISSING)

    @classmethod
    def present(cls, value: Any) -> "DriftValue":
        return cls(presence=ValuePresence.PRESENT, value=value)


class ExperienceGene(NModel):
    gene_id: str = Field(default_factory=lambda: new_id("gene"))
    name: str
    purpose: str
    activates_when: dict[str, Any] = Field(default_factory=dict)
    must_show: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    prohibited: list[str] = Field(default_factory=list)
    platform_expression: dict[str, str] = Field(default_factory=dict)
    verification_rules: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    created_at: str = Field(default_factory=now_iso)


class TwinSnapshot(NModel):
    snapshot_id: str = Field(default_factory=lambda: new_id("snapshot"))
    mission_id: str
    kind: str
    state: dict[str, Any]
    state_sha256: str
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class DriftFinding(NModel):
    drift_id: str = Field(default_factory=lambda: new_id("drift"))
    mission_id: str
    drift_type: DriftType
    path: str
    expected: DriftValue
    observed: DriftValue
    severity: RiskLevel = RiskLevel.R1
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class ProductTwinCheckpoint(NModel):
    checkpoint_id: str = Field(default_factory=lambda: new_id("twin"))
    mission_id: str
    expected: TwinSnapshot
    observed: TwinSnapshot
    drift_findings: list[DriftFinding] = Field(default_factory=list)
    reversible: bool = True
    rollback_ref: str | None = None
    created_at: str = Field(default_factory=now_iso)


class EvolutionValidation(NModel):
    simulation_passed: bool = False
    verification_passed: bool = False
    accessibility_passed: bool = False
    governance_passed: bool = False
    approval_id: str | None = None
    release_approval_id: str | None = None
    actor_id: str | None = None


class EvolutionProposal(NModel):
    proposal_id: str = Field(default_factory=lambda: new_id("evolution"))
    mission_id: str
    title: str
    observed_problem: dict[str, Any]
    proposed_changes: list[str] = Field(min_length=1)
    expected_impact: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.R2
    evidence_refs: list[str] = Field(min_length=1)
    rollback_plan: list[str] = Field(default_factory=list)
    rollback_checkpoint_id: str | None = None
    rollback_evidence_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)

    @property
    def promotion_action(self) -> str:
        return f"product_reality.promote:{self.proposal_id}"

    @property
    def release_action(self) -> str:
        return f"product_reality.release:{self.proposal_id}"

    @model_validator(mode="after")
    def require_recovery_path_for_managed_risk(self) -> "EvolutionProposal":
        if self.risk_level in (RiskLevel.R2, RiskLevel.R3, RiskLevel.R4):
            missing: list[str] = []
            if not self.rollback_plan:
                missing.append("rollback_plan")
            if not self.rollback_checkpoint_id:
                missing.append("rollback_checkpoint_id")
            if not self.rollback_evidence_refs:
                missing.append("rollback_evidence_refs")
            if missing:
                raise ValueError(
                    "R2-R4 evolution proposals require an evidenced recovery path: "
                    + ", ".join(missing)
                )
        return self


class PromotionDecision(NModel):
    proposal_id: str
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    verified_evidence_refs: list[str] = Field(default_factory=list)
    consumed_approval_ids: list[str] = Field(default_factory=list)
    assessed_at: str = Field(default_factory=now_iso)
