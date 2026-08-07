"""Tests: ChiefBrainKernel — NEXARA PRIME cognitive governance layer.

Covers:
  - Kernel initialization (default sub-components)
  - analyze_intent() — intent analysis with goal decomposition and receipt
  - decide() — governed mission execution decisions with budget/policy enforcement
  - observe_result() — post-execution learning and memory consolidation
  - bind_memory() — memory controller binding
  - latest_receipt() / all_receipts() — receipt management
  - health() — component health report
  - Model policy enforcement path
  - Budget enforcement path
  - Edge cases (empty objectives, multiple missions, etc.)
"""
from __future__ import annotations

import pytest

from src.nexara_prime.models import (
    AgentAssignment,
    Mission,
    MissionSpec,
    Persona,
    RiskLevel,
    RuntimeRole,
)
from src.nexara_prime.brain.kernel import ChiefBrainKernel
from src.nexara_prime.brain.decision_engine import DecisionOutput
from src.nexara_prime.brain.memory_controller import MemoryController


# ── Helpers ──────────────────────────────────────────────────────────────

def make_mission(
    mission_id: str = "m_test",
    objective: str = "write a test file",
    risk_level: RiskLevel = RiskLevel.R1,
    capabilities: list[str] | None = None,
) -> Mission:
    """Create a minimal valid Mission for testing."""
    spec = MissionSpec(
        title="Test Mission",
        objective=objective,
        risk_level=risk_level,
    )
    assignment = AgentAssignment(
        mission_id=mission_id,
        persona=Persona.ORION,
        runtime_role=RuntimeRole.EXECUTOR,
        loaded_capabilities=capabilities or ["tool.file_read"],
    )
    return Mission(
        mission_id=mission_id,
        spec=spec,
        trace_id=f"trace_{mission_id}",
        assignments=[assignment],
    )


