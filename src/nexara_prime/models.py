from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class RiskLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


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
    # Adaptive Runtime states (forward-compatible extension)
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


class AdaptiveMode(str, Enum):
    S0 = "S0"  # Instant — single-agent, minimal evidence
    S1 = "S1"  # Assisted — single-agent + optional reviewer
    S2 = "S2"  # Managed — multi-agent, full DAG
    S3 = "S3"  # Governed — high-risk, mandatory approval, dual verification


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
    FACT = "fact"
    DECISION = "decision"
    FAILURE = "failure"
    PATCH = "patch"
    USER_FACT = "user_fact"
    PROJECT_FACT = "project_fact"
    PREFERENCE = "preference"
    TEMPORARY_CONTEXT = "temporary_context"
    FAILURE_EXPERIENCE = "failure_experience"
    SYSTEM_RULE = "system_rule"
    SKILL_IMPROVEMENT = "skill_improvement"
    UNVERIFIED_INFERENCE = "unverified_inference"


class CapabilityType(str, Enum):
    SKILL = "skill"
    TOOL = "tool"
    MODEL = "model"
    MEMORY = "memory"
    POLICY = "policy"


class RuntimeRole(str, Enum):
    ORCHESTRATOR = "Orchestrator"
    PLANNER = "Planner"
    ANALYST = "Analyst"
    RESEARCHER = "Researcher"
    EXECUTOR = "Executor"
    REVIEWER = "Reviewer"
    AUDITOR = "Auditor"
    ARCHIVIST = "Archivist"


class Persona(str, Enum):
    HERMES = "Hermes"
    ATLAS = "Atlas"
    NYX = "Nyx"
    ORION = "Orion"
    SOLACE = "Solace"
    VERTEX = "Vertex"
    ECHO = "Echo"
    LUMEN = "Lumen"
    KAIROS = "Kairos"


class NModel(BaseModel):
    # Keep Enum instances in memory; `model_dump(mode="json")` serializes them at persistence boundaries.
    model_config = ConfigDict(extra="forbid")


class MissionSpec(NModel):
    mission_id: str = Field(default_factory=lambda: new_id("mission"))
    title: str
    objective: str
    boundaries: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2
    source_dir: str | None = None
    created_at: str = Field(default_factory=now_iso)


class WorkContract(NModel):
    contract_id: str = Field(default_factory=lambda: new_id("contract"))
    mission_id: str
    version: int = 1
    status: str = "draft"
    objective: str
    boundaries: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2
    change_log: list[str] = Field(default_factory=list)
    approved_at: str | None = None
    created_at: str = Field(default_factory=now_iso)


class PlanStep(NModel):
    step_id: str = Field(default_factory=lambda: new_id("step"))
    title: str
    description: str
    role: RuntimeRole
    persona: Persona
    required_capabilities: list[str] = Field(default_factory=list)
    status: str = "pending"


class MissionPlan(NModel):
    plan_id: str = Field(default_factory=lambda: new_id("plan"))
    mission_id: str
    steps: list[PlanStep] = Field(default_factory=list)
    simulated: bool = False
    created_at: str = Field(default_factory=now_iso)


class AgentAssignment(NModel):
    assignment_id: str = Field(default_factory=lambda: new_id("assignment"))
    mission_id: str
    persona: Persona
    runtime_role: RuntimeRole
    status: str = "active"
    loaded_capabilities: list[str] = Field(default_factory=list)
    current_step_id: str | None = None


