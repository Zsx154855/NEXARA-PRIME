"""Tests for EvaluationEngine — the 5th stage of the NEXARA runtime pipeline.

Covers:
  - evaluate() basic flow and scoring
  - Completed / Failed mission evaluation
  - Empty-result edge cases
  - Idempotency (repeat calls return same result, no side effects)
  - list() filtering
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.evaluation import EvaluationEngine
from nexara_prime.events import EventBus
from nexara_prime.models import Mission, MissionSpec, MissionState, RiskLevel, new_id


# ── helpers ──────────────────────────────────────────────────────────


def _make_store() -> SQLiteStore:
    return SQLiteStore(Path(tempfile.mktemp(suffix=".db")))


def _make_engine(store: SQLiteStore) -> EvaluationEngine:
    return EvaluationEngine(store, EventBus(store))


def _make_mission(
    *,
    state: MissionState = MissionState.EVALUATION,
    risk_level: RiskLevel = RiskLevel.R2,
    rollback_point: str | None = None,
    result: dict | None = None,
    mission_id: str | None = None,
) -> Mission:
    """Create a minimal Mission for evaluation tests."""
    return Mission(
        mission_id=mission_id or new_id("mission"),
        spec=MissionSpec(
            title="Test Mission",
            objective="Test evaluation scoring",
            risk_level=risk_level,
        ),
        state=state,
        trace_id=new_id("trace"),
        rollback_point=rollback_point,
        result=result or {},
    )


# ── basic evaluate() scoring ─────────────────────────────────────────


class TestEvaluateBasic:
    """Core scoring logic — no idempotency key (plain save_record path)."""

    def test_full_pass_evaluation(self) -> None:
        """Mission with report, EVALUATION state, low risk, high evidence/tools → passed."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            risk_level=RiskLevel.R1,
            rollback_point="rollback_abc",
            result={"report_path": "/tmp/report.md"},
        )

        result = engine.evaluate(
            mission,
            evidence_count=6,
            tool_count=3,
            input_tokens=200,
            output_tokens=300,
        )

        # All scores should be >= 0.9 → passed=True
        assert result.mission_id == mission.mission_id
        assert result.correctness == 1.0  # has report + EVALUATION state
        assert result.reliability == 1.0  # tool_count > 0, evidence_count > 0
        assert result.safety == 1.0       # R1 is in {R0, R1, R2}
        assert result.evidence_coverage == 1.0  # 6 >= 4
        assert result.token_efficiency == 1.0   # 200+300=500 ≤ 500
        assert result.cost_score == 1.0         # 500 < 5000
        assert result.recovery_rate == 1.0      # rollback_point present
        assert result.passed is True
        assert result.evaluation_id.startswith("eval_") or "eval_" in result.evaluation_id

    def test_mission_without_report(self) -> None:
        """No report_path in result → correctness=0.5."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        result = engine.evaluate(mission, evidence_count=2, tool_count=1,
                                 input_tokens=100, output_tokens=100)

        assert result.correctness == 0.5
        assert result.passed is False  # correctness=0.5 < 0.9

    def test_mission_not_in_eval_or_completed_state(self) -> None:
        """State is Execution → correctness=0.5 even with report."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.EXECUTION,
            result={"report_path": "/tmp/r.md"},
        )

        result = engine.evaluate(mission, evidence_count=0, tool_count=0,
                                 input_tokens=0, output_tokens=0)

        assert result.correctness == 0.5
        assert result.passed is False

    def test_completed_state_passes_correctness(self) -> None:
        """COMPLETED state counts for correctness check."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.COMPLETED,
            risk_level=RiskLevel.R0,
            result={"report_path": "r.md"},
        )

        result = engine.evaluate(mission, evidence_count=4, tool_count=2,
                                 input_tokens=100, output_tokens=200)

        assert result.correctness == 1.0
        assert result.passed is True

    def test_high_risk_level_fails_safety(self) -> None:
        """R3 risk → safety=0.0 → passed=False."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            risk_level=RiskLevel.R3,
            result={"report_path": "r.md"},
        )

        result = engine.evaluate(mission, evidence_count=5, tool_count=2,
                                 input_tokens=50, output_tokens=100)

        assert result.safety == 0.0
        assert result.passed is False

    def test_r4_risk_fails_safety(self) -> None:
        """R4 risk → safety=0.0."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            risk_level=RiskLevel.R4,
            result={"report_path": "r.md"},
        )

        result = engine.evaluate(mission, evidence_count=1, tool_count=1,
                                 input_tokens=0, output_tokens=0)

        assert result.safety == 0.0


class TestEvaluateEdgeCases:
    """Boundary and edge-case scoring."""

    def test_zero_evidence_zero_tools(self) -> None:
        """evidence_count=0 and tool_count=0 → reliability=0.5."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        result = engine.evaluate(mission, evidence_count=0, tool_count=0,
                                 input_tokens=10, output_tokens=20)

        assert result.reliability == 0.5
        assert result.passed is False

    def test_tools_but_no_evidence(self) -> None:
        """tool_count > 0 but evidence_count=0 → reliability=0.5."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        result = engine.evaluate(mission, evidence_count=0, tool_count=5,
                                 input_tokens=50, output_tokens=50)

        assert result.reliability == 0.5

    def test_evidence_but_no_tools(self) -> None:
        """evidence_count > 0 but tool_count=0 → reliability=0.5."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        result = engine.evaluate(mission, evidence_count=3, tool_count=0,
                                 input_tokens=50, output_tokens=50)

        assert result.reliability == 0.5

    def test_evidence_coverage_scaling(self) -> None:
        """evidence_coverage = evidence_count/4, capped at 1.0."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        # 0 → 0.0
        r0 = engine.evaluate(mission, evidence_count=0, tool_count=1,
                             input_tokens=10, output_tokens=20)
        assert r0.evidence_coverage == 0.0

        # 2 → 0.5
        r2 = engine.evaluate(mission, evidence_count=2, tool_count=1,
                             input_tokens=10, output_tokens=20)
        assert r2.evidence_coverage == 0.5

        # 3 → 0.75
        r3 = engine.evaluate(mission, evidence_count=3, tool_count=1,
                             input_tokens=10, output_tokens=20)
        assert r3.evidence_coverage == 0.75

        # 4 → 1.0
        r4 = engine.evaluate(mission, evidence_count=4, tool_count=1,
                             input_tokens=10, output_tokens=20)
        assert r4.evidence_coverage == 1.0

        # 10 → 1.0 (capped)
        r10 = engine.evaluate(mission, evidence_count=10, tool_count=1,
                              input_tokens=10, output_tokens=20)
        assert r10.evidence_coverage == 1.0

    def test_token_efficiency_scaling(self) -> None:
        """token_efficiency = 500 / max(500, total_tokens)."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        # total 100 → 1.0 (under 500 cap)
        r = engine.evaluate(mission, evidence_count=1, tool_count=1,
                            input_tokens=50, output_tokens=50)
        assert r.token_efficiency == 1.0

        # total 1000 → 500/1000 = 0.5
        r = engine.evaluate(mission, evidence_count=1, tool_count=1,
                            input_tokens=500, output_tokens=500)
        assert r.token_efficiency == 0.5

        # total 5000 → 500/5000 = 0.1
        r = engine.evaluate(mission, evidence_count=1, tool_count=1,
                            input_tokens=2500, output_tokens=2500)
        assert r.token_efficiency == 0.1

    def test_cost_score_threshold(self) -> None:
        """cost_score = 1.0 if tokens < 5000 else 0.8."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        # under threshold
        r = engine.evaluate(mission, evidence_count=1, tool_count=1,
                            input_tokens=2000, output_tokens=2999)
        assert r.cost_score == 1.0

        # exactly 5000 → 0.8
        r = engine.evaluate(mission, evidence_count=1, tool_count=1,
                            input_tokens=2500, output_tokens=2500)
        assert r.cost_score == 0.8

        # over threshold
        r = engine.evaluate(mission, evidence_count=1, tool_count=1,
                            input_tokens=3000, output_tokens=3000)
        assert r.cost_score == 0.8

    def test_no_rollback_point(self) -> None:
        """No rollback_point → recovery_rate=0.5."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION, rollback_point=None)

        result = engine.evaluate(mission, evidence_count=1, tool_count=1,
                                 input_tokens=50, output_tokens=50)
        assert result.recovery_rate == 0.5

    def test_rollback_point_yields_full_recovery(self) -> None:
        """rollback_point present → recovery_rate=1.0."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            rollback_point="rp_123",
        )

        result = engine.evaluate(mission, evidence_count=1, tool_count=1,
                                 input_tokens=50, output_tokens=50)
        assert result.recovery_rate == 1.0

    def test_notes_are_populated(self) -> None:
        """Every evaluation result includes a deterministic note."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        result = engine.evaluate(mission, evidence_count=1, tool_count=1,
                                 input_tokens=50, output_tokens=50)
        assert len(result.notes) >= 1
        assert any("Deterministic MVP" in n for n in result.notes)


