"""Planning Engine — converts MissionContract into executable plan.

Phase 4A: Takes compiled MissionContract from MissionIntelligenceEngine,
produces Plan with ordered task sequence, resource estimation, and
Gateway routing integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from nexara_prime.brain.mission_types import MissionContract, TaskNode, DecompositionResult
from nexara_prime.models import now_iso, new_id

if TYPE_CHECKING:
    from nexara_prime.brain.memory_controller import MemoryController


@dataclass(frozen=True)
class PlanTask:
    """A single executable task in a plan."""
    task_id: str
    description: str
    action: str  # read|write|test|deploy|review|analyze
    estimated_tokens: int = 0
    depends_on: list[str] = field(default_factory=list)
    assigned_adapter: str = "claude"


@dataclass(frozen=True)
class Plan:
    """Executable plan derived from a MissionContract."""
    plan_id: str
    mission_id: str
    objective: str
    tasks: list[PlanTask]
    total_estimated_tokens: int = 0
    adapter: str = "claude"
    risk_level: str = "R2"
    created_at: str = field(default_factory=now_iso)


class PlanningEngine:
    """Converts MissionContract → executable Plan.

    Reads MemoryController for historical planning patterns.
    Integrates with Gateway routing by suggesting adapter assignments.
    Deterministic — no model calls, no network, no side effects.
    """

    def __init__(self, memory_controller: MemoryController | None = None) -> None:
        self._mc = memory_controller

    def plan(self, contract: MissionContract, decomposition: DecompositionResult | None = None) -> Plan:
        """Create an executable plan from a mission contract.

        Args:
            contract: The compiled MissionContract.
            decomposition: Optional pre-computed decomposition.

        Returns:
            Plan with ordered tasks, token estimates, and adapter assignments.
        """
        plan_id = new_id("plan")
        tasks: list[PlanTask] = []

        if decomposition and decomposition.tasks:
            for tn in decomposition.tasks:
                action = self._infer_action(tn.description, contract.risk_level)
                tasks.append(PlanTask(
                    task_id=tn.task_id,
                    description=tn.description,
                    action=action,
                    estimated_tokens=self._estimate_tokens(tn.description, action),
                    depends_on=list(tn.dependencies),
                    assigned_adapter=self._assign_adapter(action, contract.risk_level),
                ))
        else:
            # Fallback: generate tasks from contract
            order = 0
            for criterion in contract.success_criteria:
                order += 1
                desc = criterion.replace("Complete: ", "")
                action = self._infer_action(desc, contract.risk_level)
                tasks.append(PlanTask(
                    task_id=f"t{order}",
                    description=desc,
                    action=action,
                    estimated_tokens=self._estimate_tokens(desc, action),
                    depends_on=[f"t{order-1}"] if order > 1 else [],
                    assigned_adapter=self._assign_adapter(action, contract.risk_level),
                ))

        total_tokens = sum(t.estimated_tokens for t in tasks)
        adapter = self._primary_adapter(contract.required_capabilities)

        return Plan(
            plan_id=plan_id,
            mission_id=contract.mission_id,
            objective=contract.objective,
            tasks=tasks,
            total_estimated_tokens=total_tokens,
            adapter=adapter,
            risk_level=contract.risk_level,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _infer_action(description: str, risk_level: str) -> str:
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ("write", "create", "implement", "build", "code", "generate", "apply")):
            return "write"
        if any(kw in desc_lower for kw in ("test", "verify", "validate", "check")):
            return "test"
        if any(kw in desc_lower for kw in ("deploy", "publish", "release", "ship")):
            return "deploy" if risk_level in ("R0", "R1", "R2") else "review"
        if any(kw in desc_lower for kw in ("review", "audit", "inspect", "scan", "analyze", "diagnose")):
            return "review"
        if any(kw in desc_lower for kw in ("research", "gather", "study", "define")):
            return "analyze"
        return "read"

    @staticmethod
    def _estimate_tokens(description: str, action: str) -> int:
        base = len(description.split()) * 500
        action_multiplier = {"write": 3, "test": 2, "deploy": 4, "review": 1, "analyze": 1, "read": 1}
        return base * action_multiplier.get(action, 1)

    @staticmethod
    def _assign_adapter(action: str, risk_level: str) -> str:
        if action == "deploy" or risk_level in ("R3", "R4"):
            return "claude"  # high-risk → Claude for architecture oversight
        if action == "review":
            return "codex"  # review tasks → Codex
        if action in ("analyze", "research"):
            return "hermes"  # research → Hermes
        return "claude"

    @staticmethod
    def _primary_adapter(capabilities: list[str]) -> str:
        if "deployment" in capabilities:
            return "claude"
        if "architecture" in capabilities:
            return "claude"
        if "review" in capabilities or "inspection" in capabilities:
            return "codex"
        return "claude"

    def health(self) -> dict[str, Any]:
        return {
            "engine": "planning_engine",
            "status": "ready",
            "memory_available": self._mc is not None,
        }
