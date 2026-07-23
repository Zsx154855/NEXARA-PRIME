"""Runtime Truth data models — mirrors NEXARA API contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MissionState(str, Enum):
    DRAFT = "DRAFT"
    CONTEXT_READY = "CONTEXT_READY"
    CONTRACTED = "CONTRACTED"
    PLANNED = "PLANNED"
    SIMULATED = "SIMULATED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class RiskLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


class MemoryKind(str, Enum):
    SHORT_TERM = "SHORT_TERM"
    TEMPORARY_CONTEXT = "TEMPORARY_CONTEXT"
    FACT = "FACT"
    DECISION = "DECISION"
    FAILURE = "FAILURE"
    FAILURE_EXPERIENCE = "FAILURE_EXPERIENCE"
    PATCH = "PATCH"
    SKILL_IMPROVEMENT = "SKILL_IMPROVEMENT"
    SYSTEM_RULE = "SYSTEM_RULE"
    USER_FACT = "USER_FACT"
    PROJECT_FACT = "PROJECT_FACT"
    PREFERENCE = "PREFERENCE"
    UNVERIFIED_INFERENCE = "UNVERIFIED_INFERENCE"


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


class Mission(BaseModel):
    mission_id: str
    spec: MissionSpec | None = None
    state: MissionState = MissionState.DRAFT
    plan: MissionPlan | None = None
    contract: WorkContract | None = None
    created_at: str = ""
    updated_at: str = ""


# ── Approval ──


class ApprovalRequest(BaseModel):
    approval_id: str = ""
    mission_id: str = ""
    action: str = ""
    resource: str = ""
    risk_level: RiskLevel = RiskLevel.R2
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = ""
    expires_at: str = ""
    decided_at: str = ""


# ── Evidence ──


class EvidenceArtifact(BaseModel):
    evidence_id: str = ""
    mission_id: str = ""
    kind: str = ""
    sha256: str = ""
    source: str = ""
    verification_status: str = ""
    created_at: str = ""


# ── Memory ──


class MemoryRecord(BaseModel):
    memory_id: str = ""
    kind: MemoryKind = MemoryKind.FACT
    content: str = ""
    source_evidence_id: str = ""
    confidence: float = 1.0
    created_at: str = ""


# ── Plugin ──


class PluginManifest(BaseModel):
    """Plugin manifest schema — capability declaration != authorization."""
    plugin_id: str
    name: str
    version: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    network_scope: list[str] = Field(default_factory=list)
    secret_scope: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2
    signature_required: bool = True
    isolation: str = "process"  # process | sandbox | none
