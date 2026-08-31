"""V1.2 Intelligence Layer — DecisionEngine.

Deterministic action selection: honour an explicit policy-mandated action,
otherwise fall back to the first available action. Confidence is a function
of the active ReasoningMode. Read-only over V1.1.
"""
from __future__ import annotations

from typing import Any

from .contracts import Decision, ReasoningMode

__all__ = ["DecisionEngine"]

# mode -> confidence
_CONFIDENCE: dict[ReasoningMode, float] = {
    ReasoningMode.NORMAL: 0.8,
    ReasoningMode.FAST: 0.6,
    ReasoningMode.DEEP: 0.9,
    ReasoningMode.RECOVERY: 0.5,
    ReasoningMode.COST_OPTIMIZED: 0.7,
}

# policy keys that may carry a forced/mandated action, in priority order.
_MANDATORY_KEYS: tuple[str, ...] = ("mandatory_action", "forced_action", "action")


def _objective(goal: Any) -> str:
    if isinstance(goal, dict):
        return goal.get("objective") or goal.get("intent") or str(goal)
    return getattr(goal, "objective", None) or str(goal)


class DecisionEngine:
    """Pick an action from available_actions under an optional policy."""

    def __init__(
        self,
        goal: Any = None,
        context: dict[str, Any] | None = None,
        available_actions: list[Any] | None = None,
        policy: dict[str, Any] | None = None,
        reasoning_mode: ReasoningMode = ReasoningMode.NORMAL,
    ):
        self.goal = goal
        self.context = context or {}
        self.available_actions = available_actions or []
        self.policy = policy or {}
        self.reasoning_mode = reasoning_mode

    def decide(
        self,
        goal: Any = None,
        available_actions: list[Any] | None = None,
        policy: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        reasoning_mode: ReasoningMode | None = None,
    ) -> Decision:
        goal = self.goal if goal is None else goal
        context = self.context if context is None else context
        available_actions = self.available_actions if available_actions is None else available_actions
        policy = self.policy if policy is None else policy
        mode = self.reasoning_mode if reasoning_mode is None else reasoning_mode

        policy = policy or {}
        actions = list(available_actions or [])

        # 1) policy-mandated action wins.
        selected = None
        reason_code = "first_available"
        policy_reference = policy.get("policy_reference") or policy.get("name") or ""
        for key in _MANDATORY_KEYS:
            if key in policy and policy[key] is not None:
                selected = policy[key]
                reason_code = "policy_mandated"
                break

        # 2) otherwise first available.
        if selected is None and actions:
            selected = actions[0]

        # 3) no action available at all → zero confidence, explicit reason.
        confidence = _CONFIDENCE.get(mode, _CONFIDENCE[ReasoningMode.NORMAL])
        if selected is None:
            reason_code = "no_available_action"
            confidence = 0.0

        return Decision(
            input=_objective(goal),
            context=dict(context or {}),
            available_actions=actions,
            selected_action=selected,
            confidence=confidence,
            reason_code=reason_code,
            policy_reference=policy_reference,
        )