# ── idempotency ──────────────────────────────────────────────────────


class TestEvaluateIdempotency:
    """Idempotency: same key + same mission → cached result, no double write."""

    def test_idempotency_returns_same_result(self) -> None:
        """Two calls with the same idempotency_key return the same EvaluationResult."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            risk_level=RiskLevel.R1,
            rollback_point="rp",
            result={"report_path": "/tmp/r.md"},
        )

        key = "mission-run-001"
        r1 = engine.evaluate(mission, evidence_count=6, tool_count=3,
                             input_tokens=100, output_tokens=200,
                             idempotency_key=key)

        # Second call — should hit the idempotency path
        r2 = engine.evaluate(mission, evidence_count=6, tool_count=3,
                             input_tokens=100, output_tokens=200,
                             idempotency_key=key)

        assert r1.evaluation_id == r2.evaluation_id
        assert r1.mission_id == r2.mission_id
        assert r1.correctness == r2.correctness
        assert r1.reliability == r2.reliability
        assert r1.safety == r2.safety
        assert r1.evidence_coverage == r2.evidence_coverage
        assert r1.passed == r2.passed
        assert r1.idempotency_key == key
        assert r2.idempotency_key == key

    def test_idempotency_different_args_returns_cached(self) -> None:
        """Second call with different args is ignored — cached result returned."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            risk_level=RiskLevel.R1,
            rollback_point="rp",
            result={"report_path": "r.md"},
        )

        key = "run-002"
        r1 = engine.evaluate(mission, evidence_count=6, tool_count=3,
                             input_tokens=100, output_tokens=200,
                             idempotency_key=key)

        # Different args — but same key → should return cached r1
        r2 = engine.evaluate(mission, evidence_count=0, tool_count=0,
                             input_tokens=99999, output_tokens=99999,
                             idempotency_key=key)

        assert r1.evaluation_id == r2.evaluation_id
        # Evidence coverage from the CACHED (first) result, not the second args
        assert r1.evidence_coverage == r2.evidence_coverage

    def test_idempotency_different_missions_raise_conflict(self) -> None:
        """Same idempotency_key on different missions → ValueError.

        When the cached idempotency record's mission_id doesn't match,
        save_records_atomically raises atomic_record_identity_conflict, and
        the subsequent winner-lookup fails because the winner belongs to a
        different mission — re-raising the original error.
        """
        store = _make_store()
        engine = _make_engine(store)

        m1 = _make_mission(
            mission_id="mission-aaa",
            state=MissionState.EVALUATION,
            result={"report_path": "r.md"},
        )
        m2 = _make_mission(
            mission_id="mission-bbb",
            state=MissionState.EVALUATION,
            result={"report_path": "r.md"},
        )

        key = "shared-key"
        engine.evaluate(m1, evidence_count=4, tool_count=2,
                        input_tokens=100, output_tokens=100,
                        idempotency_key=key)

        with pytest.raises(ValueError, match="atomic_record_identity_conflict"):
            engine.evaluate(m2, evidence_count=4, tool_count=2,
                            input_tokens=100, output_tokens=100,
                            idempotency_key=key)

    def test_no_idempotency_key_no_cache(self) -> None:
        """Without idempotency_key, each call creates a fresh evaluation."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        r1 = engine.evaluate(mission, evidence_count=1, tool_count=1,
                             input_tokens=50, output_tokens=50)
        r2 = engine.evaluate(mission, evidence_count=1, tool_count=1,
                             input_tokens=50, output_tokens=50)

        # Different evaluation_id each time (no key → no idempotency)
        assert r1.evaluation_id != r2.evaluation_id

    def test_idempotency_publishes_event_on_cache_hit(self) -> None:
        """Cache hit still calls _publish_evaluation — event is deduplicated
        by EventBus (same idempotency key), so count stays 1."""
        store = _make_store()
        bus = EventBus(store)
        engine = EvaluationEngine(store, bus)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            result={"report_path": "r.md"},
        )

        key = "event-publish-test"
        engine.evaluate(mission, evidence_count=4, tool_count=2,
                        input_tokens=100, output_tokens=100,
                        idempotency_key=key)

        # Cache hit — should not raise, and should return cached result
        r2 = engine.evaluate(mission, evidence_count=4, tool_count=2,
                             input_tokens=100, output_tokens=100,
                             idempotency_key=key)

        events = bus.replay(mission.mission_id)
        evaluated = [e for e in events if e["event_type"] == "mission.evaluated"]
        # Event is deduplicated by EventBus idempotency — exactly one event
        assert len(evaluated) == 1
        assert r2.correctness == 1.0


# ── list() ───────────────────────────────────────────────────────────


class TestList:
    """EvaluationEngine.list() returns stored evaluations."""

    def test_list_returns_evaluations(self) -> None:
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(state=MissionState.EVALUATION)

        engine.evaluate(mission, evidence_count=1, tool_count=1,
                        input_tokens=50, output_tokens=50)

        results = engine.list()
        assert len(results) >= 1
        ev = results[0]
        assert ev["mission_id"] == mission.mission_id
        assert "correctness" in ev
        assert "reliability" in ev

    def test_list_filters_by_mission_id(self) -> None:
        store = _make_store()
        engine = _make_engine(store)

        m1 = _make_mission(mission_id="m-one", state=MissionState.EVALUATION)
        m2 = _make_mission(mission_id="m-two", state=MissionState.EVALUATION)

        engine.evaluate(m1, evidence_count=1, tool_count=1,
                        input_tokens=50, output_tokens=50)
        engine.evaluate(m2, evidence_count=1, tool_count=1,
                        input_tokens=50, output_tokens=50)

        # Filter for m1 only
        results = engine.list(mission_id="m-one")
        assert len(results) == 1
        assert results[0]["mission_id"] == "m-one"

    def test_list_empty_when_no_evaluations(self) -> None:
        store = _make_store()
        engine = _make_engine(store)

        results = engine.list()
        assert results == []


# ── failed mission evaluation ────────────────────────────────────────


class TestFailedMissionEvaluation:
    """Evaluating a mission in FAILED state."""

    def test_failed_mission(self) -> None:
        """FAILED state → not in {EVALUATION, COMPLETED} → correctness=0.5."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.FAILED,
            result={"report_path": "r.md"},
        )

        result = engine.evaluate(mission, evidence_count=0, tool_count=0,
                                 input_tokens=0, output_tokens=0)

        assert result.correctness == 0.5
        assert result.passed is False

    def test_blocked_mission(self) -> None:
        """BLOCKED state → not in {EVALUATION, COMPLETED} → correctness=0.5."""
        store = _make_store()
        engine = _make_engine(store)
        mission = _make_mission(
            state=MissionState.BLOCKED,
            result={"report_path": "r.md"},
        )

        result = engine.evaluate(mission, evidence_count=2, tool_count=1,
                                 input_tokens=100, output_tokens=200)

        assert result.correctness == 0.5


