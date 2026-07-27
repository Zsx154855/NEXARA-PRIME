"""DeepReasoningEngine — multi-hypothesis reasoning with structured output."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ..models import now_iso
from .cognitive_models import ReasoningDecision

if TYPE_CHECKING:
    from .memory_controller import MemoryController


class DeepReasoningEngine:
    """Multi-hypothesis reasoning with constraint detection, strategy comparison, and risk analysis."""

    def __init__(self, memory_controller: MemoryController) -> None:
        self._mc = memory_controller

    def reason(self, mission: dict[str, Any], context: dict[str, Any] | None = None) -> ReasoningDecision:
        goal = mission.get("objective", mission.get("goal", "unknown"))
        constraints = self._identify_constraints(mission, context or {})
        hypotheses = self._generate_hypotheses(goal, constraints)
        strategies = self._generate_alternatives(goal, hypotheses)
        risk = self._analyze_risks(strategies)
        comparison = self.compare_strategies(strategies)
        selected = comparison[0] if comparison else ""

        return ReasoningDecision(
            decision_id=f"dec_{now_iso()}",
            mission_id=mission.get("mission_id", ""),
            normalized_goal=goal,
            constraints=constraints,
            hypotheses=hypotheses,
            candidate_strategies=strategies,
            selected_strategy=selected,
            rejected_strategies=[s.get("name", "") for s in strategies[1:]] if len(strategies) > 1 else [],
            risk_analysis=risk,
            expected_outcomes=[s.get("expected_outcome", "") for s in strategies[:3]],
            confidence=0.6 if comparison else 0.3,
            uncertainty=0.4 if comparison else 0.7,
            created_at=now_iso(),
        )

    def normalize_problem(self, goal: str) -> dict[str, Any]:
        return {"goal": goal, "domain": goal.split()[0] if goal else "general", "complexity": "medium"}

    def _identify_constraints(self, mission: dict, context: dict) -> list[str]:
        constraints = []
        if mission.get("risk_level") == "high":
            constraints.append("high_risk_execution")
        if mission.get("type") == "deployment":
            constraints.append("deployment_safety")
        return constraints + context.get("constraints", [])

    def _generate_hypotheses(self, goal: str, constraints: list[str]) -> list[dict[str, Any]]:
        return [
            {"id": "h1", "statement": f"Standard approach achieves {goal}", "confidence": 0.7},
            {"id": "h2", "statement": f"Alternative approach needed due to {constraints[:1]}", "confidence": 0.4},
        ]

    def _generate_alternatives(self, goal: str, hypotheses: list) -> list[dict[str, Any]]:
        return [
            {"name": "standard", "approach": "Direct execution", "risk": 0.3, "expected_outcome": f"Achieve {goal}"},
            {"name": "cautious", "approach": "Phased execution with checkpoints", "risk": 0.15, "expected_outcome": f"Safely achieve {goal}"},
        ]

    def compare_strategies(self, strategies: list[dict]) -> list[str]:
        if not strategies:
            return []
        scored = sorted(strategies, key=lambda s: 1.0 - float(s.get("risk", 0.5)), reverse=True)
        return [s.get("name", "") for s in scored]

    def detect_conflicts(self, constraints: list[str]) -> list[str]:
        conflicts = []
        if "high_risk_execution" in constraints and "deployment_safety" in constraints:
            conflicts.append("risk_deployment_conflict")
        return conflicts

    def _analyze_risks(self, strategies: list[dict]) -> dict[str, float]:
        return {s.get("name", "unknown"): float(s.get("risk", 0.5)) for s in strategies}

    def counterfactual(self, selected: str, strategies: list[dict]) -> dict[str, Any]:
        return {
            "selected": selected,
            "alternatives": [s.get("name") for s in strategies if s.get("name") != selected],
            "analysis": "Counterfactual analysis requires full context — see strategy comparison",
        }

    def emit_decision(self, decision: ReasoningDecision) -> str:
        content = json.dumps({
            "decision_id": decision.decision_id, "mission_id": decision.mission_id,
            "goal": decision.normalized_goal, "constraints": decision.constraints,
            "selected": decision.selected_strategy, "confidence": decision.confidence,
            "risk_analysis": decision.risk_analysis, "evidence_refs": decision.evidence_refs,
            "created_at": decision.created_at,
        })
        return self._mc.commit(
            mission_id=decision.mission_id, key=f"decision:{decision.decision_id}",
            content=content, kind="procedural", confidence=decision.confidence,
        )

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall("global", layer="procedural")
        decisions = [r for r in records if r.get("key", "").startswith("decision:")]
        return {"total_decisions": len(decisions)}
