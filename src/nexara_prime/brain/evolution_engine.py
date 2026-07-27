"""EvolutionEngine — learns from mission outcomes.

Records: what worked, what failed, what models were used, routing decisions.
Feeds back into model policy refinement.
"""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso


class EvolutionEngine:
    """Tracks mission outcomes for continuous improvement.

    Does NOT modify policies directly. Produces observations that the
    ChiefBrainKernel uses to refine model_policy and routing.
    """

    name = "evolution_engine"

    def __init__(self) -> None:
        self._observations: list[dict[str, Any]] = []

    def observe(
        self,
        mission_id: str,
        provider: str,
        model: str,
        success: bool,
        tokens: int,
        cost: float,
        routing_decision: dict[str, Any] | None = None,
    ) -> str:
        """Record a mission outcome observation."""
        obs_id = new_id("evo")
        observation = {
            "observation_id": obs_id,
            "mission_id": mission_id,
            "provider": provider,
            "model": model,
            "success": success,
            "tokens": tokens,
            "cost": cost,
            "routing_decision": routing_decision,
            "timestamp": now_iso(),
        }
        self._observations.append(observation)
        return obs_id

    def insights(self) -> dict[str, Any]:
        """Generate insights from observations."""
        if not self._observations:
            return {"status": "no_data"}

        total = len(self._observations)
        successes = sum(1 for o in self._observations if o["success"])
        total_cost = sum(o["cost"] for o in self._observations)
        total_tokens = sum(o["tokens"] for o in self._observations)
        providers_used = list({o["provider"] for o in self._observations})
        models_used = list({o["model"] for o in self._observations})

        return {
            "total_missions": total,
            "success_rate": round(successes / total, 2) if total else 0,
            "total_cost": round(total_cost, 8),
            "total_tokens": total_tokens,
            "avg_tokens_per_mission": total_tokens // total if total else 0,
            "providers_used": providers_used,
            "models_used": models_used,
        }

    def health(self) -> dict[str, Any]:
        return {"observations": len(self._observations), "insights": self.insights()}
