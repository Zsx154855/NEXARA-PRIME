"""Runtime Truth data models — mirrors NEXARA API contracts.

All enum values match the runtime's wire format exactly:
- MissionState: PascalCase ("Intent", "Completed", "Running", ...)
- ApprovalStatus: lowercase ("pending", "approved", ...)
- MemoryKind: snake_case ("short_term", "fact", ...)
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MissionState(str, Enum):
    INTENT = "Intent"
    CONTEXT = "Context"
    CONTRACT = "Contract"
    PLAN = "Plan"
    SIMULATION = "Simulation"
    APPROVAL = "Approval"
    EXECUTION = "Execution"
    VERIFICATION = "Verification"
    EVIDENCE = "Evidence"
    MEMORY_PATCH = "MemoryPatch"
    EVALUATION = "Evaluation"
    COMPLETED = "Completed"
    BLOCKED = "Blocked"
    FAILED = "Failed"
    ROLLED_BACK = "RolledBack"
    CREATED = "Created"
    TRIAGED = "Triaged"
    CONTRACTED = "Contracted"
    PLANNED = "Planned"
    SCHEDULED = "Scheduled"
    AWAITING_APPROVAL = "AwaitingApproval"
    RUNNING = "Running"
    VERIFYING = "Verifying"
    DEGRADED = "Degraded"
    PAUSED = "Paused"
    CANCELLED = "Cancelled"
    ROLLING_BACK = "RollingBack"


class RiskLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    PAUSED = "paused"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class MemoryKind(str, Enum):
    SHORT_TERM = "short_term"
    TEMPORARY_CONTEXT = "temporary_context"
    FACT = "fact"
    DECISION = "decision"
    FAILURE = "failure"
    FAILURE_EXPERIENCE = "failure_experience"
    PATCH = "patch"
    SKILL_IMPROVEMENT = "skill_improvement"
    SYSTEM_RULE = "system_rule"
    USER_FACT = "user_fact"
    PROJECT_FACT = "project_fact"
    PREFERENCE = "preference"
    UNVERIFIED_INFERENCE = "unverified_inference"


# ── Core Models ──


class RuntimeOverview(BaseModel):
    system: dict[str, Any] = Field(default_factory=dict)
    missions: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    capabilities: list[dict[str, Any]] = Field(default_factory=list)


class MissionSpec(BaseModel):
    mission_id: str
    title: str = ""
    objective: str = ""
    boundaries: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2


class PlanStep(BaseModel):
    step_id: str = ""
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    assigned_role: str = ""
    estimated_tokens: int = 0
    estimated_duration_ms: int = 0


class MissionPlan(BaseModel):
    plan_id: str = ""
    mission_id: str = ""
    steps: list[PlanStep] = Field(default_factory=list)


class WorkContract(BaseModel):
    contract_id: str = ""
    mission_id: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    allowed_side_effects: list[str] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    rollback_plan: dict[str, Any] | None = None


class Mission(BaseModel):
    mission_id: str
    spec: MissionSpec | None = None
    state: MissionState = MissionState.CREATED
    plan: MissionPlan | None = None
    contract: WorkContract | None = None
    created_at: str = ""
    updated_at: str = ""
    is_paused: bool = False
    is_safe_mode: bool = False


# ── Approval ──


class ApprovalRequest(BaseModel):
    approval_id: str = ""
    mission_id: str = ""
    action: str = ""
    resource: str = ""
    risk_level: RiskLevel = RiskLevel.R2
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str = ""
    affected_resources: list[str] = Field(default_factory=list)
    external_effect: bool = False
    reversible: bool = True
    requested_at: str = ""
    expires_at: str = ""
    decided_at: str = ""


# ── Evidence ──


class EvidenceArtifact(BaseModel):
    evidence_id: str = ""
    mission_id: str = ""
    title: str = ""
    kind: str = ""
    sha256: str = ""
    source: str = ""
    verification_status: str = ""
    confidence: float = 1.0
    content_preview: str = ""
    created_at: str = ""


# ── Memory ──


class MemoryRecord(BaseModel):
    memory_id: str = ""
    kind: MemoryKind = MemoryKind.FACT
    content: str = ""
    source_evidence_id: str = ""
    confidence: float = 1.0
    status: str = "committed"
    created_at: str = ""


# ── Plugin ──


class PluginManifest(BaseModel):
    """Plugin manifest schema — capability declaration != authorization.

    Declaring a capability does NOT authorize execution.
    Policy must grant permission separately.
    """
    plugin_id: str
    name: str
    version: str
    description: str = ""
    entry_point: str = ""
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    network_scope: list[str] = Field(default_factory=list)
    secret_scope: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2
    signature_required: bool = True
    isolation: str = "process"
    dependencies: list[str] = Field(default_factory=list)
    health_check: str = ""


# ── Improvement Proposal (Evolution) ──


class ImprovementProposal(BaseModel):
    proposal_id: str = ""
    target: str = ""
    evidence: list[str] = Field(default_factory=list)
    hypothesis: str = ""
    expected_gain: float = 0.0
    risk: RiskLevel = RiskLevel.R2
    experiment_plan: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] = Field(default_factory=dict)
