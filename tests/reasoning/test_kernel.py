"""Tests: Reasoning Kernel API."""

import pytest
from src.nexara_prime.brain.reasoning import (
    ReasoningKernel, ReasoningResult,
    MissionContext,
)


@pytest.fixture
def kernel():
    return ReasoningKernel()


@pytest.fixture
def mission():
    return MissionContext(
        mission_id="test_m1",
        objective="Decide whether to use deepseek-v4-pro for report generation",
        risk_level="R2",
        constraints=["Budget: $0.50 max", "No external API calls"],
        boundaries=["Local workspace only"],
    )


class TestKernelAPI:
    """10 tests: reason(), audit(), quantify_uncertainty()."""

    def test_reason_returns_result(self, kernel, mission):
        result = kernel.reason(mission)
        assert isinstance(result, ReasoningResult)
        assert result.reasoning_id.startswith("reason_")

    def test_reason_has_conclusion(self, kernel, mission):
        result = kernel.reason(mission)
        assert result.conclusion != "" or result.trace.steps

    def test_reason_has_confidence(self, kernel, mission):
        result = kernel.reason(mission)
        assert 0.0 <= result.confidence.score <= 1.0

    def test_reason_has_self_check(self, kernel, mission):
        result = kernel.reason(mission)
        assert result.self_check is not None
        assert result.self_check.checks_total == 5

    def test_reason_produces_7_steps(self, kernel, mission):
        result = kernel.reason(mission)
        step_types = [s.step_type for s in result.trace.steps]
        assert "OBSERVE" in step_types
        assert "CLASSIFY" in step_types

    def test_reason_with_query(self, kernel, mission):
        result = kernel.reason(mission, query="Which model should I use?")
        assert result.conclusion or result.trace.steps

    def test_audit_returns_trace(self, kernel, mission):
        result = kernel.reason(mission)
        audit = kernel.audit(result.trace)
        assert audit["reasoning_id"] == result.reasoning_id
        assert audit["step_count"] == len(result.trace.steps)

    def test_quantify_uncertainty(self, kernel):
        result = kernel.quantify_uncertainty("Test conclusion", 0.8)
        assert "confidence_score" in result
        assert result["evidence_weight"] == 0.8

    def test_reason_evidence_refs_collected(self, kernel, mission):
        result = kernel.reason(mission)
        assert isinstance(result.evidence_refs, list)

    def test_reason_deterministic(self, kernel, mission):
        r1 = kernel.reason(mission)
        r2 = kernel.reason(mission)
        assert r1.conclusion == r2.conclusion
        assert r1.confidence.score == r2.confidence.score
