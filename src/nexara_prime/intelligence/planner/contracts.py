"""V1.2 Intelligence Layer — Planner Object Contracts.

Goal / Plan / TaskGraph first-class planning objects. Independent L2 overlay;
read-only over V1.1 (does not import/modify V1.1 Runtime Core or SQLite).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from nexara_prime.models import new_id, now_iso

__all__ = ["Goal", "GoalStatus", "Plan", "PlanStep", "TaskGraph", "TaskNode"]


class GoalStatus(str, Enum):
    CREATED = "CREATED"
    ANALYZED = "ANALYZED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class Goal:
    """A user goal distilled from a request. Planning input."""

    id: str = field(default_factory=lambda: new_id("goal"))
    user_intent: str = ""
    objective: str = ""
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    priority: int = 3  # 1 (low) .. 5 (critical)
    deadline: str = ""
    status: GoalStatus = GoalStatus.CREATED
    created_at: str = field(default_factory=now_iso)


@dataclass
class PlanStep:
    """One decomposable step with dependencies and kind."""

    id: str = field(default_factory=lambda: new_id("step"))
    description: str = ""
    kind: str = "tool"  # tool | agent | verification
    dependencies: list[str] = field(default_factory=list)
    estimated_cost: float = 0.0


@dataclass
class Plan:
    """A decomposition of a goal into ordered, dependency-aware steps."""

    id: str = field(default_factory=lambda: new_id("plan"))
    goal_id: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    risk: str = "low"  # low | medium | high
    estimated_cost: float = 0.0
    estimated_time: str = ""
    created_at: str = field(default_factory=now_iso)


@dataclass
class TaskNode:
    """A node in the task graph (Goal → Task → Tool/Agent/Verification)."""

    id: str = field(default_factory=lambda: new_id("task"))
    name: str = ""
    kind: str = "tool"  # tool | agent | verification
    dependencies: list[str] = field(default_factory=list)


@dataclass
class TaskGraph:
    """Dependency graph of tasks derived from a plan."""

    goal_id: str = ""
    nodes: list[TaskNode] = field(default_factory=list)

    def as_adjacency(self) -> dict[str, list[str]]:
        return {n.id: list(n.dependencies) for n in self.nodes}
