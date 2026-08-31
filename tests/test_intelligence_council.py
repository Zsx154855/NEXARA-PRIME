"""Tests for intelligence.council — CouncilRole / CouncilAgent / AgentCouncil."""
from __future__ import annotations

import pytest

from nexara_prime.intelligence.council.contracts import CouncilAgent, CouncilRole
from nexara_prime.intelligence.council.council import AgentCouncil


class TestCouncilRole:
    def test_five_roles(self):
        assert len(CouncilRole) == 5

    def test_pipeline_order(self):
        names = [r.value for r in CouncilRole]
        assert names == ["PLANNER", "EXECUTOR", "REVIEWER", "SECURITY", "COST"]


class TestCouncilAgent:
    def test_defaults(self):
        a = CouncilAgent()
        assert a.id.startswith("agent_")
        assert a.role is CouncilRole.PLANNER
        assert a.least_privilege == []

    def test_custom(self):
        a = CouncilAgent(name="sec", role=CouncilRole.SECURITY, least_privilege=["read", "audit"])
        assert a.name == "sec"
        assert a.role is CouncilRole.SECURITY
        assert a.least_privilege == ["read", "audit"]


class TestAgentCouncil:
    def test_empty_council(self):
        c = AgentCouncil()
        assert c.pipeline() == ["PLANNER", "EXECUTOR", "REVIEWER", "SECURITY", "COST"]

    def test_add_agent(self):
        c = AgentCouncil()
        a = CouncilAgent(name="p", role=CouncilRole.PLANNER)
        returned = c.add_agent(a)
        assert returned is a

    def test_add_default_agents(self):
        c = AgentCouncil()
        agents = c.add_default_agents()
        assert len(agents) == 5
        roles = {a.role for a in agents}
        assert roles == set(CouncilRole)

    def test_assign_seeds_defaults(self):
        c = AgentCouncil()
        agent = c.assign(CouncilRole.SECURITY)
        assert agent.role is CouncilRole.SECURITY
        assert agent.name == "security"

    def test_assign_returns_existing(self):
        c = AgentCouncil()
        custom = CouncilAgent(name="my_planner", role=CouncilRole.PLANNER)
        c.add_agent(custom)
        assert c.assign(CouncilRole.PLANNER) is custom

    def test_governance_all_true(self):
        c = AgentCouncil()
        g = c.governance()
        assert g == {
            "single_writer": True,
            "least_privilege": True,
            "evidence_required": True,
            "role_separation": True,
        }

    def test_default_privilege_scopes(self):
        c = AgentCouncil()
        c.add_default_agents()
        planner = c.assign(CouncilRole.PLANNER)
        assert "plan" in planner.least_privilege
        cost = c.assign(CouncilRole.COST)
        assert "meter" in cost.least_privilege

    def test_add_agent_overwrites_role(self):
        c = AgentCouncil()
        c.add_agent(CouncilAgent(name="first", role=CouncilRole.EXECUTOR))
        c.add_agent(CouncilAgent(name="second", role=CouncilRole.EXECUTOR))
        assert c.assign(CouncilRole.EXECUTOR).name == "second"
