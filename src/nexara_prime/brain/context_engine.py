"""ContextEngine — compiles mission context from runtime state."""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso


class ContextEngine:
    """Compiles bounded context for mission execution.

    Does NOT access external systems. Only reads local runtime state.
    """

    name = "context_engine"

    def compile(self, mission_spec: dict[str, Any], runtime_state: dict[str, Any]) -> dict[str, Any]:
        """Compile a bounded context for model consumption."""
        return {
            "context_id": new_id("ctx"),
            "mission_id": mission_spec.get("mission_id", ""),
            "objective": mission_spec.get("objective", ""),
            "risk_level": mission_spec.get("risk_level", "R1"),
            "boundaries": mission_spec.get("boundaries", []),
            "constraints": mission_spec.get("constraints", []),
            "deliverables": mission_spec.get("deliverables", []),
            "available_tools": runtime_state.get("available_tools", []),
            "evidence_count": runtime_state.get("evidence_count", 0),
            "model_provider": runtime_state.get("model_provider", "unknown"),
            "compiled_at": now_iso(),
        }

    def enrich(self, context: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
        """Enrich context with additional facts."""
        enriched = dict(context)
        enriched.update({k: v for k, v in facts.items() if k not in enriched})
        enriched["enriched_at"] = now_iso()
        return enriched
