"""Tests for L2 V1.1 formal object model."""
import pytest
from nexara_prime.v1_1_objects import (
    Agent, AgentStatus, TokenUsage, CostRecord, AuditEvent, RuntimeVersion,
)


class TestAgent:
    def test_create(self):
        a = Agent.create("prime", role="executor", model="deepseek-v4-pro")
        assert a.name == "prime"
        assert a.status == AgentStatus.CREATED
        assert a.version == 1

    def test_bind_mission(self):
        a = Agent.create("prime")
        a.bind_mission("m1")
        assert "m1" in a.mission_ids
        assert a.version == 2

    def test_bind_mission_dedup(self):
        a = Agent.create("prime")
        a.bind_mission("m1")
        a.bind_mission("m1")
        assert len(a.mission_ids) == 1

    def test_transition(self):
        a = Agent.create("prime")
        a.transition(AgentStatus.READY)
        assert a.status == AgentStatus.READY


class TestTokenUsage:
    def test_total_tokens(self):
        t = TokenUsage(input_tokens=100, output_tokens=50)
        assert t.total_tokens == 150

    def test_cost_none_default(self):
        t = TokenUsage()
        assert t.cost_usd is None


class TestCostRecord:
    def test_defaults(self):
        c = CostRecord()
        assert c.cost_usd == 0.0
        assert c.id.startswith("cost_")


class TestAuditEvent:
    def test_defaults(self):
        e = AuditEvent(actor="system", action="test")
        assert e.actor == "system"
        assert e.id.startswith("audit_")


class TestRuntimeVersion:
    def test_identity(self):
        rv = RuntimeVersion(runtime_version="0.1.0", git_sha="abc12345def")
        assert rv.identity == "0.1.0@abc12345"

    def test_identity_no_sha(self):
        rv = RuntimeVersion()
        assert "unknown" in rv.identity