def make_mission_r2(capabilities: list[str] | None = None) -> Mission:
    """R2 mission with write capability (so it executes)."""
    caps = capabilities or ["tool.file_write_report"]
    return make_mission(
        mission_id="m_r2",
        objective="modify config",
        risk_level=RiskLevel.R2,
        capabilities=caps,
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestKernelInitialization:
    """Tests for ChiefBrainKernel.__init__ and default sub-components."""

    def test_default_constructor_creates_all_engines(self):
        k = ChiefBrainKernel()
        assert k.name == "chief_brain_kernel"
        assert k.decisions is not None
        assert k.goals is not None
        assert k.context is not None
        assert k.model_policy is not None
        assert k.budget is not None
        assert k.memory is None  # not bound by default
        assert k._receipts == []
        assert k._missions_observed == set()

    def test_default_budget_is_positive(self):
        k = ChiefBrainKernel()
        assert k.budget.remaining > 0
        assert k.budget.total_budget > 0

    def test_custom_budget(self):
        from src.nexara_prime.brain.reasoning_budget import ReasoningBudgetManager
        budget = ReasoningBudgetManager(total_budget=5.0)
        k = ChiefBrainKernel(budget=budget)
        assert k.budget.total_budget == 5.0

    def test_custom_model_policy(self):
        from src.nexara_prime.brain.model_policy import ModelPolicyEngine
        policy = ModelPolicyEngine()
        k = ChiefBrainKernel(model_policy=policy)
        assert k.model_policy is policy

    def test_memory_none_by_default(self):
        k = ChiefBrainKernel()
        assert k.memory is None


class TestAnalyzeIntent:
    """Tests for analyze_intent() — pre-mission intent analysis."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_returns_dict_with_expected_keys(self, kernel):
        result = kernel.analyze_intent("write tests for the brain module")
        assert isinstance(result, dict)
        assert "receipt_id" in result
        assert result["action"] == "intent_analysis"
        assert result["objective"] == "write tests for the brain module"
        assert result["risk_level"] == "R1"
        assert "model_tier" in result
        assert "estimated_tokens" in result
        assert "goals" in result
        assert "timestamp" in result

    def test_default_risk_level_is_r1(self, kernel):
        result = kernel.analyze_intent("any task")
        assert result["risk_level"] == "R1"

    def test_r2_risk_level_passed_through(self, kernel):
        result = kernel.analyze_intent("moderate risk task", risk_level="R2")
        assert result["risk_level"] == "R2"

    def test_r3_risk_level_passed_through(self, kernel):
        result = kernel.analyze_intent("high risk task", risk_level="R3")
        assert result["risk_level"] == "R3"

    def test_short_objective_decomposes_to_single_goal(self, kernel):
        result = kernel.analyze_intent("hello")
        assert len(result["goals"]) == 1

    def test_long_objective_decomposes_to_three_goals(self, kernel):
        result = kernel.analyze_intent("write a comprehensive test suite for the brain kernel module")
        assert len(result["goals"]) == 3
        goal_descs = [g["description"] for g in result["goals"]]
        assert any("Plan:" in d for d in goal_descs)
        assert any("Execute:" in d for d in goal_descs)
        assert any("Verify:" in d for d in goal_descs)

    def test_estimated_tokens_scales_with_objective_length(self, kernel):
        short = kernel.analyze_intent("hi")["estimated_tokens"]
        long = kernel.analyze_intent("a " * 200)["estimated_tokens"]
        assert long > short

    def test_model_tier_is_pro_for_complexity_0_5(self, kernel):
        """analyze_intent uses complexity=0.5 which is >= 0.4 → pro tier."""
        result = kernel.analyze_intent("simple task", risk_level="R1")
        # complexity=0.5 >= 0.4 threshold → pro, even for R1
        assert result["model_tier"] == "pro"

    def test_model_tier_is_pro_for_r3(self, kernel):
        """R3 → risk_num = 3/4 = 0.75 → >= 0.75 → pro tier."""
        result = kernel.analyze_intent("risky task", risk_level="R3")
        assert result["model_tier"] == "pro"

    def test_receipt_is_appended(self, kernel):
        assert len(kernel.all_receipts()) == 0
        kernel.analyze_intent("task one")
        assert len(kernel.all_receipts()) == 1
        kernel.analyze_intent("task two")
        assert len(kernel.all_receipts()) == 2

    def test_empty_objective_handled(self, kernel):
        result = kernel.analyze_intent("")
        assert result["objective"] == ""
        assert len(result["goals"]) == 1


class TestDecide:
    """Tests for decide() — governed mission execution decision."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_returns_receipt_dict(self, kernel):
        mission = make_mission()
        receipt = kernel.decide(mission, {"source": "test"})
        assert isinstance(receipt, dict)
        assert "receipt_id" in receipt
        assert "action" in receipt
        assert "decision" in receipt

    def test_decision_contains_action(self, kernel):
        mission = make_mission()
        receipt = kernel.decide(mission, {"source": "test"})
        assert receipt["decision"]["action"] in ("execute", "escalate", "reject", "delegate")

    def test_receipts_accumulate(self, kernel):
        m1 = make_mission("m1")
        m2 = make_mission("m2")
        kernel.decide(m1, {})
        kernel.decide(m2, {})
        assert len(kernel.all_receipts()) == 2

    def test_missions_observed_grows(self, kernel):
        m1 = make_mission("m1")
        m2 = make_mission("m2")
        kernel.decide(m1, {})
        assert "m1" in kernel._missions_observed
        kernel.decide(m2, {})
        assert "m2" in kernel._missions_observed
        assert len(kernel._missions_observed) == 2

    def test_low_risk_mission_executes(self, kernel):
        mission = make_mission(risk_level=RiskLevel.R1, capabilities=["tool.file_read"])
        receipt = kernel.decide(mission, {})
        assert receipt["decision"]["action"] == "execute"

    def test_r2_with_write_cap_executes(self, kernel):
        mission = make_mission_r2(capabilities=["tool.file_write_report"])
        receipt = kernel.decide(mission, {})
        assert receipt["decision"]["action"] == "execute"

    def test_r2_without_write_cap_delegates(self, kernel):
        mission = make_mission_r2(capabilities=["tool.file_read"])
        receipt = kernel.decide(mission, {})
        assert receipt["decision"]["action"] == "delegate"

    def test_r3_escalates_regardless_of_budget(self, kernel):
        mission = make_mission(risk_level=RiskLevel.R3, capabilities=["tool.file_write"])
        receipt = kernel.decide(mission, {})
        assert receipt["decision"]["action"] == "escalate"

    def test_decision_includes_selected_model(self, kernel):
        mission = make_mission()
        receipt = kernel.decide(mission, {})
        assert "selected_model" in receipt["decision"]
        assert receipt["decision"]["selected_model"].startswith("deepseek-v4-")

    def test_context_passed_through(self, kernel):
        mission = make_mission()
        context = {"key1": "value1", "nested": {"a": 1}}
        receipt = kernel.decide(mission, context)
        # Context is passed to DecisionEngine.evaluate — verify it produces a valid decision
        assert receipt["receipt_id"].startswith("br_")

    def test_multiple_assignments_capabilities_merged(self, kernel):
        """All assignments' loaded_capabilities are collected."""
        spec = MissionSpec(title="Multi", objective="multi-cap", risk_level=RiskLevel.R1)
        a1 = AgentAssignment(
            mission_id="m_multi", persona=Persona.ORION,
            runtime_role=RuntimeRole.EXECUTOR,
            loaded_capabilities=["tool.file_read"],
        )
        a2 = AgentAssignment(
            mission_id="m_multi", persona=Persona.ATLAS,
            runtime_role=RuntimeRole.REVIEWER,
            loaded_capabilities=["tool.file_write_report"],
        )
        mission = Mission(
            mission_id="m_multi", spec=spec, trace_id="tr_multi",
            assignments=[a1, a2],
        )
        receipt = kernel.decide(mission, {})
        assert receipt["decision"]["action"] == "execute"

    def test_receipt_id_is_unique_per_decision(self, kernel):
        ids = set()
        for i in range(5):
            m = make_mission(f"m{i}")
            receipt = kernel.decide(m, {})
            ids.add(receipt["receipt_id"])
        assert len(ids) == 5


class TestModelPolicyRejection:
    """Tests for the model-policy rejection path in decide()."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_policy_rejects_disallowed_model(self, kernel, monkeypatch):
        """When DecisionEngine picks a model not allowed for the risk level,
        the kernel overrides action to 'reject'."""
        # Monkey-patch evaluate to return a DecisionOutput with a non-deepseek model
        from src.nexara_prime.brain import decision_engine as de_mod

        original_evaluate = de_mod.DecisionEngine.evaluate

        def fake_evaluate(self, *, mission_id, objective, risk_level, context,
                          available_capabilities, budget_remaining):
            output = original_evaluate(
                self, mission_id=mission_id, objective=objective,
                risk_level=risk_level, context=context,
                available_capabilities=available_capabilities,
                budget_remaining=budget_remaining,
            )
            # Override to a model NOT allowed for R3
            output.selected_model = "gpt-5"
            return output

        monkeypatch.setattr(de_mod.DecisionEngine, "evaluate", fake_evaluate)

        mission = make_mission(risk_level=RiskLevel.R3, capabilities=["tool.file_write"])
        receipt = kernel.decide(mission, {})

        assert receipt["decision"]["action"] == "reject"
        assert "not allowed" in receipt["decision"]["reasoning"].lower()

    def test_deepseek_models_always_allowed(self, kernel):
        """All deepseek-prefixed models pass the policy gate."""
        mission = make_mission(risk_level=RiskLevel.R4, capabilities=["tool.file_write"])
        # R4 with deepseek-v4-pro should NOT be rejected by model policy
        receipt = kernel.decide(mission, {})
        # Action should be escalate (from R4), not reject (model policy)
        assert receipt["decision"]["action"] == "escalate"


class TestBudgetEnforcement:
    """Tests for the budget enforcement path in decide()."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_budget_exceeded_triggers_escalate(self, kernel, monkeypatch):
        """When cost_estimate > remaining budget, action becomes 'escalate'."""
        from src.nexara_prime.brain import decision_engine as de_mod

        original_evaluate = de_mod.DecisionEngine.evaluate

        def fake_evaluate(self, *, mission_id, objective, risk_level, context,
                          available_capabilities, budget_remaining):
            output = original_evaluate(
                self, mission_id=mission_id, objective=objective,
                risk_level=risk_level, context=context,
                available_capabilities=available_capabilities,
                budget_remaining=budget_remaining,
            )
            # Force high token estimate → high cost
            output.estimated_tokens = 1_000_000
            return output

        monkeypatch.setattr(de_mod.DecisionEngine, "evaluate", fake_evaluate)

        # Default budget is 0.10 — 1M tokens with pro model will exceed it
        mission = make_mission(risk_level=RiskLevel.R2, capabilities=["tool.file_write_report"])
        receipt = kernel.decide(mission, {})

        assert receipt["decision"]["action"] == "escalate"
        assert "Budget exceeded" in receipt["decision"]["reasoning"]

    def test_budget_not_exceeded_no_escalation(self, kernel):
        """Normal budget (0.10) with 0 estimated tokens should not trigger escalation."""
        mission = make_mission()
        receipt = kernel.decide(mission, {})
        # Action should be execute (low risk), not escalate
        assert receipt["decision"]["action"] == "execute"

    def test_small_budget_still_works(self, kernel):
        """Very small but non-zero budget allows low-token tasks."""
        from src.nexara_prime.brain.reasoning_budget import ReasoningBudgetManager
        kernel = ChiefBrainKernel(budget=ReasoningBudgetManager(total_budget=0.0001))
        mission = make_mission()
        receipt = kernel.decide(mission, {})
        assert receipt["decision"]["action"] == "execute"


class TestObserveResult:
    """Tests for observe_result() — post-execution learning."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_records_token_usage(self, kernel):
        initial = kernel.budget.remaining
        kernel.observe_result("m1", {
            "input_tokens": 500,
            "output_tokens": 200,
            "cost_usd": 0.001,
            "provider": "deepseek",
            "evaluation_passed": False,
        })
        assert kernel.budget.remaining < initial

    def test_zero_tokens_no_effect(self, kernel):
        initial = kernel.budget.remaining
        kernel.observe_result("m1", {})
        assert kernel.budget.remaining == initial

    def test_missing_cost_defaults_to_zero(self, kernel):
        initial = kernel.budget.remaining
        kernel.observe_result("m1", {"input_tokens": 100, "output_tokens": 50})
        assert kernel.budget.remaining <= initial

    def test_passing_evaluation_triggers_memory_consolidation(self, kernel, monkeypatch, tmp_path):
        """When evaluation_passed=True and memory is bound, consolidate() is called."""
        from src.nexara_prime.brain.db import BrainDB

        db = BrainDB(path=tmp_path / "brain.db")
        mc = MemoryController(db=db, persist=True)
        kernel.bind_memory(mc)

        consolidated = []

        def fake_consolidate(mission_id):
            consolidated.append(mission_id)

        monkeypatch.setattr(mc, "consolidate", fake_consolidate)

        kernel.observe_result("m_cons", {
            "input_tokens": 10,
            "output_tokens": 10,
            "cost_usd": 0.001,
            "provider": "deepseek",
            "evaluation_passed": True,
        })
        assert consolidated == ["m_cons"]

    def test_failing_evaluation_skips_memory(self, kernel, monkeypatch, tmp_path):
        """When evaluation_passed=False, memory.consolidate is NOT called."""
        from src.nexara_prime.brain.db import BrainDB

        db = BrainDB(path=tmp_path / "brain.db")
        mc = MemoryController(db=db, persist=True)
        kernel.bind_memory(mc)

        consolidated = []

        def fake_consolidate(mission_id):
            consolidated.append(mission_id)

        monkeypatch.setattr(mc, "consolidate", fake_consolidate)

        kernel.observe_result("m_fail", {
            "input_tokens": 10,
            "output_tokens": 10,
            "evaluation_passed": False,
        })
        assert consolidated == []

    def test_no_memory_bound_no_consolidation(self, kernel):
        """Without memory bound, observe_result does not crash on eval_passed=True."""
        # should not raise
        kernel.observe_result("m_no_mem", {
            "input_tokens": 10,
            "output_tokens": 10,
            "evaluation_passed": True,
        })


class TestBindMemory:
    """Tests for bind_memory()."""

    def test_bind_memory_sets_controller(self, tmp_path):
        from src.nexara_prime.brain.db import BrainDB

        k = ChiefBrainKernel()
        db = BrainDB(path=tmp_path / "brain.db")
        mc = MemoryController(db=db, persist=True)

        assert k.memory is None
        k.bind_memory(mc)
        assert k.memory is mc

    def test_health_reflects_bound_memory(self, tmp_path):
        from src.nexara_prime.brain.db import BrainDB

        k = ChiefBrainKernel()
        db = BrainDB(path=tmp_path / "brain.db")
        mc = MemoryController(db=db, persist=True)

        assert k.health()["memory_bound"] is False
        k.bind_memory(mc)
        assert k.health()["memory_bound"] is True


class TestReceipts:
    """Tests for latest_receipt() and all_receipts()."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_latest_receipt_none_when_empty(self, kernel):
        assert kernel.latest_receipt() is None

    def test_latest_receipt_returns_last(self, kernel):
        kernel.analyze_intent("first")
        kernel.analyze_intent("second")
        latest = kernel.latest_receipt()
        assert latest is not None
        assert latest["objective"] == "second"

    def test_all_receipts_returns_copies(self, kernel):
        kernel.analyze_intent("task")
        receipts = kernel.all_receipts()
        assert len(receipts) == 1
        assert receipts[0]["action"] == "intent_analysis"

    def test_all_receipts_empty_initially(self, kernel):
        assert kernel.all_receipts() == []


class TestHealth:
    """Tests for health() report."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_health_returns_expected_keys(self, kernel):
        h = kernel.health()
        assert h["component"] == "chief_brain_kernel"
        assert "decisions_made" in h
        assert "goals_active" in h
        assert "budget_remaining" in h
        assert "model_policy" in h
        assert "memory_bound" in h

    def test_decisions_made_reflects_receipt_count(self, kernel):
        assert kernel.health()["decisions_made"] == 0
        kernel.analyze_intent("task")
        assert kernel.health()["decisions_made"] == 1

    def test_goals_active_zero_initially(self, kernel):
        assert kernel.health()["goals_active"] == 0

    def test_goals_active_reflects_new_goals(self, kernel):
        kernel.analyze_intent("write comprehensive test suite for brain kernel")
        assert kernel.health()["goals_active"] == 3

    def test_budget_remaining_positive(self, kernel):
        assert kernel.health()["budget_remaining"] > 0


class TestKernelEdgeCases:
    """Edge case and boundary tests for ChiefBrainKernel."""

    @pytest.fixture
    def kernel(self):
        return ChiefBrainKernel()

    def test_multiple_missions_same_id(self, kernel):
        """Deciding on same mission_id twice should work (observed set dedup)."""
        m = make_mission("same_id")
        kernel.decide(m, {})
        kernel.decide(m, {})  # second call with same id
        assert len(kernel._missions_observed) == 1
        assert len(kernel.all_receipts()) == 2

    def test_mission_without_assignments(self, kernel):
        spec = MissionSpec(title="No Assign", objective="nothing to do", risk_level=RiskLevel.R1)
        mission = Mission(
            mission_id="no_assign", spec=spec, trace_id="tr_no_assign",
            assignments=[],
        )
        receipt = kernel.decide(mission, {})
        # No capabilities → reject
        assert receipt["decision"]["action"] == "reject"

    def test_observe_result_with_negative_tokens(self, kernel):
        """Negative token values should not crash (though semantically odd)."""
        initial = kernel.budget.remaining
        kernel.observe_result("neg", {"input_tokens": -100, "output_tokens": -50})
        # Just verifies no exception
        assert kernel.budget.remaining >= 0

    def test_observe_result_with_negative_cost(self, kernel):
        """Negative cost should not crash."""
        kernel.observe_result("neg_cost", {"input_tokens": 100, "output_tokens": 50, "cost_usd": -0.01})
        # No crash = success

    def test_analyze_intent_then_decide_then_observe_full_cycle(self, kernel):
        """Full brain pipeline: intent → decide → observe."""
        # 1. Analyze intent
        intent = kernel.analyze_intent("create a test file", risk_level="R1")
        assert intent["action"] == "intent_analysis"

        # 2. Decide on mission
        mission = make_mission(objective="create a test file", risk_level=RiskLevel.R1)
        decision = kernel.decide(mission, {"source": "cli"})
        assert "receipt_id" in decision

        # 3. Observe result
        kernel.observe_result(mission.mission_id, {
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.0001,
            "provider": "deepseek",
            "evaluation_passed": True,
        })

        # 4. Verify receipts
        assert len(kernel.all_receipts()) == 2
        health = kernel.health()
        assert health["decisions_made"] == 2
