"""Portfolio data models — ProgramRecords, budgets, decisions, directives, review budgets."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexara_prime.models import new_id, now_iso


class ProgramStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    WAIT_EXTERNAL = "wait_external"
    WAIT_APPROVAL = "wait_approval"
    WAIT_RESOURCE = "wait_resource"
    PAUSED = "paused"
    RECOVERING = "recovering"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass
class ProgramDependency:
    depends_on: str = ""  # program_id
    dependency_type: str = "hard"  # hard | soft | milestone


@dataclass
class ProgramMilestone:
    milestone_id: str = field(default_factory=lambda: new_id("ms"))
    name: str = ""
    description: str = ""
    reached: bool = False
    reached_at: str = ""
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class ProgramBudget:
    token_budget: int = 0
    cost_budget: float = 0.0
    time_budget_hours: float = 0.0
    retry_budget: int = 3
    tokens_used: int = 0
    cost_used: float = 0.0
    time_used_hours: float = 0.0
    retries_used: int = 0

    @property
    def token_exceeded(self) -> bool:
        return self.token_budget > 0 and self.tokens_used >= self.token_budget

    @property
    def cost_exceeded(self) -> bool:
        return self.cost_budget > 0 and self.cost_used >= self.cost_budget

    @property
    def time_exceeded(self) -> bool:
        return self.time_budget_hours > 0 and self.time_used_hours >= self.time_budget_hours

    @property
    def retries_exhausted(self) -> bool:
        return self.retries_used >= self.retry_budget


@dataclass
class ProgramRisk:
    risk_id: str = field(default_factory=lambda: new_id("risk"))
    category: str = ""  # security | quality | schedule | resource | dependency
    description: str = ""
    severity: str = "medium"  # low | medium | high | critical
    mitigation: str = ""
    is_active: bool = True


@dataclass
class ProgramCheckpoint:
    checkpoint_id: str = field(default_factory=lambda: new_id("cp"))
    program_id: str = ""
    mission_id: str = ""
    phase: str = ""
    snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)


@dataclass
class ProgramDecision:
    decision_id: str = field(default_factory=lambda: new_id("dec"))
    program_id: str = ""
    reason: str = ""
    priority_score: float = 0.0
    selected_for_execution: bool = False
    alternatives_considered: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)


@dataclass
class ProgramWaitCondition:
    condition_id: str = field(default_factory=lambda: new_id("wait"))
    condition_type: str = ""  # codex_review | ci_status | approval | worker | timer | filesystem | user_directive
    description: str = ""
    external_ref: str = ""  # PR number, job ID, approval ID, etc.
    check_interval_seconds: float = 60.0
    last_checked_at: str = ""
    satisfied: bool = False
    timeout_seconds: float = 0.0  # 0 = no timeout
    created_at: str = field(default_factory=now_iso)


@dataclass
class ProgramDeliveryState:
    program_id: str = ""
    status: ProgramStatus = ProgramStatus.PLANNED
    progress_pct: float = 0.0
    current_milestone: str = ""
    active_missions: list[str] = field(default_factory=list)
    completed_missions: list[str] = field(default_factory=list)
    failed_missions: list[str] = field(default_factory=list)
    last_evidence_at: str = ""
    last_decision_at: str = ""


@dataclass
class ReviewBudget:
    """Per-program review budget — prevents infinite review cycles."""
    program_id: str = ""
    max_cycles: int = 10
    max_elapsed_time_hours: float = 48.0
    blocking_priorities: list[str] = field(default_factory=lambda: ["P0", "P1"])
    repeated_root_cause_limit: int = 2
    p2_policy: str = "issue"  # issue | accept_risk | defer
    p3_policy: str = "non_blocking"
    cycles_used: int = 0
    started_at: str = ""
    last_review_at: str = ""
    root_cause_counts: dict[str, int] = field(default_factory=dict)

    @property
    def budget_exhausted(self) -> bool:
        return self.cycles_used >= self.max_cycles

    @property
    def repeated_root_cause_detected(self) -> bool:
        return any(count >= self.repeated_root_cause_limit for count in self.root_cause_counts.values())


@dataclass
class OwnerDirective:
    """A directive from the Owner — never treated as a raw shell command."""
    directive_id: str = field(default_factory=lambda: new_id("od"))
    owner_id: str = "local-owner"
    text: str = ""
    intent: str = ""  # continue | review | pause | stop | investigate | prioritize
    scope: str = "*"  # program_id or "*" for portfolio-wide
    priority: str = "normal"  # urgent | high | normal | low
    constraints: list[str] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    expires_at: str = ""
    supersedes: str = ""
    status: str = "active"  # active | processed | expired | superseded


@dataclass
class ProgramRecord:
    """A single program in the portfolio."""
    program_id: str = field(default_factory=lambda: new_id("prog"))
    name: str = ""
    purpose: str = ""
    owner_goal_id: str = ""
    status: ProgramStatus = ProgramStatus.PLANNED
    priority: int = 5  # 1-10, higher = more important
    value_score: float = 5.0
    urgency_score: float = 5.0
    risk_score: float = 3.0
    effort_score: float = 3.0
    confidence: float = 0.7
    dependencies: list[ProgramDependency] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    wait_conditions: list[ProgramWaitCondition] = field(default_factory=list)
    active_missions: list[str] = field(default_factory=list)
    completed_missions: list[str] = field(default_factory=list)
    milestones: list[ProgramMilestone] = field(default_factory=list)
    worker_requirements: list[str] = field(default_factory=list)
    budget: ProgramBudget = field(default_factory=ProgramBudget)
    review_budget: ReviewBudget = field(default_factory=ReviewBudget)
    checkpoint_ref: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    started_at: str = ""
    completed_at: str = ""
    next_action: str = ""
    next_review_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Portfolio:
    """The complete portfolio of programs."""
    portfolio_id: str = "nexara_prime_portfolio_v1"
    programs: dict[str, ProgramRecord] = field(default_factory=dict)
    active_program_id: str = ""
    owner_goals: dict[str, str] = field(default_factory=dict)  # goal_id → description
    directives: list[OwnerDirective] = field(default_factory=list)
    last_snapshot_at: str = ""
    version: int = 1


@dataclass
class PortfolioSnapshot:
    """Immutable snapshot of portfolio state at a point in time."""
    snapshot_id: str = field(default_factory=lambda: new_id("snap"))
    portfolio_id: str = ""
    program_states: dict[str, ProgramStatus] = field(default_factory=dict)
    active_program_id: str = ""
    decision_trace: list[ProgramDecision] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    version: int = 1
