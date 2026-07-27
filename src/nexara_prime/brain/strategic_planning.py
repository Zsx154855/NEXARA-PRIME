"""StrategicPlanningEngine — goal decomposition, dependency graph, drift detection."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ..models import now_iso
from .cognitive_models import StrategicPlan

if TYPE_CHECKING:
    from .memory_controller import MemoryController


class StrategicPlanningEngine:
    """Goal→Strategy→Program→Mission→Action planning with dependency tracking."""

    def __init__(self, memory_controller: MemoryController) -> None:
        self._mc = memory_controller

    def create_plan(self, goal: str, success_criteria: list[str] | None = None,
                    horizon: str = "medium") -> StrategicPlan:
        plan = StrategicPlan(
            plan_id=f"plan_{now_iso()}",
            owner_goal=goal,
            success_criteria=success_criteria or [goal],
            planning_horizon=horizon,
        )
        return plan

    def generate_strategy_options(self, plan: StrategicPlan) -> list[dict[str, Any]]:
        return [
            {"name": "direct", "risk": 0.3, "description": f"Direct execution of {plan.owner_goal}"},
            {"name": "phased", "risk": 0.15, "description": f"Incremental approach to {plan.owner_goal}"},
        ]

    def decompose_strategy(self, plan: StrategicPlan, strategy: dict) -> list[dict[str, Any]]:
        return [
            {"id": "m1", "title": f"Phase 1: {strategy.get('name', 'init')}", "dependencies": []},
            {"id": "m2", "title": f"Phase 2: complete {strategy.get('name', 'init')}", "dependencies": ["m1"]},
        ]

    def build_dependency_graph(self, missions: list[dict]) -> list[dict[str, str]]:
        deps = []
        for m in missions:
            for dep in m.get("dependencies", []):
                deps.append({"from": dep, "to": m.get("id", "")})
        return deps

    def estimate_resources(self, plan: StrategicPlan) -> dict[str, Any]:
        return {"missions": 2, "estimated_hours": 4, "confidence": 0.6}

    def define_milestones(self, plan: StrategicPlan, missions: list[dict]) -> list[dict[str, Any]]:
        return [{"name": m.get("title", ""), "status": "pending"} for m in missions]

    def identify_critical_path(self, missions: list[dict]) -> list[str]:
        return [m.get("id", "") for m in missions]

    def detect_plan_drift(self, plan: StrategicPlan, current_state: dict[str, Any]) -> bool:
        return current_state.get("status", "") not in ("ACTIVE", "COMPLETED")

    def propose_replan(self, plan: StrategicPlan) -> StrategicPlan:
        plan.status = "REPLANNING"
        plan.confidence = max(0.1, plan.confidence - 0.1)
        return plan

    def record_plan(self, plan: StrategicPlan) -> str:
        content = json.dumps({
            "plan_id": plan.plan_id, "owner_goal": plan.owner_goal,
            "success_criteria": plan.success_criteria, "status": plan.status,
            "confidence": plan.confidence, "horizon": plan.planning_horizon,
        })
        return self._mc.commit(
            mission_id="global", key=f"plan:{plan.plan_id}",
            content=content, kind="procedural", confidence=plan.confidence,
        )

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall("global", layer="procedural")
        plans = [r for r in records if r.get("key", "").startswith("plan:")]
        return {"total_plans": len(plans)}
