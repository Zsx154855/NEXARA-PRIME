"""GoalManager — hierarchical goal tracking for Chief Brain."""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso


class GoalManager:
    """Tracks goals hierarchically. Goals decompose into sub-goals."""

    name = "goal_manager"

    def __init__(self) -> None:
        self._goals: dict[str, dict[str, Any]] = {}

    def decompose(self, objective: str) -> list[dict[str, Any]]:
        """Decompose an objective into atomic goals."""
        goals = []
        words = objective.split()
        if len(words) <= 3:
            goals.append(self._make_goal(objective, 0))
        else:
            goals.append(self._make_goal(f"Plan: {objective[:60]}", 0))
            goals.append(self._make_goal(f"Execute: {objective[:60]}", 0))
            goals.append(self._make_goal(f"Verify: {objective[:60]}", 0))
        return goals

    def active(self) -> list[dict[str, Any]]:
        return [g for g in self._goals.values() if g["status"] == "active"]

    def complete(self, goal_id: str) -> None:
        if goal_id in self._goals:
            self._goals[goal_id]["status"] = "completed"
            self._goals[goal_id]["completed_at"] = now_iso()

    def block(self, goal_id: str, reason: str) -> None:
        if goal_id in self._goals:
            self._goals[goal_id]["status"] = "blocked"
            self._goals[goal_id]["block_reason"] = reason

    def _make_goal(self, description: str, parent_index: int) -> dict[str, Any]:
        goal = {
            "goal_id": new_id("goal"),
            "description": description,
            "status": "active",
            "parent_index": parent_index,
            "evidence_refs": [],
            "created_at": now_iso(),
            "completed_at": None,
        }
        self._goals[goal["goal_id"]] = goal
        return goal
