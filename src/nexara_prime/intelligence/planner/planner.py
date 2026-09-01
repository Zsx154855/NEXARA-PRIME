"""V1.2 Planner Interface — Goal → Plan → TaskGraph → Mission mapping.

Thin orchestration layer over the V1.1 Mission API. Read-only against V1.1:
it never imports or mutates V1.1 Runtime Core / SQLite semantics — it only
drives the existing HTTP Mission API.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from .contracts import Goal, Plan, PlanStep, TaskGraph, TaskNode

__all__ = ["Planner"]


class Planner:
    """Minimal intelligence planning loop: understand → decompose → graph → mission."""

    def __init__(self, base_url: str = "http://127.0.0.1:8765"):
        self.base_url = base_url.rstrip("/")

    # -- planning -- #

    def understand(self, user_request: str) -> Goal:
        return Goal(
            user_intent=user_request,
            objective=user_request,
            success_criteria=[f"完成: {user_request}"],
        )

    def decompose(self, goal: Goal) -> Plan:
        s1 = PlanStep(description="理解目标与约束", kind="agent")
        s2 = PlanStep(description="执行核心任务", kind="tool")
        s3 = PlanStep(description="验证结果符合成功标准", kind="verification")
        s2.dependencies = [s1.id]
        s3.dependencies = [s2.id]
        return Plan(goal_id=goal.id, steps=[s1, s2, s3], risk="low")

    def build_graph(self, plan: Plan) -> TaskGraph:
        nodes = [
            TaskNode(id=s.id, name=s.description, kind=s.kind, dependencies=list(s.dependencies))
            for s in plan.steps
        ]
        return TaskGraph(goal_id=plan.goal_id, nodes=nodes)

    # -- V1.1 Mission API bridge -- #

    def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else b""
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data or None,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return json.loads(urllib.request.urlopen(req, timeout=180).read())

    def to_mission(self, goal: Goal) -> dict[str, Any]:
        """Map a Goal onto a V1.1 Mission via the existing HTTP API."""
        return self._post("/api/missions", {"objective": goal.objective, "source_dir": "."})

    def plan_mission(self, mission_id: str) -> dict[str, Any]:
        return self._post(f"/api/missions/{mission_id}/plan", None)

    def run_mission(self, mission_id: str) -> dict[str, Any]:
        return self._post(f"/api/missions/{mission_id}/run", None)

    # -- full loop -- #

    def plan_and_execute(self, user_request: str) -> dict[str, Any]:
        goal = self.understand(user_request)
        plan = self.decompose(goal)
        graph = self.build_graph(plan)
        mission = self.to_mission(goal)
        return {
            "goal_id": goal.id,
            "plan_id": plan.id,
            "step_count": len(plan.steps),
            "graph_nodes": len(graph.nodes),
            "graph_adjacency": graph.as_adjacency(),
            "mission_id": mission.get("mission_id"),
            "mission_state": mission.get("current_state") or mission.get("state"),
        }
