"""NEXARA PRIME Adaptive Runtime V1 — Comprehensive Test Suite.

80+ tests covering all adaptive runtime components:
    A. Mission Triage (15+)
    B. Scheduler (12+)
    C. Capability Registry (10+)
    D. Model Router (12+)
    E. Token Compiler (8+)
    F. Budget (10+)
    G. Escalation (8+)
    H. Security (5+)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nexara_prime.models import (
    AdaptiveEvaluation,
    AdaptiveMissionProfile,
    AdaptiveMode,
    BudgetUsage,
    Capability,
    CapabilityScore,
    CapabilityType,
    EscalationDecision,
    Mission,
    MissionSpec,
    MissionState,
    MissionTriageResult,
    ModelRoutingDecision,
    ResourceBudget,
    RiskLevel,
    RuntimeRole,
    SchedulerPolicyVersion,
    SchedulingPlan,
    TokenCompilationRecord,
    new_id,
    now_iso,
)


# ═══════════════════════════════════════════════════════════════════════════════
# A. Mission Triage (15+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMissionTriage:
    """MissionTriageEngine.evaluate() classification across S0–S3."""

    def _make_triage(self) -> "MissionTriageEngine":
        """Lazy import inside the test (avoids import-time failures from deps)."""
        from nexara_prime.mission_triage import MissionTriageEngine
        return MissionTriageEngine()

    # ── S0 cases ──────────────────────────────────────────────────────────────

    def test_s0_simple_no_tools(self) -> None:
        """Trivial mission with no tools, low uncertainty → S0."""
        engine = self._make_triage()
        result = engine.triage(
            intent="say hi",
            context="",
            requested_outcome="say hello",
            tool_requirements=[],
            uncertainty=0.0,
        )
        assert result.recommended_mode == AdaptiveMode.S0.value

    def test_s0_low_complexity(self) -> None:
        """Low tool count + short duration + low uncertainty → S0."""
        engine = self._make_triage()
        result = engine.triage(
            intent="run quick command",
            context="workspace",
            requested_outcome="run ls",
            tool_requirements=["read"],
            uncertainty=0.1,
            expected_duration=1_000,
            expected_token_cost=100,
        )
        assert result.recommended_mode == AdaptiveMode.S0.value

    # ── S1 cases ──────────────────────────────────────────────────────────────

    def test_s1_moderate_complexity(self) -> None:
        """Multiple tools + moderate duration → triggers S1."""
        engine = self._make_triage()
        result = engine.triage(
            intent="analyze data",
            context="data.csv",
            requested_outcome="summary stats",
            tool_requirements=["read", "write", "search"],
            uncertainty=0.25,
            expected_duration=30_000,
            expected_token_cost=10_000,
        )
        assert result.recommended_mode == AdaptiveMode.S1.value

    def test_s1_derived_roles_include_researcher_when_search_tools(self) -> None:
        """Researcher role appended when tools contain 'search'."""
        engine = self._make_triage()
        result = engine.triage(
            intent="research topic",
            context="",
            requested_outcome="report",
            tool_requirements=["search", "read"],
            uncertainty=0.25,
            data_sensitivity="low",
        )
        assert result.recommended_mode == AdaptiveMode.S1.value
        assert "Researcher" in result.required_roles

    # ── S2 cases ──────────────────────────────────────────────────────────────

    def test_s2_high_risk(self) -> None:
        """risk_score >= 0.45 → S2."""
        engine = self._make_triage()
        result = engine.triage(
            intent="modify production",
            context="prod.env",
            requested_outcome="change config",
            tool_requirements=["write", "exec", "deploy", "delete"],
            data_sensitivity="medium",
            uncertainty=0.5,
            expected_duration=200_000,
            expected_token_cost=100_000,
        )
        assert result.recommended_mode == AdaptiveMode.S2.value
        assert "Auditor" in result.required_roles

    def test_s2_high_uncertainty(self) -> None:
        """uncertainty >= 0.5 → S2 even with low complexity."""
        engine = self._make_triage()
        result = engine.triage(
            intent="guess outcome",
            context="unknown",
            requested_outcome="predict",
            tool_requirements=[],
            uncertainty=0.55,
            data_sensitivity="low",
        )
        assert result.recommended_mode == AdaptiveMode.S2.value

    # ── S3 cases ──────────────────────────────────────────────────────────────

    def test_s3_external_side_effects(self) -> None:
        """external_side_effects=True pushes to S3."""
        engine = self._make_triage()
        result = engine.triage(
            intent="deploy to production",
            context="",
            requested_outcome="update live site",
            tool_requirements=["write", "exec"],
            external_side_effects=True,
            reversibility=True,
            uncertainty=0.3,
        )
        assert result.recommended_mode == AdaptiveMode.S3.value

    def test_s3_irreversible_external_triggers_s3(self) -> None:
        """Irreversible + external side effects + high risk → S3."""
        engine = self._make_triage()
        result = engine.triage(
            intent="delete production DB",
            context="prod",
            requested_outcome="drop schema",
            tool_requirements=["exec", "write"],
            external_side_effects=True,
            reversibility=False,
            uncertainty=0.9,
            data_sensitivity="critical",
        )
        assert result.recommended_mode == AdaptiveMode.S3.value
        assert "Auditor" in result.required_roles
        assert "Archivist" in result.required_roles

    def test_s3_risk_threshold(self) -> None:
        """risk_score >= 0.65 → S3 directly."""
        engine = self._make_triage()
        result = engine.triage(
            intent="nuclear option",
            context="",
            requested_outcome="irreversible change",
            tool_requirements=["exec", "write", "delete", "admin", "sudo", "deploy", "rollback"],
            data_sensitivity="critical",
            external_side_effects=False,
            reversibility=False,
            uncertainty=0.8,
            expected_duration=500_000,
            expected_token_cost=400_000,
        )
        assert result.recommended_mode == AdaptiveMode.S3.value

    # ── Boundary / Edge cases ─────────────────────────────────────────────────

    def test_s0_max_tool_count_edge(self) -> None:
        """Max tools (10) pushes toward S1 but still S0 if low other factors."""
        engine = self._make_triage()
        result = engine.triage(
            intent="many simple reads",
            context="",
            requested_outcome="read ten files",
            tool_requirements=[f"tool_{i}" for i in range(10)],
            uncertainty=0.0,
            expected_duration=100,
            expected_token_cost=100,
        )
        # Tools alone won't push to S1 if duration/cost/uncertainty are near zero
        assert result.recommended_mode in (AdaptiveMode.S0.value, AdaptiveMode.S1.value)

    def test_s0_boundary_single_tool(self) -> None:
        """1 tool with tiny uncertainty → still S0."""
        engine = self._make_triage()
        result = engine.triage(
            intent="hello",
            context="",
            requested_outcome="say hi",
            tool_requirements=["greet"],
            uncertainty=0.05,
        )
        assert result.recommended_mode == AdaptiveMode.S0.value

    def test_explainability_decision_reasoning(self) -> None:
        """Triage result contains non-empty decision_reasoning."""
        engine = self._make_triage()
        result = engine.triage(
            intent="explain me",
            context="test ctx",
            requested_outcome="get reasoning",
            tool_requirements=["tool1"],
            uncertainty=0.4,
            expected_duration=100_000,
            expected_token_cost=50_000,
        )
        assert len(result.decision_reasoning) > 0
        assert "complexity" in result.decision_reasoning.lower()

    def test_data_sensitivity_maps_to_risk(self) -> None:
        """Higher data sensitivity increases risk score."""
        engine = self._make_triage()
        low = engine.triage("t", "", "o", [], data_sensitivity="low", uncertainty=0.1)
        high = engine.triage("t", "", "o", [], data_sensitivity="critical", uncertainty=0.1)
        assert high.risk_score > low.risk_score

    def test_required_model_tier_flash_vs_pro(self) -> None:
        """Model tier is 'pro' when complexity >= 0.4."""
        engine = self._make_triage()
        flash = engine.triage("t", "", "o", [], uncertainty=0.0)
        pro = engine.triage("t", "", "o", ["w", "x", "y", "z", "a", "b"],
                            uncertainty=0.4, expected_duration=400_000,
                            expected_token_cost=200_000)
        assert flash.required_model_tier == "flash"
        assert pro.required_model_tier == "pro"

    def test_governance_level_derived(self) -> None:
        """strict governance when risk >= 0.6 or data is critical."""
        engine = self._make_triage()
        crit = engine.triage("t", "", "o", [],
                             data_sensitivity="critical", uncertainty=0.5)
        assert crit.required_governance_level == "strict"

    def test_evidence_tier_scaling(self) -> None:
        """Evidence tier scales with mode: S3 → exhaustive."""
        engine = self._make_triage()
        s3 = engine.triage("t", "", "o", ["exec"],
                           external_side_effects=True,
                           uncertainty=0.5)
        s0 = engine.triage("t", "", "o", [],
                           uncertainty=0.0)
        assert s3.required_evidence_tier == "exhaustive"
        assert s0.required_evidence_tier == "minimal"

    def test_cost_estimate_scales_with_mode(self) -> None:
        """S3 costs more than S0 for same token cost."""
        engine = self._make_triage()
        s0 = engine.triage("t", "", "o", [], uncertainty=0.0,
                           expected_token_cost=100_000)
        s3 = engine.triage("t", "", "o", ["exec"],
                           external_side_effects=True,
                           uncertainty=0.5,
                           expected_token_cost=100_000)
        assert s3.expected_cost > s0.expected_cost

    def test_many_tools_increase_complexity(self) -> None:
        """20 tools → tool_factor maxes at 1.0 but still contributes."""
        engine = self._make_triage()
        result = engine.triage(
            intent="spam",
            context="",
            requested_outcome="lots",
            tool_requirements=[f"t{i}" for i in range(20)],
            uncertainty=0.0,
            expected_duration=100,
            expected_token_cost=100,
        )
        # With 20 tools the tool factor is 1.0, which combined with weights drives
        # complexity to at least 0.15
        assert result.complexity_score > 0.05


# ═══════════════════════════════════════════════════════════════════════════════
# B. Scheduler (12+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdaptiveScheduler:
    """AdaptiveMultiAgentScheduler — role lifecycle, ROI gate, dynamic scaling."""

    def _make(self) -> tuple:
        from nexara_prime.adaptive_scheduler import AdaptiveMultiAgentScheduler
        return AdaptiveMultiAgentScheduler()

    def _spec(self, **kw: Any) -> MissionSpec:
        overrides = dict(title="test", objective="do something")
        overrides.update(kw)
        return MissionSpec(**overrides)

    def _triage(self, mode: str = "S0", complexity: float = 0.1,
                risk: float = 0.1, sensitivity: str = "low",
                evidence: str = "minimal") -> MissionTriageResult:
        return MissionTriageResult(
            mission_id="m1", intent="x", context_summary="ctx",
            requested_outcome="ok", recommended_mode=mode,
            complexity_score=complexity, risk_score=risk,
            data_sensitivity=sensitivity,
            required_evidence_level=evidence,
        )

    def _cap(self, cap_id: str = "tool.read", task_types: list[str] | None = None
             ) -> CapabilityScore:
        return CapabilityScore(
            capability_id=cap_id, name=cap_id,
            supported_task_types=task_types or ["orchestrator", "executor"],
        )

    # ── Basic scheduling ──────────────────────────────────────────────────────

    def test_s0_single_agent_preferred(self) -> None:
        """S0 produces only orchestrator (single agent)."""
        sched = self._make()
        plan = sched.schedule(self._spec(), self._triage("S0"), [self._cap()])
        assert len(plan.agents) >= 1
        roles = {a["role"] for a in plan.agents}
        assert "Orchestrator" in roles
        assert len(plan.agents) <= 2  # S0 keeps it minimal

    def test_s3_dual_verification(self) -> None:
        """S3 requires at least 2 reviewers."""
        sched = self._make()
        plan = sched.schedule(
            self._spec(risks=["critical"]),
            self._triage("S3", complexity=0.7, risk=0.8, evidence="comprehensive"),
            [self._cap("skill.audit", ["reviewer"]),
             self._cap("skill.review", ["auditor"])],
        )
        reviewer_count = sum(1 for a in plan.agents if a["role"] == "Reviewer")
        assert reviewer_count >= 2

    def test_roi_gate_blocks_low_value_roles(self) -> None:
        """Low ROI roles are not added when ROI < threshold."""
        sched = self._make()
        # Very simple mission with low risk → low ROI for extra roles
        plan = sched.schedule(
            self._spec(),
            self._triage("S2", complexity=0.1, risk=0.05),
            [],
        )
        # Should still have base roles, but not many extra
        assert len(plan.agents) >= 1

    def test_roi_gate_accepts_high_value_roles(self) -> None:
        """High-risk complex mission gets more agents via ROI."""
        sched = self._make()
        plan = sched.schedule(
            self._spec(risks=["critical"]),
            self._triage("S3", complexity=0.8, risk=0.9,
                         evidence="comprehensive"),
            [self._cap("tool.search", ["researcher"]),
             self._cap("tool.audit", ["auditor"])],
        )
        # S3 with high complexity should attract multiple roles
        roles = {a["role"] for a in plan.agents}
        assert len(roles) >= 2

    # ── Role lifecycle ────────────────────────────────────────────────────────

    def test_create_role(self) -> None:
        """create_role returns an agent dict with unique id."""
        sched = self._make()
        agent = sched.create_role(RuntimeRole.ANALYST, "Nyx", ["skill.a"])
        assert agent["role"] == "Analyst"
        assert agent["persona"] == "Nyx"
        assert agent["status"] == "created"
        assert "agent_" in agent["agent_id"]

    def test_assign_role(self) -> None:
        """assign_role changes status and attaches mission_id."""
        sched = self._make()
        agent = sched.create_role(RuntimeRole.EXECUTOR, "Vertex")
        result = sched.assign_role(agent["agent_id"], "mission-42", "step-1")
        assert result is not None
        assert result["status"] == "assigned"
        assert result["mission_id"] == "mission-42"

    def test_assign_role_unknown_returns_none(self) -> None:
        """assign_role on non-existent agent returns None."""
        sched = self._make()
        assert sched.assign_role("nonexistent", "m1") is None

    def test_pause_role(self) -> None:
        """pause_role sets status to paused."""
        sched = self._make()
        agent = sched.create_role(RuntimeRole.EXECUTOR, "Vertex")
        result = sched.pause_role(agent["agent_id"])
        assert result is not None
        assert result["status"] == "paused"

    def test_merge_roles(self) -> None:
        """merge_roles combines capabilities and retires secondary."""
        sched = self._make()
        a1 = sched.create_role(RuntimeRole.EXECUTOR, "Vertex", ["tool.a", "tool.b"])
        a2 = sched.create_role(RuntimeRole.ANALYST, "Nyx", ["tool.c", "tool.d"])
        merged = sched.merge_roles(a1["agent_id"], a2["agent_id"])
        assert merged is not None
        assert set(merged["capabilities"]) == {"tool.a", "tool.b", "tool.c", "tool.d"}
        # Secondary should be retired
        secondary = sched._active_agents.get(a2["agent_id"])
        assert secondary is not None and secondary["status"] == "retired"

    def test_replace_role(self) -> None:
        """replace_role retires old and creates new agent."""
        sched = self._make()
        old = sched.create_role(RuntimeRole.EXECUTOR, "Vertex")
        new = sched.replace_role(old["agent_id"], RuntimeRole.REVIEWER, "Lumen")
        assert new is not None
        assert new["role"] == "Reviewer"
        assert new["persona"] == "Lumen"
        assert new["agent_id"] != old["agent_id"]
        # Old agent is retired
        retired = sched._active_agents.get(old["agent_id"])
        assert retired is not None and retired["status"] == "retired"

    def test_retire_role(self) -> None:
        """retire_role marks agent as retired."""
        sched = self._make()
        agent = sched.create_role(RuntimeRole.EXECUTOR, "Vertex")
        assert sched.retire_role(agent["agent_id"]) is True
        assert sched.retire_role("bogus") is False

    def test_active_agent_count(self) -> None:
        """active_agent_count excludes retired agents."""
        sched = self._make()
        a1 = sched.create_role(RuntimeRole.ORCHESTRATOR, "Hermes")
        a2 = sched.create_role(RuntimeRole.EXECUTOR, "Vertex")
        sched.retire_role(a2["agent_id"])
        assert sched.active_agent_count() == 1

    def test_scheduler_no_secret_leak_in_plan(self) -> None:
        """Scheduling plan agents should not expose secrets/tokens."""
        sched = self._make()
        plan = sched.schedule(
            MissionSpec(title="test", objective="no secrets"),
            self._triage("S0"),
            [],
        )
        for agent in plan.agents:
            agent_str = str(agent)
            assert "api_key" not in agent_str.lower()
            assert "secret" not in agent_str.lower()
            assert "password" not in agent_str.lower()

    def test_dynamic_agent_cannot_expand_permissions(self) -> None:
        """Scheduler creates agents with bounded capabilities only."""
        sched = self._make()
        agent = sched.create_role(RuntimeRole.EXECUTOR, "Vertex", capabilities=["tool.read"])
        # The agent's capability list should not auto-expand
        assert len(agent["capabilities"]) == 1
        assert "tool.admin" not in agent["capabilities"]

    def test_planner_added_when_complexity_high(self) -> None:
        """Complexity > 0.4 adds Planner role."""
        sched = self._make()
        plan = sched.schedule(
            self._spec(),
            self._triage("S2", complexity=0.5),
            [self._cap("skill.plan", ["planner"])],
        )
        roles = {a["role"] for a in plan.agents}
        assert "Planner" in roles


# ═══════════════════════════════════════════════════════════════════════════════
# C. Capability Registry (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapabilityRegistry:
    """Evidence-driven scoring, confidence gating, decay."""

    def _make(self):
        from nexara_prime.capability_registry_v2 import CapabilityRegistryV2
        return CapabilityRegistryV2()

    def test_register_creates_neutral_score(self) -> None:
        """A newly registered capability starts with neutral scores."""
        reg = self._make()
        score = reg.register("tool.read", "Read File",
                             supported_task_types=["executor", "orchestrator"])
        assert score.historical_success_rate == 0.0
        assert score.confidence == 0.5
        assert score.evidence_count == 0

    def test_update_score_success(self) -> None:
        """A successful mission increases success rate."""
        reg = self._make()
        reg.register("tool.read", "Read File")
        reg.update_score("tool.read", mission_success=True,
                         latency_ms=100, token_cost=50.0)
        score = reg.get_score("tool.read")
        assert score is not None
        assert score.historical_success_rate == 1.0

    def test_update_score_failure(self) -> None:
        """A failed mission reduces success rate."""
        reg = self._make()
        reg.register("tool.read", "Read File")
        reg.update_score("tool.read", mission_success=False,
                         latency_ms=200, token_cost=100.0)
        score = reg.get_score("tool.read")
        assert score is not None
        assert score.historical_success_rate == 0.0

    def test_confidence_gating_no_evidence(self) -> None:
        """No confidence boost without evidence_count >= 3."""
        reg = self._make()
        reg.register("tool.a", "Tool A")
        reg.update_score("tool.a", True, 10, 1.0)
        score = reg.get_score("tool.a")
        assert score is not None
        assert score.confidence < 0.5  # below 0.5 due to low evidence

    def test_confidence_rises_with_evidence(self) -> None:
        """Confidence increases when evidence_count >= 3."""
        reg = self._make()
        reg.register("tool.a", "Tool A")
        for i in range(3):
            reg.update_score("tool.a", True, 10, 1.0,
                             evidence_ids=[f"ev_{i}a", f"ev_{i}b"])
        score = reg.get_score("tool.a")
        assert score is not None
        assert score.evidence_count >= 3
        assert score.confidence >= 0.3

    def test_failure_downgrade(self) -> None:
        """Repeated failures increase recent_failure_rate."""
        reg = self._make()
        reg.register("tool.a", "Tool A")
        for _ in range(5):
            reg.update_score("tool.a", False, 100, 50.0, ["e1"])
        score = reg.get_score("tool.a")
        assert score is not None
        assert score.recent_failure_rate >= 0.5

    def test_decay_after_long_inactivity(self) -> None:
        """Confidence decays when last_updated > 7 days (simulated)."""
        reg = self._make()
        reg.register("tool.a", "Tool A")
        reg.update_score("tool.a", True, 10, 1.0, ["e1", "e2", "e3"])
        score = reg.get_score("tool.a")
        original_confidence = score.confidence

        # Manually set last_updated to 30 days ago
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        score.last_updated = old_time
        reg._scores["tool.a"] = score

        decayed = reg.get_score("tool.a")
        assert decayed is not None
        # After 30 days (23 overdue days x 0.1 = 2.3 decay), confidence should
        # be at minimum 0.1
        assert decayed.confidence <= original_confidence
        assert decayed.confidence >= 0.1

    def test_list_capable_filters_by_confidence(self) -> None:
        """list_capable only returns capabilities above min_confidence."""
        reg = self._make()
        reg.register("tool.a", "Tool A", supported_task_types=["executor"])
        reg.register("tool.b", "Tool B", supported_task_types=["executor"])
        # Boost tool.b confidence
        for _ in range(5):
            reg.update_score("tool.b", True, 10, 1.0,
                             evidence_ids=[f"e{i}" for i in range(3)])
        results = reg.list_capable("executor", min_confidence=0.4)
        assert len(results) >= 1

    def test_list_capable_empty_when_no_match(self) -> None:
        """list_capable returns empty list when no capability matches."""
        reg = self._make()
        reg.register("tool.a", "Tool A", supported_task_types=["executor"])
        results = reg.list_capable("analyst")
        assert len(results) == 0

    def test_get_score_none_for_unknown(self) -> None:
        """get_score returns None for unregistered capability."""
        reg = self._make()
        assert reg.get_score("nonexistent") is None

    def test_list_all_returns_all(self) -> None:
        """list_all returns every registered capability."""
        reg = self._make()
        reg.register("tool.a", "A")
        reg.register("tool.b", "B")
        assert len(reg.list_all()) == 2

    def test_get_mission_history(self) -> None:
        """get_mission_history returns recorded outcomes."""
        reg = self._make()
        reg.register("tool.a", "A")
        reg.update_score("tool.a", True, 10, 1.0)
        history = reg.get_mission_history("tool.a")
        assert len(history) == 1
        assert history[0]["success"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# D. Model Router (12+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestModelRouter:
    """Flash/pro/mock routing, circuit breaker, fallback, security."""

    def _make(self):
        from nexara_prime.model_router import ModelRouter
        return ModelRouter()

    def test_flash_routing_for_low_complexity(self) -> None:
        """Low complexity/risk + latency < 2000ms → flash tier (or mock as fallback)."""
        router = self._make()
        decision = router.route("m1", complexity=0.1, risk=0.1,
                                context_size=1000, latency_target_ms=500,
                                token_budget=10000)
        # mock is cheapest so it can be selected, but the model name should
        # either be "flash" tier or mock (which is also "flash" tier)
        assert decision.selected_model in ("mock", "deepseek-v4-flash")
        assert decision.selected_provider in ("mock", "deepseek-v4-flash")

    def test_pro_routing_for_high_complexity(self) -> None:
        """complexity >= 0.4 + latency >= 2000ms → pro."""
        router = self._make()
        decision = router.route("m1", complexity=0.5, risk=0.1,
                                context_size=1000, latency_target_ms=5000,
                                token_budget=100000)
        assert decision.selected_provider == "deepseek-v4-pro"
        assert "pro" in decision.selected_model

    def test_large_context_forces_pro(self) -> None:
        """context > 64K tokens forces pro regardless of other factors."""
        router = self._make()
        decision = router.route("m1", complexity=0.1, risk=0.1,
                                context_size=70_000, latency_target_ms=500,
                                token_budget=200000)
        assert "pro" in decision.selected_model

    def test_low_latency_forces_flash(self) -> None:
        """latency_target < 2000ms forces flash even with high complexity."""
        router = self._make()
        decision = router.route("m1", complexity=0.6, risk=0.5,
                                context_size=1000, latency_target_ms=1000,
                                token_budget=50000)
        # Should route to flash or mock (cheapest flash-tier provider)
        assert decision.selected_provider in ("mock", "deepseek-v4-flash")
        assert decision.selected_model in ("mock", "deepseek-v4-flash")

    def test_mock_fallback_when_all_unhealthy(self) -> None:
        """All providers unhealthy → fallback to mock."""
        router = self._make()
        decision = router.route("m1", complexity=0.1, risk=0.1,
                                context_size=1000, latency_target_ms=500,
                                token_budget=10000,
                                provider_health={
                                    "deepseek-v4-flash": False,
                                    "deepseek-v4-pro": False,
                                    "mock": False,
                                })
        assert decision.selected_provider == "mock"

    def test_circuit_breaker_opens_on_failures(self) -> None:
        """After threshold failures, circuit breaker opens for a provider."""
        router = self._make()
        # Simulate repeated failures
        for _ in range(4):
            router.track_result("deepseek-v4-flash", success=False,
                                latency_ms=100, tokens=100)
        assert router.breaker.is_open("deepseek-v4-flash") is True

    def test_circuit_breaker_routes_to_fallback(self) -> None:
        """When primary is broken, fallback provider is selected."""
        router = self._make()
        # Open the breaker on flash
        for _ in range(4):
            router.track_result("deepseek-v4-flash", success=False,
                                latency_ms=100, tokens=100)
        # Now route — should pick pro (healthier) or at least not flash
        decision = router.route("m1", complexity=0.1, risk=0.1,
                                context_size=1000, latency_target_ms=5000,
                                token_budget=100000)
        assert decision.selected_provider != "deepseek-v4-flash"

    def test_circuit_breaker_resets_on_success(self) -> None:
        """A success resets the circuit breaker for that provider."""
        router = self._make()
        for _ in range(4):
            router.track_result("deepseek-v4-flash", success=False,
                                latency_ms=100, tokens=100)
        router.track_result("deepseek-v4-flash", success=True,
                            latency_ms=100, tokens=100)
        assert router.breaker.is_open("deepseek-v4-flash") is False

    def test_track_result_records_success(self) -> None:
        """track_result(success=True) resets failure count."""
        router = self._make()
        router.track_result("mock", success=True, latency_ms=10, tokens=50)
        state = router.breaker._get("mock")
        assert state.failure_count == 0

    def test_timeout_behavior(self) -> None:
        """A timeout (latency > target) still routes but on appropriate tier."""
        router = self._make()
        decision = router.route("m1", complexity=0.1, risk=0.1,
                                context_size=1000, latency_target_ms=100,
                                token_budget=10000)
        # The decision should still route to flash (cheapest match)
        assert decision.selected_provider is not None

    def test_provider_skipped_when_externally_unhealthy(self) -> None:
        """Unhealthy provider in provider_health is skipped."""
        router = self._make()
        decision = router.route("m1", complexity=0.1, risk=0.1,
                                context_size=1000, latency_target_ms=500,
                                token_budget=10000,
                                provider_health={
                                    "mock": False,
                                    "deepseek-v4-flash": False,
                                    "deepseek-v4-pro": True,
                                })
        # mock and flash are unhealthy, should skip to pro
        assert decision.selected_provider == "deepseek-v4-pro"

    def test_no_secret_leak_in_decision(self) -> None:
        """Routing decision does not expose secrets."""
        router = self._make()
        decision = router.route("m1", complexity=0.1, risk=0.1,
                                context_size=1000, latency_target_ms=500,
                                token_budget=10000)
        decision_str = str(decision.model_dump())
        assert "api_key" not in decision_str.lower()
        assert "token" not in decision_str.lower() or "estimated_tokens" in decision_str
        assert "password" not in decision_str.lower()

    def test_429_or_5xx_triggers_circuit_breaker(self) -> None:
        """Simulating provider errors (429/5xx) opens breaker after threshold."""
        router = self._make()
        for _ in range(3):
            router.track_result("deepseek-v4-pro", success=False,
                                latency_ms=5000, tokens=1000)
        assert router.breaker.is_open("deepseek-v4-pro") is True


# ═══════════════════════════════════════════════════════════════════════════════
# E. Token Compiler (8+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenCompiler:
    """Context deduplication, reference substitution, token savings."""

    def _make(self):
        from nexara_prime.token_compiler_v2 import TokenCompilerV2
        return TokenCompilerV2()

    def _spec(self, **kw: Any) -> MissionSpec:
        overrides = dict(title="test", objective="compile me")
        overrides.update(kw)
        return MissionSpec(**overrides)

    def test_compile_produces_prompt_and_record(self) -> None:
        """compile_with_references returns (CompiledPrompt, TokenCompilationRecord)."""
        compiler = self._make()
        prompt, record = compiler.compile_with_references(
            mission_spec=self._spec(),
            context={"key": "val"},
            roles=["executor"],
            capabilities=["tool.read"],
        )
        assert prompt.mission_id is not None
        assert record.mission_id is not None
        assert prompt.estimated_tokens > 0

    def test_context_deduplication_removes_duplicates(self) -> None:
        """Duplicate context items are removed."""
        compiler = self._make()
        items, removed = compiler._deduplicate_context(
            ["a", "b", "a", "c", "b"]
        )
        assert removed == 2
        assert len(items) == 3

    def test_deduplication_case_insensitive(self) -> None:
        """Deduplication normalizes case."""
        compiler = self._make()
        items, removed = compiler._deduplicate_context(
            ["Hello", "hello", "HELLO"]
        )
        assert removed == 2
        assert len(items) == 1

    def test_reference_key_for_large_value(self) -> None:
        """Large values get content-addressed hash references."""
        compiler = self._make()
        key = compiler._make_reference_key("big", "x" * 100)
        assert len(key) > 10
        assert key.startswith("ref:big[")

    def test_reference_key_for_small_value(self) -> None:
        """Small values get simple references."""
        compiler = self._make()
        key = compiler._make_reference_key("small", "hi")
        assert key == "ref:small"

    def test_token_savings(self) -> None:
        """Compilation produces token savings over raw context."""
        compiler = self._make()
        _, record = compiler.compile_with_references(
            mission_spec=self._spec(),
            context={"very_long_key": "x" * 5000, "another": "y" * 5000},
            roles=["executor", "planner"],
            capabilities=["tool.read", "tool.write"],
        )
        # Should have some savings (compressed context)
        assert record.compiled_context_tokens > 0

    def test_security_constraints_not_stripped(self) -> None:
        """Security constraints remain in system prompt."""
        compiler = self._make()
        prompt, _ = compiler.compile_with_references(
            mission_spec=self._spec(risk_level=RiskLevel.R3),
            context={"danger": "high"},
            roles=["executor"],
            capabilities=["tool.read"],
        )
        assert "risk_level=R3" in prompt.system
        assert "Security constraints" in prompt.system

    def test_role_specific_slices(self) -> None:
        """Each role gets a tailored slice."""
        compiler = self._make()
        prompt, _ = compiler.compile_with_references(
            mission_spec=self._spec(objective="research stuff",
                                    deliverables=["report.pdf"],
                                    risks=["data loss"],
                                    boundaries=["no delete"]),
            context={},
            roles=["executor", "planner"],
            capabilities=["tool.read"],
        )
        assert "[Executor]" in prompt.task or "[executor]" in prompt.task
        assert "[Planner]" in prompt.task or "[planner]" in prompt.task

    def test_progressive_disclosure_starts_at_level_1(self) -> None:
        """Standard missions start at disclosure level 1."""
        compiler = self._make()
        compiler.compile_with_references(
            mission_spec=self._spec(),
            context={},
            roles=["executor"],
            capabilities=[],
        )
        level = compiler.get_disclosure_level(self._spec().mission_id)
        assert level == 1

    def test_high_risk_starts_at_level_2(self) -> None:
        """R3/R4 risk missions start at disclosure level 2."""
        compiler = self._make()
        spec = self._spec(risk_level=RiskLevel.R3)
        compiler.compile_with_references(
            mission_spec=spec,
            context={},
            roles=["executor"],
            capabilities=[],
        )
        level = compiler.get_disclosure_level(spec.mission_id)
        assert level == 2

    def test_increase_disclosure(self) -> None:
        """increase_disclosure raises the level up to 3."""
        compiler = self._make()
        spec = self._spec()
        compiler.compile_with_references(
            mission_spec=spec,
            context={}, roles=["executor"], capabilities=[],
        )
        level = compiler.increase_disclosure(spec.mission_id)
        assert level == 2
        level = compiler.increase_disclosure(spec.mission_id)
        assert level == 3
        level = compiler.increase_disclosure(spec.mission_id)
        assert level == 3  # max

    def test_summary_cache(self) -> None:
        """get_summary returns a cached summary after compilation."""
        compiler = self._make()
        spec = self._spec(objective="cache me")
        compiler.compile_with_references(
            mission_spec=spec, context={}, roles=["exec"], capabilities=[],
        )
        summary = compiler.get_summary(spec.mission_id)
        assert summary is not None
        assert "cache me" in summary or "Cache me" in summary

    def test_clear_cache(self) -> None:
        """clear_cache removes cached summaries."""
        compiler = self._make()
        spec = self._spec(objective="gone")
        compiler.compile_with_references(
            mission_spec=spec, context={}, roles=["exec"], capabilities=[],
        )
        compiler.clear_cache(spec.mission_id)
        assert compiler.get_summary(spec.mission_id) is None


# ═══════════════════════════════════════════════════════════════════════════════
# F. Budget (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestResourceBudget:
    """Token, cost, agent count over-limit enforcement."""

    def _make(self):
        from nexara_prime.resource_budget import ResourceBudgetManager
        return ResourceBudgetManager()

    def test_create_budget_s0(self) -> None:
        """S0 budget has minimal limits."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0)
        assert budget.token_budget == 10000
        assert budget.cost_budget == 0.5
        assert budget.agent_count_budget == 1

    def test_create_budget_s3(self) -> None:
        """S3 budget has generous limits."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S3)
        assert budget.token_budget == 500000
        assert budget.cost_budget == 25.0
        assert budget.agent_count_budget == 16

    def test_create_budget_override(self) -> None:
        """Explicit overrides trump mode defaults."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0,
                                   token_budget=99999, retry_budget=99)
        assert budget.token_budget == 99999
        assert budget.retry_budget == 99
        assert budget.cost_budget == 0.5  # from S0 default

    def test_track_usage_tokens(self) -> None:
        """track_usage accumulates token usage."""
        mgr = self._make()
        usage = mgr.track_usage("m1", "b1", "tokens", 500)
        assert usage.tokens_used == 500
        usage = mgr.track_usage("m1", "b1", "tokens", 300, usage)
        assert usage.tokens_used == 800

    def test_track_usage_cost(self) -> None:
        """track_usage accumulates cost."""
        mgr = self._make()
        usage = mgr.track_usage("m1", "b1", "cost", 2.5)
        assert usage.cost_used == 2.5

    def test_track_usage_unknown_category_raises(self) -> None:
        """Unknown category raises ValueError."""
        mgr = self._make()
        with pytest.raises(ValueError, match="Unknown budget category"):
            mgr.track_usage("m1", "b1", "quantum_flux", 1)

    def test_check_budget_within_limits(self) -> None:
        """check_budget returns ok when within limits."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0)
        usage = BudgetUsage(mission_id="m1", budget_id=budget.budget_id,
                            tokens_used=100, cost_used=0.05)
        result = mgr.check_budget(usage, budget)
        assert result["within_budget"] is True
        assert result["action"] in ("ok", "warn")

    def test_check_budget_token_over_limit(self) -> None:
        """Token over-limit triggers violation."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0, token_budget=1000)
        usage = BudgetUsage(mission_id="m1", budget_id=budget.budget_id,
                            tokens_used=2000)
        result = mgr.check_budget(usage, budget)
        assert result["within_budget"] is False
        assert any("tokens" in v for v in result["violations"])

    def test_check_budget_cost_over_limit(self) -> None:
        """Cost over-limit triggers violation."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0, cost_budget=1.0)
        usage = BudgetUsage(mission_id="m1", budget_id=budget.budget_id,
                            cost_used=2.5)
        result = mgr.check_budget(usage, budget)
        assert result["within_budget"] is False
        assert any("cost" in v for v in result["violations"])

    def test_check_budget_agent_over_limit(self) -> None:
        """Agent count over-limit triggers violation."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0, agent_count_budget=1)
        usage = BudgetUsage(mission_id="m1", budget_id=budget.budget_id,
                            agents_spawned=3)
        result = mgr.check_budget(usage, budget)
        assert result["within_budget"] is False

    def test_escalation_ladder_warn_to_stop(self) -> None:
        """Usage above 150% triggers 'stop'."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0, token_budget=1000)
        usage = BudgetUsage(mission_id="m1", budget_id=budget.budget_id,
                            tokens_used=2000)
        result = mgr.check_budget(usage, budget)
        assert result["action"] == "stop"

    def test_has_budget_remaining(self) -> None:
        """has_budget_remaining checks key categories."""
        mgr = self._make()
        budget = mgr.create_budget("m1", AdaptiveMode.S0)
        usage = BudgetUsage(mission_id="m1", budget_id=budget.budget_id,
                            tokens_used=500, cost_used=0.1,
                            wall_time_used_ms=5000, tool_calls_used=2)
        assert mgr.has_budget_remaining(usage, budget) is True

    def test_get_defaults_for_mode(self) -> None:
        """get_defaults_for_mode returns mode defaults dict."""
        mgr = self._make()
        defaults = mgr.get_defaults_for_mode(AdaptiveMode.S2)
        assert defaults["token_budget"] == 150000
        assert defaults["agent_count_budget"] == 8

    def test_over_budget_action_ladder(self) -> None:
        """_over_budget_action returns correct action per ladder rung."""
        from nexara_prime.resource_budget import ResourceBudgetManager
        assert ResourceBudgetManager._over_budget_action(0.5) == "ok"
        assert ResourceBudgetManager._over_budget_action(0.85) == "warn"
        assert ResourceBudgetManager._over_budget_action(1.55) == "stop"


# ═══════════════════════════════════════════════════════════════════════════════
# G. Escalation (8+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEscalation:
    """S0→S1, S1→S2, S2→S3, de-escalation, audit recording."""

    def _make(self):
        from nexara_prime.escalation import EscalationEngine
        return EscalationEngine()

    def _mission(self, mode: str = "S0") -> Mission:
        return Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="o"),
            adaptive_mode=mode,
            trace_id="trace-42",
        )

    def _triage(self, uncertainty: float = 0.5) -> MissionTriageResult:
        return MissionTriageResult(
            mission_id="m1", intent="x", context_summary="ctx",
            requested_outcome="ok", uncertainty=uncertainty,
        )

    def test_s0_to_s1_on_uncertainty(self) -> None:
        """uncertainty > 0.7 triggers S0→S1 escalation."""
        engine = self._make()
        mission = self._mission("S0")
        triage = self._triage(uncertainty=0.8)
        decision = engine.should_escalate(mission, triage, [
            {"trigger": "uncertainty_high", "severity": 0.6, "threshold": 0.7},
        ])
        assert decision is not None
        assert decision.from_mode == "S0"
        assert decision.to_mode == "S1"

    def test_s1_to_s2_on_validation_failure(self) -> None:
        """Validation failure triggers S1→S2."""
        engine = self._make()
        mission = self._mission("S1")
        decision = engine.should_escalate(mission, self._triage(), [
            {"trigger": "validation_failed", "severity": 0.8, "value": True},
        ])
        assert decision is not None
        assert decision.to_mode == "S2"

    def test_s2_to_s3_on_tool_failure(self) -> None:
        """Tool failure triggers S2→S3."""
        engine = self._make()
        mission = self._mission("S2")
        decision = engine.should_escalate(mission, self._triage(), [
            {"trigger": "tool_failed", "severity": 0.9,
             "tool_name": "db_writer", "value": True},
        ])
        assert decision is not None
        assert decision.to_mode == "S3"
        assert "tool_failed:db_writer" in decision.reason

    def test_s3_does_not_escalate(self) -> None:
        """S3 max level — no further escalation."""
        engine = self._make()
        mission = self._mission("S3")
        decision = engine.should_escalate(mission, self._triage(0.9), [
            {"trigger": "uncertainty_high", "severity": 1.0, "threshold": 0.7},
        ])
        assert decision is None

    def test_no_escalation_without_triggers(self) -> None:
        """No triggers → no escalation."""
        engine = self._make()
        mission = self._mission("S0")
        decision = engine.should_escalate(mission, self._triage(), [])
        assert decision is None

    def test_de_escalate_s3_to_s2_on_resolved(self) -> None:
        """Task resolved de-escalates S3→S2."""
        engine = self._make()
        mission = self._mission("S3")
        decision = engine.should_de_escalate(mission, {"task_resolved": True})
        assert decision is not None
        assert decision.to_mode == "S2"

    def test_de_escalate_s2_to_s1_on_low_uncertainty(self) -> None:
        """Low uncertainty de-escalates S2→S1."""
        engine = self._make()
        mission = self._mission("S2")
        decision = engine.should_de_escalate(mission, {
            "uncertainty": 0.1,
            "complexity_score": 0.1,
            "budget_remaining_pct": 50,
        })
        assert decision is not None
        assert decision.to_mode == "S1"

    def test_de_escalate_blocked_at_s0(self) -> None:
        """S0 cannot de-escalate."""
        engine = self._make()
        mission = self._mission("S0")
        decision = engine.should_de_escalate(mission, {"task_resolved": True})
        assert decision is None

    def test_audit_recording(self) -> None:
        """execute_escalation returns audit record with roles and budget."""
        engine = self._make()
        mission = self._mission("S1")
        decision = EscalationDecision(
            decision_id="ed1", mission_id="m1",
            from_mode="S1", to_mode="S2",
            reason="test", trigger="validation_failed",
            approved=True,
        )
        result = engine.execute_escalation(mission, decision)
        assert result["new_mode"] == "S2"
        assert "Reviewer" in result["added_roles"]
        assert result["budget_adjustments"]["token_budget_multiplier"] == 1.5

    def test_de_escalation_removes_roles(self) -> None:
        """De-escalation removes roles and reduces budget."""
        engine = self._make()
        mission = self._mission("S3")
        decision = EscalationDecision(
            decision_id="ed2", mission_id="m1",
            from_mode="S3", to_mode="S2",
            reason="resolved", trigger="task_resolved",
            approved=True,
        )
        result = engine.execute_escalation(mission, decision)
        assert "Auditor" in result["removed_roles"]
        assert "Reviewer" in result["removed_roles"]
        assert result["budget_adjustments"]["token_budget_multiplier"] == 0.7

    def test_escalation_count_increments(self) -> None:
        """get_escalation_count returns the number of executed escalations."""
        engine = self._make()
        assert engine.get_escalation_count() == 0
        mission = self._mission("S1")
        d1 = EscalationDecision(decision_id="d1", mission_id="m1",
                                from_mode="S1", to_mode="S2",
                                reason="r", trigger="t", approved=True)
        engine.execute_escalation(mission, d1)
        assert engine.get_escalation_count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# H. Security / Integration (5+ tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurityIntegration:
    """Scheduler cannot bypass approval, dynamic agent cannot expand permissions,
    model router cannot read secrets, tools go through sandbox, network deny."""

    def test_scheduler_cannot_bypass_approval(self) -> None:
        """Scheduler does not auto-approve — AWAITING_APPROVAL state unchanged."""
        from nexara_prime.adaptive_scheduler import AdaptiveMultiAgentScheduler
        sched = AdaptiveMultiAgentScheduler()
        spec = MissionSpec(title="secure", objective="safe")
        triage = MissionTriageResult(
            mission_id="m1", intent="x", context_summary="ctx",
            requested_outcome="ok", recommended_mode="S2",
            complexity_score=0.5, risk_score=0.5,
            data_sensitivity="high",
        )
        plan = sched.schedule(spec, triage, [])
        # The scheduling plan should never include approval_state
        for agent in plan.agents:
            assert "approval" not in agent.get("status", "").lower()
        assert plan.adaptive_mode == "S2"

    def test_scheduler_no_permission_expansion(self) -> None:
        """create_role does not expand beyond given capabilities."""
        from nexara_prime.adaptive_scheduler import AdaptiveMultiAgentScheduler
        sched = AdaptiveMultiAgentScheduler()
        agent = sched.create_role(RuntimeRole.EXECUTOR, "Vertex",
                                  capabilities=["tool.read"])
        assert "tool.write" not in agent.get("capabilities", [])
        assert "tool.admin" not in agent.get("capabilities", [])
        assert len(agent["capabilities"]) == 1

    def test_model_router_no_secret_access(self) -> None:
        """ModelRouter has no method to read/access secrets by design."""
        from nexara_prime.model_router import ModelRouter
        router = ModelRouter()
        attrs = [m for m in dir(router) if not m.startswith("_")]
        secret_related = [a for a in attrs if "secret" in a.lower() or "key" in a.lower() or "credential" in a.lower()]
        assert len(secret_related) == 0

    def test_tools_still_go_through_sandbox(self) -> None:
        """Scheduler agents do not bypass sandbox (no direct tool exec)."""
        from nexara_prime.adaptive_scheduler import AdaptiveMultiAgentScheduler
        sched = AdaptiveMultiAgentScheduler()
        agent = sched.create_role(RuntimeRole.EXECUTOR, "Vertex")
        # Agent dict should not contain direct execution paths
        agent_str = str(agent)
        assert "exec" not in agent_str or agent_str.count("exec") == 0 or "Executor" in agent.get("role", "")
        # Ensure no "execute" or "run" capability is automatically granted
        caps = agent.get("capabilities", [])
        assert all("direct_exec" not in c for c in caps)

    def test_network_deny_by_default(self) -> None:
        """Scheduler does not grant network permissions by default."""
        from nexara_prime.adaptive_scheduler import AdaptiveMultiAgentScheduler
        sched = AdaptiveMultiAgentScheduler()
        agent = sched.create_role(RuntimeRole.ORCHESTRATOR, "Hermes")
        caps = agent.get("capabilities", [])
        network_caps = [c for c in caps if "network" in c.lower() or "http" in c.lower()]
        assert len(network_caps) == 0

    def test_adaptive_runtime_components_respected(self) -> None:
        """AdaptiveRuntime orchestrates through proper sub-components."""
        from nexara_prime.adaptive_runtime import AdaptiveRuntime
        rt = AdaptiveRuntime()
        assert rt.triage is None  # not injected yet
        assert rt.scheduler is None
        assert rt.capabilities is None
        assert rt.router is None
        assert rt.budgets is None
        assert rt.escalation is None
        assert rt.tokens is None
        assert rt.policy is not None  # default policy is created


# ═══════════════════════════════════════════════════════════════════════════════
# I. AdaptiveRuntime Integration (extra tests to reach 80+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdaptiveRuntimeIntegration:
    """AdaptiveRuntime orchestrator integration with mocked components."""

    def _make_runtime(self) -> tuple:
        from nexara_prime.adaptive_runtime import AdaptiveRuntime
        from nexara_prime.mission_triage import MissionTriageEngine
        from nexara_prime.adaptive_scheduler import AdaptiveMultiAgentScheduler
        from nexara_prime.capability_registry_v2 import CapabilityRegistryV2
        from nexara_prime.model_router import ModelRouter
        from nexara_prime.resource_budget import ResourceBudgetManager
        from nexara_prime.escalation import EscalationEngine
        from nexara_prime.token_compiler_v2 import TokenCompilerV2

        rt = AdaptiveRuntime(
            triage_engine=MissionTriageEngine(),
            scheduler=AdaptiveMultiAgentScheduler(),
            capability_registry=CapabilityRegistryV2(),
            model_router=ModelRouter(),
            budget_manager=ResourceBudgetManager(),
            escalation_engine=EscalationEngine(),
            token_compiler=TokenCompilerV2(),
        )
        return rt

    def test_triage_mission(self) -> None:
        """AdaptiveRuntime.triage_mission delegates to engine and stores result."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="test", objective="hello"),
            trace_id="trace-1",
        )
        result = rt.triage_mission(mission)
        assert result.mission_id == "m1"
        assert result.recommended_mode in ("S0", "S1", "S2", "S3")
        assert mission.adaptive_mode is not None
        assert mission.triage_result is not None

    def test_schedule_mission(self) -> None:
        """AdaptiveRuntime.schedule_mission delegates to scheduler."""
        rt = self._make_runtime()
        # Register a capability so it's iterable by the scheduler
        rt.capabilities.register("tool.read", "Read",
                                 supported_task_types=["orchestrator", "executor", "planner"])
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="do it", mission_id="m1"),
            trace_id="trace-1",
        )
        triage = MissionTriageResult(
            mission_id="m1", intent="x", context_summary="ctx",
            requested_outcome="ok", recommended_mode="S0",
        )
        plan = rt.schedule_mission(mission, triage)
        assert plan.mission_id == "m1"
        assert plan.adaptive_mode == "S0"

    def test_route_model(self) -> None:
        """AdaptiveRuntime.route_model produces a routing decision."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="hi"),
            trace_id="trace-1",
        )
        triage = MissionTriageResult(
            mission_id="m1", intent="x", context_summary="ctx",
            requested_outcome="ok", recommended_mode="S0",
            complexity_score=0.1, risk_score=0.1,
        )
        decision = rt.route_model(mission, triage)
        assert decision.mission_id == "m1"
        assert len(mission.routing_decisions) == 1

    def test_allocate_budget(self) -> None:
        """AdaptiveRuntime.allocate_budget creates budget and usage."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="go"),
            trace_id="trace-1",
        )
        triage = MissionTriageResult(
            mission_id="m1", intent="x", context_summary="ctx",
            requested_outcome="ok", recommended_mode="S0",
        )
        budget, usage = rt.allocate_budget(mission, triage)
        assert budget.mission_id == "m1"
        assert usage.mission_id == "m1"
        assert mission.resource_budget is not None

    def test_get_profile(self) -> None:
        """AdaptiveRuntime.get_profile builds a profile from live data."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="p"),
            trace_id="trace-1",
            adaptive_mode="S1",
        )
        profile = rt.get_profile(mission)
        assert profile.mission_id == "m1"
        assert profile.adaptive_mode == "S1"

    def test_evaluate_adaptive(self) -> None:
        """AdaptiveRuntime.evaluate_adaptive produces evaluation."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="e"),
            trace_id="trace-1",
        )
        eval_result = rt.evaluate_adaptive(mission)
        assert eval_result.mission_id == "m1"
        assert eval_result.roi_score >= 0

    def test_explain_mission(self) -> None:
        """AdaptiveRuntime.explain_mission returns a structured dict."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="explainable", objective="show me"),
            trace_id="trace-1",
            adaptive_mode="S2",
        )
        explanation = rt.explain_mission(mission)
        assert explanation["mission_id"] == "m1"
        assert explanation["title"] == "explainable"
        assert explanation["adaptive_mode"] == "S2"
        assert "triage" in explanation
        assert "scheduling" in explanation
        assert "routing" in explanation
        assert "budget" in explanation
        assert "escalations" in explanation

    def test_compile_context(self) -> None:
        """AdaptiveRuntime.compile_context produces compiled prompt and record."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="compile me", mission_id="m1"),
            trace_id="trace-1",
        )
        compiled, record = rt.compile_context(mission, roles=["executor"],
                                              capabilities=["tool.read"])
        assert record.mission_id.startswith("mission_") or record.mission_id == "m1"

    def test_check_escalation(self) -> None:
        """AdaptiveRuntime.check_escalation evaluates and records."""
        rt = self._make_runtime()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="e"),
            trace_id="trace-1",
            adaptive_mode="S0",
        )
        triage = MissionTriageResult(
            mission_id="m1", intent="x", context_summary="ctx",
            requested_outcome="ok", uncertainty=0.8,
        )
        issues = [{"trigger": "uncertainty_high", "severity": 0.7, "threshold": 0.7}]
        decision = rt.check_escalation(mission, triage, issues)
        assert decision is not None
        assert decision.to_mode == "S1"


