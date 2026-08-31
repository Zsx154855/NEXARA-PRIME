"""V1.2 Intelligence Layer — Decision Object Contracts.

Decision / DecisionTrace / ReasoningMode first-class decision objects.
Independent L2 overlay; read-only over V1.1 (does not import/modify
V1.1 Runtime Core).  DecisionTrace deliberately carries NO chain_of_thought
field — only a decision_summary, reason_code, and policy_reference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = ["Decision", "ReasoningMode", "DecisionTrace"]


class ReasoningMode(str, Enum):
    """How much deliberation the engine invests before deciding."""

    NORMAL = "normal"
    FAST = "fast"
    DEEP = "deep"
    RECOVERY = "recovery"
    COST_OPTIMIZED = "cost_optimized"


@dataclass
class Decision:
    """A single, auditable decision produced by the DecisionEngine."""

    input: Any = None
    context: dict[str, Any] = field(default_factory=dict)
    available_actions: list[Any] = field(default_factory=list)
    selected_action: Any = None
    confidence: float = 0.0
    reason_code: str = ""  # e.g. 'policy_mandated' | 'first_available'
    policy_reference: str = ""


@dataclass
class DecisionTrace:
    """Compact, audit-only trace of a decision. No chain_of_thought."""

    decision_summary: str = ""
    reason_code: str = ""
    policy_reference: str = ""