class Event(NModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    event_type: str
    aggregate_id: str
    aggregate_type: str
    actor: str
    trace_id: str
    timestamp: str = Field(default_factory=now_iso)
    idempotency_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceArtifact(NModel):
    evidence_id: str = Field(default_factory=lambda: new_id("evidence"))
    mission_id: str
    kind: str
    title: str
    content: str
    sha256: str
    task_id: str | None = None
    tool_invocation_id: str | None = None
    actor: str = "system"
    timestamp: str = Field(default_factory=now_iso)
    mime_type: str = "text/plain"
    source: str = "runtime"
    verification_status: str = "unverified"
    parent_evidence: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None
    source_event_id: str | None = None
    created_at: str = Field(default_factory=now_iso)


class ApprovalRequest(NModel):
    approval_id: str = Field(default_factory=lambda: new_id("approval"))
    mission_id: str
    action: str
    risk_level: RiskLevel
    rationale: str
    impact: list[str] = Field(default_factory=list)
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
    created_at: str = Field(default_factory=now_iso)
    decided_at: str | None = None


class WriterLease(NModel):
    lease_id: str = Field(default_factory=lambda: new_id("lease"))
    resource_id: str
    writer: str
    trace_id: str
    expires_at: str
    active: bool = True


class ToolInvocation(NModel):
    invocation_id: str = Field(default_factory=lambda: new_id("tool"))
    mission_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.R1
    status: str = "completed"
    duration_ms: int = 0
    trace_id: str
    idempotency_key: str | None = None
    receipt_evidence_id: str | None = None
    rollback_point: dict[str, Any] = Field(default_factory=dict)
    compensation: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class MemoryRecord(NModel):
    memory_id: str = Field(default_factory=lambda: new_id("memory"))
    mission_id: str | None = None
    kind: MemoryKind
    key: str
    content: str
    source_evidence_id: str | None = None
    confidence: float = 1.0
    status: str = "committed"
    verified: bool = False
    canonical: bool = False
    conflict_keys: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class EvaluationResult(NModel):
    evaluation_id: str = Field(default_factory=lambda: new_id("eval"))
    mission_id: str
    correctness: float
    reliability: float
    safety: float
    evidence_coverage: float
    token_efficiency: float
    cost_score: float
    recovery_rate: float
    passed: bool
    notes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class Capability(NModel):
    capability_id: str
    name: str
    capability_type: CapabilityType
    description: str
    risk_level: RiskLevel = RiskLevel.R1
    enabled: bool = True
    input_schema: dict[str, Any] = Field(default_factory=dict)


class CompiledPrompt(NModel):
    prompt_id: str = Field(default_factory=lambda: new_id("prompt"))
    mission_id: str
    system: str
    task: str
    skill_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    estimated_tokens: int = 0


class Mission(NModel):
    mission_id: str
    spec: MissionSpec
    state: MissionState = MissionState.INTENT
    contract: WorkContract | None = None
    plan: MissionPlan | None = None
    assignments: list[AgentAssignment] = Field(default_factory=list)
    pending_approval_id: str | None = None
    paused: bool = False
    safe_mode: bool = False
    rollback_point: str | None = None
    trace_id: str
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    # Adaptive Runtime fields
    adaptive_mode: str = AdaptiveMode.S0.value
    triage_result: dict[str, Any] | None = None
    scheduling_plan: dict[str, Any] | None = None
    routing_decisions: list[dict[str, Any]] = Field(default_factory=list)
    resource_budget: dict[str, Any] | None = None
    budget_usage: dict[str, Any] | None = None
    escalation_history: list[dict[str, Any]] = Field(default_factory=list)
    agent_lifecycle: list[dict[str, Any]] = Field(default_factory=list)


# ── Adaptive Runtime Models ──


class MissionTriageResult(NModel):
    triage_id: str = Field(default_factory=lambda: new_id("triage"))
    mission_id: str
    intent: str
    context_summary: str
    requested_outcome: str
    tool_requirements: list[str] = Field(default_factory=list)
    data_sensitivity: str = "low"
    external_side_effects: bool = False
    reversibility: bool = True
    uncertainty: float = 0.0
    expected_duration_ms: int = 0
    expected_token_cost: int = 0
    required_evidence_level: str = "minimal"
    complexity_score: float = 0.0
    risk_score: float = 0.0
    uncertainty_score: float = 0.0
    expected_cost: float = 0.0
    recommended_mode: str = AdaptiveMode.S0.value
    required_roles: list[str] = Field(default_factory=list)
    required_model_tier: str = "flash"
    required_governance_level: str = "standard"
    required_evidence_tier: str = "minimal"
    escalation_conditions: list[str] = Field(default_factory=list)
    decision_reasoning: str = ""
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)