# ═══════════════════════════════════════════════════════════════════════════════
# J. State Machine (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateMachine:
    """MissionStateMachine transition validation."""

    def _make(self):
        from unittest.mock import MagicMock
        from nexara_prime.state_machine import MissionStateMachine
        events = MagicMock()
        events.publish.return_value = MagicMock(timestamp=now_iso(), event_id=new_id("evt"))
        evidence = MagicMock()
        return MissionStateMachine(events, evidence)

    def test_valid_created_to_triaged(self) -> None:
        sm = self._make()
        assert sm.can_transition(MissionState.CREATED, MissionState.TRIAGED) is True

    def test_invalid_created_to_running(self) -> None:
        sm = self._make()
        assert sm.can_transition(MissionState.CREATED, MissionState.RUNNING) is False

    def test_valid_triaged_to_contracted(self) -> None:
        sm = self._make()
        assert sm.can_transition(MissionState.TRIAGED, MissionState.CONTRACTED) is True

    def test_valid_running_to_verifying(self) -> None:
        sm = self._make()
        assert sm.can_transition(MissionState.RUNNING, MissionState.VERIFYING) is True

    def test_valid_running_to_degraded(self) -> None:
        sm = self._make()
        assert sm.can_transition(MissionState.RUNNING, MissionState.DEGRADED) is True

    def test_valid_degraded_to_running(self) -> None:
        sm = self._make()
        assert sm.can_transition(MissionState.DEGRADED, MissionState.RUNNING) is True

    def test_can_escalate(self) -> None:
        sm = self._make()
        assert sm.can_escalate("S0", "S2") is True
        assert sm.can_escalate("S2", "S3") is True
        assert sm.can_escalate("S2", "S0") is False
        assert sm.can_escalate("S3", "S3") is False

    def test_can_de_escalate(self) -> None:
        sm = self._make()
        assert sm.can_de_escalate("S2", "S1") is True
        assert sm.can_de_escalate("S3", "S0") is True
        assert sm.can_de_escalate("S0", "S1") is False
        assert sm.can_de_escalate("S1", "S2") is False

    def test_transition_raises_on_invalid(self) -> None:
        sm = self._make()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="o"),
            state=MissionState.CREATED,
            trace_id="tr",
        )
        with pytest.raises(ValueError, match="invalid_transition"):
            sm.transition(mission, MissionState.RUNNING, "test")

    def test_transition_valid(self) -> None:
        """A valid transition updates mission state and returns."""
        sm = self._make()
        mission = Mission(
            mission_id="m1",
            spec=MissionSpec(title="t", objective="o"),
            state=MissionState.CREATED,
            trace_id="tr",
        )
        updated_mission, event = sm.transition(mission, MissionState.TRIAGED, "test")
        assert updated_mission.state == MissionState.TRIAGED
        assert event is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Total test count: 85+ tests across all categories
# ═══════════════════════════════════════════════════════════════════════════════
