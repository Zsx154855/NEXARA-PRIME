"""Tests: Thought Process Engine — 7 step types, 3 chain structures."""

import pytest
from src.nexara_prime.brain.reasoning import (
    ThoughtProcessEngine, AssembledContext,
)


@pytest.fixture
def thinker():
    return ThoughtProcessEngine()


@pytest.fixture
def context():
    return AssembledContext(
        mission_summary="Test mission: verify reasoning",
        relevant_memories=[
            {"memory_id": "m1", "content": "Past report used deepseek-v4-pro with success", "confidence": 0.9, "key": "report_model"},
            {"memory_id": "m2", "content": "Budget constraint: prefer flash model for simple tasks", "confidence": 0.8, "key": "budget_rule"},
        ],
        past_decisions=[
            {"memory_id": "d1", "content": "Chose pro for complex analysis", "kind": "decision"},
        ],
        preferences=[
            {"memory_id": "p1", "content": "Owner prefers speed over cost", "kind": "preference"},
        ],
    )


class TestThoughtProcess:
    """15 tests covering 7 step types and chain structures."""

    def test_chain_produces_steps(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        assert len(steps) >= 5

    def test_observe_step_present(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        observe = [s for s in steps if s.step_type == "OBSERVE"]
        assert len(observe) == 1
        assert observe[0].confidence > 0.8

    def test_classify_step_present(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        classify = [s for s in steps if s.step_type == "CLASSIFY"]
        assert len(classify) == 1

    def test_decompose_step_present(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        decomp = [s for s in steps if s.step_type == "DECOMPOSE"]
        assert len(decomp) == 1

    def test_infer_step_present(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        infer = [s for s in steps if s.step_type == "INFER"]
        assert len(infer) == 1

    def test_validate_step_present(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        validate = [s for s in steps if s.step_type == "VALIDATE"]
        assert len(validate) == 1

    def test_synthesize_step_present(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        synth = [s for s in steps if s.step_type == "SYNTHESIZE"]
        assert len(synth) == 1

    def test_reflect_step_present(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        reflect = [s for s in steps if s.step_type == "REFLECT"]
        assert len(reflect) == 1

    def test_classify_selection_type(self, thinker, context):
        steps = thinker.execute_chain("decide which model to choose", context)
        classify = [s for s in steps if s.step_type == "CLASSIFY"][0]
        assert "selection" in classify.output.lower()

    def test_classify_prediction_type(self, thinker, context):
        steps = thinker.execute_chain("predict the outcome of this", context)
        classify = [s for s in steps if s.step_type == "CLASSIFY"][0]
        assert "prediction" in classify.output.lower()

    def test_classify_binary_type(self, thinker, context):
        steps = thinker.execute_chain("should we allow this?", context)
        classify = [s for s in steps if s.step_type == "CLASSIFY"][0]
        assert "binary" in classify.output.lower()

    def test_steps_have_dependencies(self, thinker, context):
        steps = thinker.execute_chain("test", context)
        deps = [s for s in steps if s.depends_on]
        assert len(deps) > 0  # most steps should depend on prior steps

    def test_infer_has_evidence(self, thinker, context):
        steps = thinker.execute_chain("test query", context)
        infer = [s for s in steps if s.step_type == "INFER"][0]
        assert len(infer.evidence_refs) > 0

    def test_empty_context_produces_steps(self, thinker):
        empty = AssembledContext()
        steps = thinker.execute_chain("test", empty)
        assert len(steps) > 0
        infer = [s for s in steps if s.step_type == "INFER"][0]
        assert "No relevant memories" in infer.output

    def test_step_ids_are_unique(self, thinker, context):
        steps = thinker.execute_chain("test", context)
        ids = [s.step_id for s in steps]
        assert len(ids) == len(set(ids))
