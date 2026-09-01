"""L2 V1.1 formal object model — TokenUsage / CostRecord / AuditEvent / RuntimeVersion.

Independent L2 dataclasses formalising the V1.1 first-class objects that were
previously implicit in telemetry/audit/version handling. No V1.0 Core import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import new_id, now_iso

__all__ = ["Agent", "AgentStatus", "TokenUsage", "CostRecord", "AuditEvent", "RuntimeVersion"]


class AgentStatus(str, Enum):
    CREATED = "created"
    READY = "ready"
    BUSY = "busy"
    IDLE = "idle"
    FAILED = "failed"


@dataclass
class Agent:
    """A sovereign executor. Owns missions via ``mission_ids``."""

    id: str = field(default_factory=lambda: new_id("agent"))
    name: str = ""
    role: str = "executor"
    model: str = ""
    provider: str = ""
    status: AgentStatus = AgentStatus.CREATED
    created_at: str = field(default_factory=now_iso)
    version: int = 1
    mission_ids: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, name: str, role: str = "executor", model: str = "", provider: str = "") -> "Agent":
        return cls(name=name, role=role, model=model, provider=provider)

    def bind_mission(self, mission_id: str) -> "Agent":
        if mission_id not in self.mission_ids:
            self.mission_ids.append(mission_id)
            self.version += 1
        return self

    def transition(self, target: AgentStatus) -> "Agent":
        self.status = target
        self.version += 1
        return self


@dataclass
class TokenUsage:
    """Formal per-call token accounting record."""

    id: str = field(default_factory=lambda: new_id("token"))
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    retry: int = 0
    cost_usd: float | None = None  # None = provider did not report cost (never forged 0)
    provider: str = ""
    model: str = ""
    session_id: str = ""
    mission_id: str = ""
    timestamp: str = field(default_factory=now_iso)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CostRecord:
    """Formal cost record derived from token usage."""

    id: str = field(default_factory=lambda: new_id("cost"))
    token_usage_id: str = ""
    cost_usd: float = 0.0
    provider: str = ""
    model: str = ""
    scope: str = ""  # session / mission / provider / model / daily
    timestamp: str = field(default_factory=now_iso)


@dataclass
class AuditEvent:
    """Formal audit event envelope."""

    id: str = field(default_factory=lambda: new_id("audit"))
    actor: str = ""
    action: str = ""
    target_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    timestamp: str = field(default_factory=now_iso)


@dataclass
class RuntimeVersion:
    """Formal runtime version identity."""

    runtime_version: str = "0.1.0"
    git_sha: str = ""
    schema_version: str = "1"
    sealed: bool = False

    @property
    def identity(self) -> str:
        return f"{self.runtime_version}@{self.git_sha[:8] if self.git_sha else 'unknown'}"
