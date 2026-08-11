"""Tests: DecisionEngine — governed decision-making for Chief Brain Kernel.

Covers:
  - All 5 action classifications (execute, escalate, reject, delegate)
  - Risk-tier model routing (flash vs pro)
  - DecisionOutput structure integrity
  - Boundary conditions (empty capabilities, zero budget, edge risk levels)
"""
from __future__ import annotations

import pytest

from src.nexara_prime.brain.decision_engine import DecisionEngine, DecisionOutput


class TestDecisionEngineEvaluate:
    """Core evaluate() method — action classification, model selection, output shape."""

    # ── Fixtures ────────────────────────────────────────────────────────

    @pytest.fixture
    def engine(self):
        return DecisionEngine()

    @pytest.fixture
    def base_context(self):
        return {"source": "test", "timestamp": "2026-08-07T00:00:00Z"}

    # ── Action Classification ───────────────────────────────────────────

    def test_low_risk_single_cap_returns_execute(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m1",
            objective="write a test",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=1.0,
        )
        assert output.action == "execute"
        assert output.selected_model == "deepseek-v4-flash"

    def test_r3_returns_escalate(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m2",
            objective="delete production database",
            risk_level="R3",
            context=base_context,
            available_capabilities=["tool.file_write"],
            budget_remaining=50.0,
        )
        assert output.action == "escalate"

    def test_r4_returns_escalate(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m3",
            objective="destroy all evidence",
            risk_level="R4",
            context=base_context,
            available_capabilities=["tool.file_write"],
            budget_remaining=100.0,
        )
        assert output.action == "escalate"

    def test_zero_budget_returns_escalate(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m4",
            objective="write a file",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=0.0,
        )
        assert output.action == "escalate"

    def test_negative_budget_returns_escalate(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m5",
            objective="write a file",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=-5.0,
        )
        assert output.action == "escalate"

    def test_no_capabilities_returns_reject(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m6",
            objective="do something impossible",
            risk_level="R1",
            context=base_context,
            available_capabilities=[],
            budget_remaining=100.0,
        )
        assert output.action == "reject"

    def test_r2_with_write_cap_returns_execute(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m7",
            objective="modify a file",
            risk_level="R2",
            context=base_context,
            available_capabilities=["tool.file_write_report"],
            budget_remaining=10.0,
        )
        assert output.action == "execute"

    def test_r2_without_write_cap_returns_delegate(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m8",
            objective="modify a file",
            risk_level="R2",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=10.0,
        )
        assert output.action == "delegate"

    # ── Action Priority: R3/R4 > budget > capabilities > R2-rules ──────

    def test_r3_overrides_capabilities_and_budget(self, engine, base_context):
        """R3 escalates even when budget is sufficient and capabilities exist."""
        output = engine.evaluate(
            mission_id="m9",
            objective="risky op",
            risk_level="R3",
            context=base_context,
            available_capabilities=["tool.file_write_report", "tool.file_read"],
            budget_remaining=99999.0,
        )
        assert output.action == "escalate"

    def test_budget_zero_overrides_r1_with_capabilities(self, engine, base_context):
        """Zero budget escalates before checking capabilities."""
        output = engine.evaluate(
            mission_id="m10",
            objective="low risk task",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_write_report", "tool.file_read"],
            budget_remaining=0.0,
        )
        assert output.action == "escalate"

    # ── Model Selection ─────────────────────────────────────────────────

    def test_r1_risk_selects_flash(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m11",
            objective="simple task",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=1.0,
        )
        assert output.selected_model == "deepseek-v4-flash"
        assert output.selected_provider == "deepseek"

    def test_r2_risk_selects_pro(self, engine, base_context):
        """R2 → risk_num = 2/4 = 0.5 → >= 0.5 → pro tier."""
        output = engine.evaluate(
            mission_id="m12",
            objective="moderate task",
            risk_level="R2",
            context=base_context,
            available_capabilities=["tool.file_write_report"],
            budget_remaining=1.0,
        )
        assert output.selected_model == "deepseek-v4-pro"

    def test_r3_risk_selects_pro(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m13",
            objective="high risk task",
            risk_level="R3",
            context=base_context,
            available_capabilities=["tool.file_write"],
            budget_remaining=100.0,
        )
        assert output.selected_model == "deepseek-v4-pro"

    def test_r4_risk_selects_pro(self, engine, base_context):
        output = engine.evaluate(
            mission_id="m14",
            objective="critical task",
            risk_level="R4",
            context=base_context,
            available_capabilities=["tool.file_write"],
            budget_remaining=100.0,
        )
        assert output.selected_model == "deepseek-v4-pro"

    # ── Risk Assessment Text ────────────────────────────────────────────

    def test_high_risk_assessment_r4(self, engine, base_context):
        output = engine.evaluate(
            mission_id="risk_high",
            objective="critical",
            risk_level="R4",
            context=base_context,
            available_capabilities=["tool.file_write"],
            budget_remaining=100.0,
        )
        assert "HIGH" in output.risk_assessment
        assert "escalation" in output.risk_assessment

    def test_medium_risk_assessment_r2(self, engine, base_context):
        output = engine.evaluate(
            mission_id="risk_med",
            objective="moderate",
            risk_level="R2",
            context=base_context,
            available_capabilities=["tool.file_write_report"],
            budget_remaining=10.0,
        )
        assert "MEDIUM" in output.risk_assessment

    def test_low_risk_assessment_r1(self, engine, base_context):
        output = engine.evaluate(
            mission_id="risk_low",
            objective="simple",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=10.0,
        )
        assert "LOW" in output.risk_assessment

    # ── Output Structure ────────────────────────────────────────────────

    def test_decision_output_structure(self, engine, base_context):
        output = engine.evaluate(
            mission_id="struct_test",
            objective="validate output shape",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=5.0,
        )
        d = output.to_dict()
        assert d["decision_id"].startswith("dec_")
        assert d["mission_id"] == "struct_test"
        assert d["action"] in ("execute", "escalate", "reject", "delegate")
        assert d["selected_model"].startswith("deepseek-v4-")
        assert d["selected_provider"] == "deepseek"
        assert "risk_level" in d["reasoning"] or "risk" in d["reasoning"].lower()
        assert "risk_assessment" in d
        assert d["evidence_refs"] == []
        assert "timestamp" in d

    def test_estimated_tokens_defaults_to_zero(self, engine, base_context):
        output = engine.evaluate(
            mission_id="tokens_test",
            objective="tokens",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=1.0,
        )
        assert output.estimated_tokens == 0

    # ── Reasoning String Format ─────────────────────────────────────────

    def test_reasoning_contains_action_and_tier(self, engine, base_context):
        output = engine.evaluate(
            mission_id="reason_test",
            objective="just a task",
            risk_level="R1",
            context=base_context,
            available_capabilities=["tool.file_read"],
            budget_remaining=1.0,
        )
        assert "Action=" in output.reasoning
        assert "Tier=" in output.reasoning

    def test_reasoning_contains_metrics(self, engine, base_context):
        output = engine.evaluate(
            mission_id="metrics",
            objective="test metrics",
            risk_level="R2",
            context=base_context,
            available_capabilities=["tool.file_write_report"],
            budget_remaining=42.0,
        )
        assert "risk_level" in output.reasoning
        assert "capabilities" in output.reasoning
        assert "budget_remaining" in output.reasoning


