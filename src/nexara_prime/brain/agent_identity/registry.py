"""Agent Identity Capability System — agent registry, profiles, and reputation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexara_prime.models import now_iso, new_id


class AgentRole(str, Enum):
    ARCHITECT = "architect"
    PLANNER = "planner"
    EXECUTOR = "executor"
    CRITIC = "critic"
    AUDITOR = "auditor"
    MEMORY_AGENT = "memory_agent"


@dataclass
class CapabilityProfile:
    role: AgentRole
    allowed_actions: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    max_risk_level: str = "R2"


@dataclass
class AgentIdentity:
    agent_id: str
    role: AgentRole
    capabilities: CapabilityProfile
    reputation: float = 0.5
    total_missions: int = 0
    successes: int = 0
    created_at: str = field(default_factory=now_iso)


DEFAULT_PROFILES: dict[AgentRole, CapabilityProfile] = {
    AgentRole.ARCHITECT: CapabilityProfile(AgentRole.ARCHITECT, ["architecture_review", "planning", "analysis"], ["direct_execution", "external_action"], "R3"),
    AgentRole.PLANNER: CapabilityProfile(AgentRole.PLANNER, ["planning", "decomposition", "estimation"], ["direct_execution", "governance_change"], "R2"),
    AgentRole.EXECUTOR: CapabilityProfile(AgentRole.EXECUTOR, ["implementation", "testing", "execution"], ["governance_change", "policy_override"], "R2"),
    AgentRole.CRITIC: CapabilityProfile(AgentRole.CRITIC, ["review", "critique", "feedback"], ["execution", "deployment"], "R3"),
    AgentRole.AUDITOR: CapabilityProfile(AgentRole.AUDITOR, ["audit", "verify", "evidence_check"], ["execution", "modification"], "R4"),
    AgentRole.MEMORY_AGENT: CapabilityProfile(AgentRole.MEMORY_AGENT, ["memory_read", "memory_query", "pattern_retrieval"], ["memory_write", "memory_delete"], "R2"),
}


class AgentRegistry:
    """Registry of agent identities with capability profiles."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentIdentity] = {}

    def register(self, role: AgentRole, agent_id: str | None = None) -> AgentIdentity:
        aid = agent_id or new_id("agt")
        profile = DEFAULT_PROFILES[role]
        agent = AgentIdentity(aid, role, profile)
        self._agents[aid] = agent
        return agent

    def get(self, agent_id: str) -> AgentIdentity | None:
        return self._agents.get(agent_id)

    def list_by_role(self, role: AgentRole) -> list[AgentIdentity]:
        return [a for a in self._agents.values() if a.role == role]

    def can_execute(self, agent_id: str, action: str, risk_level: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        if action in agent.capabilities.forbidden_actions:
            return False
        if action not in agent.capabilities.allowed_actions:
            return False
        risk_order = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}
        return risk_order.get(risk_level, 4) <= risk_order.get(agent.capabilities.max_risk_level, 2)

    def record_mission(self, agent_id: str, success: bool) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.total_missions += 1
            if success:
                agent.successes += 1
            agent.reputation = agent.successes / max(agent.total_missions, 1)

    def stats(self) -> dict[str, Any]:
        return {"total_agents": len(self._agents), "by_role": {r.value: len(self.list_by_role(r)) for r in AgentRole}}
