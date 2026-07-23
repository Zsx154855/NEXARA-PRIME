"""Runtime Truth data models — mirrors NEXARA API contracts authoritatively.

All enum values and field shapes match runtime wire format exactly.
Nullable runtime fields are nullable here. No silent field discard.
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


class RuntimeRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"
    ARCHIVIST = "archivist"


class Persona(str, Enum):
    NEXARA = "Nexara"
    SOLACE = "Solace"
    NYX = "Nyx"
    ORION = "Orion"
    VERTEX = "Vertex"
    LUMEN = "Lumen"
    ATLAS = "Atlas"
    ECHO = "Echo"
    KAIROS = "Kairos"


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
    title: str = ""
    description: str = ""
    role: RuntimeRole = RuntimeRole.EXECUTOR
    persona: Persona = Persona.NEXARA
    required_capabilities: list[str] = Field(default_factory=list)
    status: str = "pending"


class MissionPlan(BaseModel):
    plan_id: str = ""
    mission_id: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    simulated: bool = False
    created_at: str = ""


class WorkContract(BaseModel):
    contract_id: str = ""
    mission_id: str = ""
    version: int = 1
    status: str = "draft"
    objective: str = ""
    boundaries: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2
    change_log: list[str] = Field(default_factory=list)
    approved_at: str | None = None
    created_at: str = ""
    schema_version: int = 1
    mission_run_id: str | None = None
    correlation_id: str | None = None
    provenance: str | None = None


class Mission(BaseModel):
    mission_id: str
    spec: MissionSpec | None = None
    state: MissionState = MissionState.CREATED
    contract: WorkContract | None = None
    plan: MissionPlan | None = None
    paused: bool = False
    safe_mode: bool = False
    pending_approval_id: str | None = None
    rollback_point: str | None = None
    trace_id: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    adaptive_mode: str = "S0"
    triage_result: dict[str, Any] | None = None


# ── Approval ──


class ApprovalRequest(BaseModel):
    approval_id: str = ""
    mission_id: str = ""
    action: str = ""
    risk_level: RiskLevel = RiskLevel.R2
    rationale: str = ""
    reason: str | None = None
    affected_resources: list[str] = Field(default_factory=list)
    external_effect: bool = False
    reversible: bool = True
    rollback_plan: dict[str, Any] = Field(default_factory=dict)
    estimated_cost: float = 0.0
    approval_scope: str = "single_action"
    executor_id: str | None = None
    proposal_sha256: str | None = None
    expires_at: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: str | None = None
    decision_note: str | None = None
    decision_action: str | None = None
    created_at: str = ""
    decided_at: str | None = None
    schema_version: int = 1


# ── Evidence ──


class EvidenceArtifact(BaseModel):
    evidence_id: str = ""
    mission_id: str = ""
    kind: str = ""
    title: str = ""
    content: str = ""
    sha256: str = ""
    task_id: str | None = None
    tool_invocation_id: str | None = None
    actor: str = "system"
    timestamp: str = ""
    mime_type: str = "text/plain"
    source: str = "runtime"
    verification_status: str = "unverified"
    parent_evidence: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None
    source_event_id: str | None = None
    created_at: str = ""


# ── Memory ──


class MemoryRecord(BaseModel):
    memory_id: str = ""
    mission_id: str | None = None
    kind: MemoryKind = MemoryKind.FACT
    key: str = ""
    content: str = ""
    source_evidence_id: str | None = None
    confidence: float = 1.0
    status: str = "committed"
    verified: bool = False
    canonical: bool = False
    conflict_keys: list[str] = Field(default_factory=list)
    created_at: str = ""
    schema_version: int = 1


# ── Plugin ──


class PluginManifest(BaseModel):
    """Plugin manifest schema — capability declaration != authorization."""
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


# ── Evolution ──


class ImprovementProposal(BaseModel):
    proposal_id: str = ""
    target: str = ""
    evidence: list[str] = Field(default_factory=list)
    hypothesis: str = ""
    expected_gain: float = 0.0
    risk: RiskLevel = RiskLevel.R2
    experiment_plan: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] = Field(default_factory=dict)