class TestDecisionEngineClassifyAction:
    """Unit tests for the static _classify_action method."""

    def test_r3_escalates(self):
        assert DecisionEngine._classify_action("R3", ["cap1"], 100.0) == "escalate"

    def test_r4_escalates(self):
        assert DecisionEngine._classify_action("R4", ["cap1"], 100.0) == "escalate"

    def test_zero_budget_escalates(self):
        assert DecisionEngine._classify_action("R1", ["cap1"], 0.0) == "escalate"

    def test_negative_budget_escalates(self):
        assert DecisionEngine._classify_action("R1", ["cap1"], -1.0) == "escalate"

    def test_no_capabilities_rejects(self):
        assert DecisionEngine._classify_action("R1", [], 100.0) == "reject"

    def test_r2_with_write_cap_executes(self):
        assert DecisionEngine._classify_action("R2", ["tool.file_write_report"], 10.0) == "execute"

    def test_r2_without_write_cap_delegates(self):
        assert DecisionEngine._classify_action("R2", ["tool.file_read"], 10.0) == "delegate"

    def test_r1_defaults_execute(self):
        assert DecisionEngine._classify_action("R1", ["tool.file_read"], 1.0) == "execute"

    def test_r0_defaults_execute(self):
        assert DecisionEngine._classify_action("R0", ["tool.file_read"], 1.0) == "execute"

    def test_barely_positive_budget_ok(self):
        """Very small but positive budget allows execution."""
        assert DecisionEngine._classify_action("R1", ["cap1"], 0.000001) == "execute"

    # ── Priority test ───────────────────────────────────────────────

    def test_classify_priority_r3_before_budget(self):
        """R3 escalates even when budget is zero — R3/R4 check comes first."""
        assert DecisionEngine._classify_action("R3", [], 0.0) == "escalate"