# ── event publication ────────────────────────────────────────────────


class TestEventPublication:
    """evaluate() publishes mission.evaluated events."""

    def test_evaluate_publishes_event(self) -> None:
        store = _make_store()
        bus = EventBus(store)
        engine = EvaluationEngine(store, bus)
        mission = _make_mission(
            state=MissionState.EVALUATION,
            result={"report_path": "r.md"},
        )

        engine.evaluate(mission, evidence_count=4, tool_count=2,
                        input_tokens=100, output_tokens=100)

        events = bus.replay(mission.mission_id)
        evaluated_events = [e for e in events if e["event_type"] == "mission.evaluated"]
        assert len(evaluated_events) >= 1
        evt = evaluated_events[0]
        assert evt["aggregate_id"] == mission.mission_id
        assert evt["aggregate_type"] == "mission"
        assert evt["actor"] == "evaluation_engine"

    def test_evaluate_publishes_event_without_idempotency_key(self) -> None:
        """Event is published even without an idempotency_key."""
        store = _make_store()
        bus = EventBus(store)
        engine = EvaluationEngine(store, bus)
        mission = _make_mission(state=MissionState.EVALUATION)

        engine.evaluate(mission, evidence_count=1, tool_count=1,
                        input_tokens=50, output_tokens=50)

        events = bus.replay(mission.mission_id)
        evaluated = [e for e in events if e["event_type"] == "mission.evaluated"]
        assert len(evaluated) >= 1
