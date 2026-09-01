"""Tests for intelligence.capability — Capability contract + CapabilityRegistry + _tokens."""
from __future__ import annotations

import pytest

from nexara_prime.intelligence.capability.contracts import Capability
from nexara_prime.intelligence.capability.registry import CapabilityRegistry, _tokens


class TestCapability:
    def test_defaults(self):
        c = Capability()
        assert c.id.startswith("cap_")
        assert c.name == ""
        assert c.risk == "low"
        assert c.cost == 0.0
        assert c.success_rate == 0.0


class TestTokens:
    def test_latin_words(self):
        assert _tokens("hello world") == {"hello", "world"}

    def test_case_insensitive(self):
        assert _tokens("Hello WORLD") == {"hello", "world"}

    def test_cjk_bigrams(self):
        tokens = _tokens("检查运行")
        assert "检查" in tokens
        assert "查运" in tokens
        assert "运行" in tokens

    def test_mixed_latin_cjk(self):
        tokens = _tokens("run测试")
        assert "run" in tokens
        assert "测试" in tokens

    def test_empty_string(self):
        assert _tokens("") == set()

    def test_none_safe(self):
        assert _tokens(None) == set()

    def test_alphanumeric_tokens(self):
        tokens = _tokens("v42 test")
        assert "v42" in tokens
        assert "test" in tokens


class TestCapabilityRegistry:
    def test_empty_registry_no_match(self):
        reg = CapabilityRegistry()
        assert reg.match("anything") is None

    def test_register_and_match_by_name(self):
        reg = CapabilityRegistry()
        cap = Capability(name="health check", description="check runtime health")
        reg.register(cap)
        assert reg.match("health check") is cap

    def test_match_by_description_substring(self):
        reg = CapabilityRegistry()
        cap = Capability(name="hc", description="verify runtime health status")
        reg.register(cap)
        assert reg.match("runtime health") is cap

    def test_match_by_keyword_overlap(self):
        reg = CapabilityRegistry()
        cap = Capability(name="deploy", description="deploy service to production")
        reg.register(cap)
        result = reg.match("deploy production")
        assert result is cap

    def test_no_match_returns_none(self):
        reg = CapabilityRegistry()
        reg.register(Capability(name="deploy", description="deploy service"))
        assert reg.match("completely unrelated xyz") is None

    def test_best_overlap_wins(self):
        reg = CapabilityRegistry()
        cap_a = Capability(name="deploy", description="deploy service")
        cap_b = Capability(name="deploy monitor", description="deploy and monitor service")
        reg.register(cap_a)
        reg.register(cap_b)
        result = reg.match("deploy monitor service")
        assert result is cap_b

    def test_select_tools(self):
        reg = CapabilityRegistry()
        cap = Capability(tools=["git", "docker"])
        reg.register(cap)
        assert reg.select_tools(cap) == ["git", "docker"]

    def test_empty_goal_no_match(self):
        reg = CapabilityRegistry()
        reg.register(Capability(name="test", description="test"))
        assert reg.match("") is None

    def test_cjk_match(self):
        reg = CapabilityRegistry()
        cap = Capability(name="健康检查", description="检查运行时健康状态")
        reg.register(cap)
        result = reg.match("检查运行状态")
        assert result is cap

    def test_register_overwrite_same_id(self):
        reg = CapabilityRegistry()
        cap1 = Capability(id="cap_x", name="old")
        cap2 = Capability(id="cap_x", name="new")
        reg.register(cap1)
        reg.register(cap2)
        assert reg.match("new") is cap2
        assert reg.match("old") is None

    def test_none_goal_no_match(self):
        reg = CapabilityRegistry()
        reg.register(Capability(name="test", description="test"))
        assert reg.match(None) is None

    def test_tie_breaking_first_registered_wins(self):
        reg = CapabilityRegistry()
        cap_a = Capability(name="alpha", description="shared")
        cap_b = Capability(name="beta", description="shared")
        reg.register(cap_a)
        reg.register(cap_b)
        result = reg.match("shared")
        assert result is cap_a or result is cap_b

    def test_empty_name_and_description_no_keyword_match(self):
        reg = CapabilityRegistry()
        reg.register(Capability(name="", description=""))
        assert reg.match("anything") is None

    def test_single_cjk_char_no_bigram(self):
        tokens = _tokens("测")
        assert tokens == set()

    def test_select_tools_returns_copy(self):
        reg = CapabilityRegistry()
        cap = Capability(tools=["git", "docker"])
        reg.register(cap)
        tools = reg.select_tools(cap)
        tools.append("kubectl")
        assert reg.select_tools(cap) == ["git", "docker"]

    def test_capability_custom_fields(self):
        cap = Capability(
            name="deploy",
            description="deploy to prod",
            inputs=["image"],
            outputs=["url"],
            tools=["docker"],
            cost=1.5,
            risk="high",
            permission="deploy:write",
            success_rate=0.95,
        )
        assert cap.inputs == ["image"]
        assert cap.outputs == ["url"]
        assert cap.permission == "deploy:write"
        assert cap.risk == "high"
        assert cap.cost == 1.5
        assert cap.success_rate == 0.95
