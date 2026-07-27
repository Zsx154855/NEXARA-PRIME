"""Planner — mission planning with goal decomposition."""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso


class Planner:
    """Decomposes objectives into execution plans."""

    name = "planner"

    def plan(self, objective: str, risk_level: str, boundaries: list[str], deliverables: list[str]) -> dict[str, Any]:
        plan_id = new_id("plan")
        steps = self._decompose(objective, risk_level)
        return {
            "plan_id": plan_id,
            "objective": objective,
            "risk_level": risk_level,
            "boundaries": boundaries,
            "deliverables": deliverables,
            "steps": steps,
            "created_at": now_iso(),
        }

    @staticmethod
    def _decompose(objective: str, risk_level: str) -> list[dict[str, Any]]:
        steps = [
            {"order": 1, "role": "Orchestrator", "action": "validate_boundaries", "description": "Verify operation boundaries and constraints"},
            {"order": 2, "role": "Planner", "action": "assess_capabilities", "description": "List available capabilities and gaps"},
            {"order": 3, "role": "Analyst", "action": "analyze_context", "description": "Compile execution context"},
            {"order": 4, "role": "Executor", "action": "execute_task", "description": f"Execute: {objective[:80]}"},
            {"order": 5, "role": "Reviewer", "action": "verify_outputs", "description": "Verify results against acceptance criteria"},
            {"order": 6, "role": "Auditor", "action": "audit_trail", "description": "Evidence chain integrity check"},
            {"order": 7, "role": "Archivist", "action": "archive_evidence", "description": "Commit evidence to store"},
        ]
        if risk_level in ("R3", "R4"):
            steps.insert(3, {"order": 3, "role": "Auditor", "action": "risk_gate", "description": "Human approval gate before execution"})
        return steps
