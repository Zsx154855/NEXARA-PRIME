"""V1.2.1 Failure Taxonomy — real-world failure sample database.

Classifies and records real failures (never success-only) so the intelligence
layer can learn from them. Independent L2 module; read-only over V1.1/V1.2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from nexara_prime.models import new_id, now_iso

__all__ = ["FailureCategory", "FailureRecord", "FailureDatabase"]


class FailureCategory(str, Enum):
    PLANNING = "planning"
    DECISION = "decision"
    CAPABILITY = "capability"
    TOOL = "tool"
    EXECUTION = "execution"
    RECOVERY = "recovery"
    MEMORY = "memory"
    COST = "cost"
    GOVERNANCE = "governance"


@dataclass
class FailureRecord:
    category: FailureCategory
    context: str = ""
    trigger: str = ""
    root_cause: str = ""
    recovery_action: str = ""
    final_result: str = ""
    lesson: str = ""
    failure_id: str = field(default_factory=lambda: new_id("failure"))
    timestamp: str = field(default_factory=now_iso)

    def as_dict(self) -> dict:
        return {
            "failure_id": self.failure_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "context": self.context,
            "trigger": self.trigger,
            "root_cause": self.root_cause,
            "recovery_action": self.recovery_action,
            "final_result": self.final_result,
            "lesson": self.lesson,
        }


class FailureDatabase:
    """In-memory + JSON-serializable collection of failure records."""

    def __init__(self):
        self._records: list[FailureRecord] = []

    def record(self, rec: FailureRecord) -> FailureRecord:
        self._records.append(rec)
        return rec

    def by_category(self, category: FailureCategory) -> list[FailureRecord]:
        return [r for r in self._records if r.category is category]

    def count(self) -> int:
        return len(self._records)

    def categories_present(self) -> list[str]:
        return sorted({r.category.value for r in self._records})

    def to_dicts(self) -> list[dict]:
        return [r.as_dict() for r in self._records]
