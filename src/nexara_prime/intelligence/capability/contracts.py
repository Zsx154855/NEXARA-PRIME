"""V1.2 Intelligence Layer — Capability Object Contract.

Capability is a self-describing unit of action (name/description/inputs/outputs/
tools/cost/risk/permission/success_rate). Independent L2 overlay; read-only
over V1.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nexara_prime.models import new_id

__all__ = ["Capability"]


@dataclass
class Capability:
    """A discoverable action the agent can take, with cost/risk metadata."""

    id: str = field(default_factory=lambda: new_id("cap"))
    name: str = ""
    description: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    cost: float = 0.0
    risk: str = "low"  # low | medium | high
    permission: str = ""
    success_rate: float = 0.0