class TestDecisionOutput:
    """Tests for the DecisionOutput data class."""

    def test_to_dict_matches_constructor(self):
        d = DecisionOutput(
            decision_id="dec_abc123",
            mission_id="m42",
            action="execute",
            selected_model="deepseek-v4-flash",
            selected_provider="deepseek",
            reasoning="test reasoning",
            risk_assessment="LOW",
            evidence_refs=["ev1", "ev2"],
            timestamp="2026-08-07T00:00:00Z",
        )
        result = d.to_dict()
        assert result["decision_id"] == "dec_abc123"
        assert result["mission_id"] == "m42"
        assert result["action"] == "execute"
        assert result["evidence_refs"] == ["ev1", "ev2"]

    def test_to_dict_is_serializable(self):
        import json
        d = DecisionOutput(
            decision_id="dec_abc",
            mission_id="m",
            action="execute",
            selected_model="deepseek-v4-flash",
            selected_provider="deepseek",
            reasoning="r",
            risk_assessment="LOW",
            evidence_refs=[],
            timestamp="2026-08-07T00:00:00Z",
        )
        # should not raise
        json.dumps(d.to_dict())

    def test_estimated_tokens_default(self):
        d = DecisionOutput(
            decision_id="dec_x",
            mission_id="m",
            action="execute",
            selected_model="deepseek-v4-flash",
            selected_provider="deepseek",
            reasoning="r",
            risk_assessment="LOW",
            evidence_refs=[],
            timestamp="2026-08-07T00:00:00Z",
        )
        assert d.estimated_tokens == 0


class TestDecisionEngineEdgeCases:
    """Edge case and boundary tests."""

    @pytest.fixture
    def engine(self):
        return DecisionEngine()

    def test_empty_objective(self, engine):
        output = engine.evaluate(
            mission_id="empty_obj",
            objective="",
            risk_level="R1",
            context={},
            available_capabilities=["tool.file_read"],
            budget_remaining=1.0,
        )
        assert output.mission_id == "empty_obj"

    def test_very_long_objective(self, engine):
        long_obj = "analyze the complete architecture " * 100
        output = engine.evaluate(
            mission_id="long_obj",
            objective=long_obj,
            risk_level="R1",
            context={},
            available_capabilities=["tool.file_read"],
            budget_remaining=1.0,
        )
        assert output.mission_id == "long_obj"

    def test_many_capabilities(self, engine):
        caps = [f"tool.cap_{i}" for i in range(100)]
        output = engine.evaluate(
            mission_id="many_caps",
            objective="use all tools",
            risk_level="R1",
            context={},
            available_capabilities=caps,
            budget_remaining=1.0,
        )
        assert output.action == "execute"

    def test_enormous_budget(self, engine):
        output = engine.evaluate(
            mission_id="big_budget",
            objective="costly task",
            risk_level="R2",
            context={},
            available_capabilities=["tool.file_write_report"],
            budget_remaining=1e12,
        )
        assert output.action == "execute"
        assert output.selected_model == "deepseek-v4-pro"

    def test_unique_decision_ids(self, engine):
        """Each evaluate() call produces a unique decision_id."""
        ids = set()
        for i in range(10):
            output = engine.evaluate(
                mission_id=f"m{i}",
                objective=f"task {i}",
                risk_level="R1",
                context={},
                available_capabilities=["tool.file_read"],
                budget_remaining=1.0,
            )
            ids.add(output.decision_id)
        assert len(ids) == 10

    def test_r2_exactly_zero_point_five_risk_num(self, engine):
        """R2 → risk_num = 2/4 = 0.5 → >= 0.5 → pro tier."""
        output = engine.evaluate(
            mission_id="exact_boundary",
            objective="boundary test",
            risk_level="R2",
            context={},
            available_capabilities=["tool.file_write_report"],
            budget_remaining=10.0,
        )
        assert output.selected_model == "deepseek-v4-pro"

    def test_r1_risk_num_0_25_selects_flash(self, engine):
        """R1 → risk_num = 1/4 = 0.25 → < 0.5 → flash tier."""
        output = engine.evaluate(
            mission_id="r1_flash",
            objective="flash task",
            risk_level="R1",
            context={},
            available_capabilities=["tool.file_read"],
            budget_remaining=10.0,
        )
        assert output.selected_model == "deepseek-v4-flash"
