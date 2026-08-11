"""Tests: Planner — mission planning with goal decomposition."""

import pytest

from src.nexara_prime.brain.planner import Planner


@pytest.fixture
def planner():
    return Planner()


@pytest.fixture
def sample_args():
    return {
        "objective": "Build a governed AI agent runtime",
        "risk_level": "R1",
        "boundaries": ["no network egress", "read-only fs"],
        "deliverables": ["tested code", "evidence"],
    }


class TestPlannerBasics:
    """Basic planner properties."""

    def test_name(self, planner):
        assert planner.name == "planner"


class TestPlan:
    """plan() method — full plan generation."""

    def test_plan_returns_dict(self, planner, sample_args):
        result = planner.plan(**sample_args)
        assert isinstance(result, dict)

    def test_plan_includes_all_keys(self, planner, sample_args):
        result = planner.plan(**sample_args)

        assert "plan_id" in result
        assert "objective" in result
        assert "risk_level" in result
        assert "boundaries" in result
        assert "deliverables" in result
        assert "steps" in result
        assert "created_at" in result

    def test_plan_id_format(self, planner, sample_args):
        result = planner.plan(**sample_args)
        assert result["plan_id"].startswith("plan_")
        assert len(result["plan_id"]) > 5

    def test_plan_ids_are_unique(self, planner, sample_args):
        r1 = planner.plan(**sample_args)
        r2 = planner.plan(**sample_args)
        assert r1["plan_id"] != r2["plan_id"]

    def test_plan_preserves_objective(self, planner, sample_args):
        result = planner.plan(**sample_args)
        assert result["objective"] == sample_args["objective"]

    def test_plan_preserves_risk_level(self, planner, sample_args):
        result = planner.plan(**sample_args)
        assert result["risk_level"] == sample_args["risk_level"]

    def test_plan_preserves_boundaries(self, planner, sample_args):
        result = planner.plan(**sample_args)
        assert result["boundaries"] == sample_args["boundaries"]

    def test_plan_preserves_deliverables(self, planner, sample_args):
        result = planner.plan(**sample_args)
        assert result["deliverables"] == sample_args["deliverables"]

    def test_plan_created_at_is_iso(self, planner, sample_args):
        result = planner.plan(**sample_args)
        ts = result["created_at"]
        assert "T" in ts
        assert ts.endswith("+00:00") or ts.endswith("Z")


class TestStepsStandardRisk:
    """Step generation for standard risk levels (R0-R2)."""

    @pytest.mark.parametrize("risk_level", ["R0", "R1", "R2"])
    def test_standard_risk_has_seven_steps(self, planner, risk_level):
        result = planner.plan("test obj", risk_level, [], [])
        assert len(result["steps"]) == 7

    @pytest.mark.parametrize("risk_level", ["R0", "R1", "R2"])
    def test_standard_risk_no_risk_gate(self, planner, risk_level):
        result = planner.plan("test obj", risk_level, [], [])
        actions = [s["action"] for s in result["steps"]]
        assert "risk_gate" not in actions

    def test_step_structure(self, planner):
        result = planner.plan("test obj", "R1", [], [])
        step = result["steps"][0]

        assert "order" in step
        assert "role" in step
        assert "action" in step
        assert "description" in step

    def test_steps_have_correct_roles(self, planner):
        result = planner.plan("test obj", "R1", [], [])

        expected_roles = [
            "Orchestrator",
            "Planner",
            "Analyst",
            "Executor",
            "Reviewer",
            "Auditor",
            "Archivist",
        ]
        actual_roles = [s["role"] for s in result["steps"]]
        assert actual_roles == expected_roles

    def test_steps_have_correct_actions(self, planner):
        result = planner.plan("test obj", "R1", [], [])

        expected_actions = [
            "validate_boundaries",
            "assess_capabilities",
            "analyze_context",
            "execute_task",
            "verify_outputs",
            "audit_trail",
            "archive_evidence",
        ]
        actual_actions = [s["action"] for s in result["steps"]]
        assert actual_actions == expected_actions

    def test_execute_step_includes_objective(self, planner):
        objective = "Build a rocket ship"
        result = planner.plan(objective, "R1", [], [])

        execute_step = result["steps"][3]
        assert "Execute:" in execute_step["description"]
        assert objective[:80] in execute_step["description"]


class TestStepsHighRisk:
    """Step generation for high risk levels (R3-R4)."""

    @pytest.mark.parametrize("risk_level", ["R3", "R4"])
    def test_high_risk_has_eight_steps(self, planner, risk_level):
        result = planner.plan("test obj", risk_level, [], [])
        assert len(result["steps"]) == 8

    @pytest.mark.parametrize("risk_level", ["R3", "R4"])
    def test_high_risk_includes_risk_gate(self, planner, risk_level):
        result = planner.plan("test obj", risk_level, [], [])
        actions = [s["action"] for s in result["steps"]]
        assert "risk_gate" in actions

    def test_risk_gate_position(self, planner):
        """Risk gate should be at position 3 (inserted before execution)."""
        result = planner.plan("test obj", "R4", [], [])

        risk_gate_steps = [s for s in result["steps"] if s["action"] == "risk_gate"]
        assert len(risk_gate_steps) == 1
        assert risk_gate_steps[0]["order"] == 3
        assert risk_gate_steps[0]["role"] == "Auditor"

    def test_risk_gate_before_execution(self, planner):
        """Risk gate should appear before the execute_task step."""
        result = planner.plan("test obj", "R4", [], [])

        gate_idx = next(i for i, s in enumerate(result["steps"]) if s["action"] == "risk_gate")
        exec_idx = next(i for i, s in enumerate(result["steps"]) if s["action"] == "execute_task")

        assert gate_idx < exec_idx

    def test_risk_gate_description(self, planner):
        result = planner.plan("test obj", "R4", [], [])
        gate = [s for s in result["steps"] if s["action"] == "risk_gate"][0]
        assert "Human approval gate" in gate["description"]


class TestDecompose:
    """Direct _decompose() method."""

    @pytest.mark.parametrize("risk_level", ["R0", "R1", "R2"])
    def test_decompose_low_risk_no_gate(self, planner, risk_level):
        steps = planner._decompose("test", risk_level)
        assert len(steps) == 7
        actions = [s["action"] for s in steps]
        assert "risk_gate" not in actions

    @pytest.mark.parametrize("risk_level", ["R3", "R4"])
    def test_decompose_high_risk_has_gate(self, planner, risk_level):
        steps = planner._decompose("test", risk_level)
        assert len(steps) == 8
        actions = [s["action"] for s in steps]
        assert "risk_gate" in actions

    def test_decompose_objective_in_description(self, planner):
        steps = planner._decompose("build api", "R1")
        assert "Execute:" in steps[3]["description"]
        assert "build api" in steps[3]["description"]

    def test_decompose_long_objective_truncated(self, planner):
        long_obj = "x" * 120
        steps = planner._decompose(long_obj, "R1")
        desc = steps[3]["description"]
        assert len(desc) <= 9 + 80  # "Execute: " + 80 chars

    def test_decompose_returns_list_of_dicts(self, planner):
        steps = planner._decompose("test", "R2")
        assert isinstance(steps, list)
        assert all(isinstance(s, dict) for s in steps)

    def test_decompose_every_step_has_required_keys(self, planner):
        steps = planner._decompose("test", "R3")
        for step in steps:
            assert "order" in step
            assert "role" in step
            assert "action" in step
            assert "description" in step