class AdaptiveMissionProfile(NModel):
    profile_id: str = Field(default_factory=lambda: new_id("profile"))
    mission_id: str
    adaptive_mode: str = AdaptiveMode.S0.value
    complexity_score: float = 0.0
    risk_score: float = 0.0
    active_agents: list[str] = Field(default_factory=list)
    selected_provider: str = ""
    selected_model: str = ""
    token_budget: int = 0
    token_used: int = 0
    cost_estimate: float = 0.0
    tool_calls: int = 0
    retries: int = 0
    approval_state: str = "none"
    sandbox_state: str = "active"
    audit_state: str = "intact"
    evidence_count: int = 0
    escalation_count: int = 0
    recovery_count: int = 0
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class SchedulingPlan(NModel):
    plan_id: str = Field(default_factory=lambda: new_id("schedplan"))
    mission_id: str
    adaptive_mode: str = AdaptiveMode.S0.value
    agents: list[dict[str, Any]] = Field(default_factory=list)
    task_dag: dict[str, Any] = Field(default_factory=dict)
    parallelism_degree: int = 1
    estimated_duration_ms: int = 0
    roi_decision: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)


class CapabilityScore(NModel):
    capability_id: str
    name: str
    supported_task_types: list[str] = Field(default_factory=list)
    tool_permissions: list[str] = Field(default_factory=list)
    risk_ceiling: str = RiskLevel.R1.value
    model_requirements: list[str] = Field(default_factory=list)
    historical_success_rate: float = 0.0
    average_latency_ms: float = 0.0
    average_token_cost: float = 0.0
    recent_failure_rate: float = 0.0
    confidence: float = 0.5
    evidence_count: int = 0
    last_updated: str = Field(default_factory=now_iso)
    source_evidence: list[str] = Field(default_factory=list)
    schema_version: int = 2


class ModelRoutingDecision(NModel):
    decision_id: str = Field(default_factory=lambda: new_id("route"))
    mission_id: str
    selected_provider: str
    selected_model: str
    reason: str
    alternatives: list[dict[str, str]] = Field(default_factory=list)
    estimated_tokens: int = 0
    estimated_cost: float = 0.0
    fallback: str = ""
    policy_version: str = "1.0"
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)


class ResourceBudget(NModel):
    budget_id: str = Field(default_factory=lambda: new_id("budget"))
    mission_id: str
    token_budget: int = 100000
    cost_budget: float = 10.0
    wall_time_budget_ms: int = 300000
    tool_call_budget: int = 50
    retry_budget: int = 5
    agent_count_budget: int = 8
    browser_budget: int = 10
    evidence_budget: int = 100
    over_budget_action: str = "warn"
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)


class BudgetUsage(NModel):
    usage_id: str = Field(default_factory=lambda: new_id("usage"))
    mission_id: str
    budget_id: str
    tokens_used: int = 0
    cost_used: float = 0.0
    wall_time_used_ms: int = 0
    tool_calls_used: int = 0
    retries_used: int = 0
    agents_spawned: int = 0
    browser_calls_used: int = 0
    evidence_used: int = 0
    over_budget_triggers: list[str] = Field(default_factory=list)
    degraded: bool = False
    stopped: bool = False
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class EscalationDecision(NModel):
    decision_id: str = Field(default_factory=lambda: new_id("escalate"))
    mission_id: str
    from_mode: str
    to_mode: str
    reason: str
    trigger: str
    approved: bool = False
    actor: str = "system"
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)


class TokenCompilationRecord(NModel):
    record_id: str = Field(default_factory=lambda: new_id("tcompile"))
    mission_id: str
    raw_context_tokens: int = 0
    compiled_context_tokens: int = 0
    token_savings_ratio: float = 0.0
    context_items_removed: int = 0
    context_items_referenced: int = 0
    shared_immutable_context: dict[str, Any] = Field(default_factory=dict)
    role_slices: list[str] = Field(default_factory=list)
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)


class AdaptiveEvaluation(NModel):
    evaluation_id: str = Field(default_factory=lambda: new_id("adapteval"))
    mission_id: str
    adaptive_mode_effective: str
    agents_used: int
    agents_wasted: int
    token_efficiency: float
    latency_vs_baseline: float
    evidence_completeness: float
    approval_correctness: bool
    recovery_correctness: bool
    roi_score: float
    notes: list[str] = Field(default_factory=list)
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)


class SchedulerPolicyVersion(NModel):
    policy_id: str = Field(default_factory=lambda: new_id("policy"))
    version: str = "1.0.0"
    single_agent_preferred: bool = True
    roi_threshold: float = 0.3
    max_agents_default: int = 3
    max_agents_governed: int = 8
    escalation_thresholds: dict[str, float] = Field(default_factory=dict)
    de_escalation_thresholds: dict[str, float] = Field(default_factory=dict)
    schema_version: int = 1
    created_at: str = Field(default_factory=now_iso)
