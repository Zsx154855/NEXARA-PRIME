"""V1.2 Agent Council — five-role collaboration with governance.

Multi-agent coordination surface: a council holds one agent per role and
exposes a fixed collaboration pipeline plus a governance contract
(single-writer, least-privilege, evidence-required, role-separation).
Read-only over V1.1 — never imports or mutates V1.1 Runtime Core / SQLite.
"""
from __future__ import annotations

from .contracts import CouncilAgent, CouncilRole

__all__ = ["AgentCouncil"]


class AgentCouncil:
    """Coordinates the five council roles into a governed pipeline."""

    def __init__(self) -> None:
        self._agents: dict[CouncilRole, CouncilAgent] = {}

    # -- membership -- #

    def add_agent(self, agent: CouncilAgent) -> CouncilAgent:
        self._agents[agent.role] = agent
        return agent

    def add_default_agents(self) -> list[CouncilAgent]:
        """Seed one agent per role with default responsibilities and scopes."""
        defaults: list[tuple[CouncilRole, str, str, list[str]]] = [
            (
                CouncilRole.PLANNER,
                "planner",
                "Decompose goals into dependency-aware plans.",
                ["read", "plan", "estimate"],
            ),
            (
                CouncilRole.EXECUTOR,
                "executor",
                "Execute planned steps within granted scope.",
                ["read", "execute"],
            ),
            (
                CouncilRole.REVIEWER,
                "reviewer",
                "Verify outcomes against success criteria.",
                ["read", "review"],
            ),
            (
                CouncilRole.SECURITY,
                "security",
                "Audit actions for policy and safety compliance.",
                ["read", "audit"],
            ),
            (
                CouncilRole.COST,
                "cost",
                "Track and bound token / compute spend.",
                ["read", "meter"],
            ),
        ]
        added = [
            self.add_agent(
                CouncilAgent(
                    name=name,
                    role=role,
                    responsibility=resp,
                    least_privilege=list(scope),
                )
            )
            for role, name, resp, scope in defaults
        ]
        return added

    # -- collaboration -- #

    def pipeline(self) -> list[str]:
        """Fixed role collaboration order."""
        return [r.value for r in CouncilRole]

    def assign(self, role: CouncilRole) -> CouncilAgent:
        """Return the agent bound to `role`, seeding a default if absent."""
        if role not in self._agents:
            self.add_default_agents()
        return self._agents[role]

    # -- governance -- #

    def governance(self) -> dict[str, bool]:
        return {
            "single_writer": True,
            "least_privilege": True,
            "evidence_required": True,
            "role_separation": True,
        }
