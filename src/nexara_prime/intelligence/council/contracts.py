"""V1.2 Intelligence Layer — Agent Council Object Contracts.

CouncilRole / CouncilAgent first-class collaboration objects. Independent L2
overlay; read-only over V1.1 (does not import/modify V1.1 Runtime Core or SQLite).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from nexara_prime.models import new_id, now_iso

__all__ = ["CouncilRole", "CouncilAgent"]


class CouncilRole(str, Enum):
    """The five fixed roles that collaborate inside an Agent Council.

    Order of definition is the canonical pipeline order.
    """

    PLANNER = "PLANNER"
    EXECUTOR = "EXECUTOR"
    REVIEWER = "REVIEWER"
    SECURITY = "SECURITY"
    COST = "COST"


@dataclass
class CouncilAgent:
    """One seat in the council, bound to a role with least-privilege scope."""

    id: str = field(default_factory=lambda: new_id("agent"))
    name: str = ""
    role: CouncilRole = CouncilRole.PLANNER
    responsibility: str = ""
    least_privilege: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
