"""Tests for L2 TokenGovernor — five-layer budget enforcement."""
import pytest
from nexara_prime.cost_governor import TokenGovernor, ScopeUsage, OK, WARN, BLOCK


class TestScopeUsage:
    def test_add_with_cost(self):
        su = ScopeUsage(scope="session", key="s1")
        su.add(100, 0.01)
        assert su.tokens == 100
        assert su.cost_usd == pytest.approx(0.01)

    def test_add_none_cost_ignored(self):
        su = ScopeUsage(scope="session", key="s1")
        su.add(100, None)
        assert su.tokens == 100
        assert su.cost_usd == 0.0


class TestTokenGovernor:
    def test_no_budget_always_ok(self):
        gov = TokenGovernor()
        assert gov.record_usage("session", "s1", 999999) == OK

    def test_under_limit_ok(self):
        gov = TokenGovernor()
        gov.set_budget("session", "s1", 1000)
        assert gov.record_usage("session", "s1", 500) == OK

    def test_warn_threshold(self):
        gov = TokenGovernor(warn_ratio=0.8)
        gov.set_budget("session", "s1", 1000)
        assert gov.record_usage("session", "s1", 800) == WARN

    def test_over_limit_block(self):
        gov = TokenGovernor()
        gov.set_budget("session", "s1", 1000)
        gov.record_usage("session", "s1", 800)
        assert gov.record_usage("session", "s1", 300) == BLOCK

    def test_invalid_scope_raises(self):
        gov = TokenGovernor()
        with pytest.raises(ValueError, match="unknown budget scope"):
            gov.record_usage("invalid_scope", "k", 10)

    def test_negative_tokens_raises(self):
        gov = TokenGovernor()
        with pytest.raises(ValueError, match="non-negative"):
            gov.record_usage("session", "s1", -1)

    def test_daily_scope_global(self):
        gov = TokenGovernor()
        gov.set_budget("daily", "any_key", 500)
        gov.record_usage("daily", "key_a", 100)
        gov.record_usage("daily", "key_b", 200)
        check = gov.check("daily", "key_a")
        assert check["used_tokens"] == 300

    def test_reset_daily(self):
        gov = TokenGovernor()
        gov.record_usage("daily", "x", 100)
        cleared = gov.reset_daily()
        assert cleared == 1
        assert gov.check("daily", "x")["used_tokens"] == 0

    def test_snapshot(self):
        gov = TokenGovernor()
        gov.set_budget("session", "s1", 1000)
        gov.record_usage("session", "s1", 100, 0.05)
        snap = gov.snapshot()
        assert "session:s1" in snap
        assert snap["session:s1"]["used_tokens"] == 100

    def test_invalid_warn_ratio(self):
        with pytest.raises(ValueError):
            TokenGovernor(warn_ratio=0.0)
        with pytest.raises(ValueError):
            TokenGovernor(warn_ratio=1.5)
