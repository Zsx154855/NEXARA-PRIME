"""KMA Phase 2 — Capability History Persistence Tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.capabilities import CapabilityRegistry
from nexara_prime.db import SQLiteStore


@pytest.fixture
def store():
    db = Path(tempfile.mkdtemp()) / "test_cap.db"
    return SQLiteStore(db)


@pytest.fixture
def registry(store):
    return CapabilityRegistry(store=store)


class TestCapabilityPersistence:
    def test_record_history_persists(self, registry, store):
        record = registry.record_history(
            capability_id="skill.test",
            mission_id="m1",
            provider="deepseek-v4-pro",
            model="deepseek-v4-pro",
            success=True,
            latency_ms=100.0,
            input_tokens=500,
            output_tokens=200,
            cost=0.003,
            idempotency_key="cap-key-1",
        )
        assert record.record_id.startswith("caphist_")
        history = registry.get_history("skill.test")
        assert len(history) >= 1
        # Verify actual store persistence
        store_records = store.list_records("capability_history")
        assert any(
            r.get("capability_id") == "skill.test" for r in store_records
        ), "Record not persisted to SQLiteStore"

    def test_record_history_idempotent(self, registry):
        _r1 = registry.record_history(
            capability_id="skill.dup", success=True,
            idempotency_key="dup-key",
        )
        _r2 = registry.record_history(
            capability_id="skill.dup", success=True,
            idempotency_key="dup-key",
        )
        history = registry.get_history("skill.dup")
        assert len(history) == 1

    def test_update_score_persists(self, registry):
        registry.register_v2("skill.scored", "Scored Cap")
        score = registry.update_score(
            "skill.scored", True, 100.0, 0.005,
            provider="mock", model="mock-v1",
            mission_id="m2", idempotency_key="score-key",
        )
        assert score is not None
        history = registry.get_history("skill.scored")
        assert len(history) >= 1

    def test_get_aggregates(self, registry):
        registry.record_history(capability_id="c1", success=True)
        registry.record_history(capability_id="c1", success=False)
        agg = registry.get_aggregates()
        assert agg["total_history_records"] >= 2
        assert agg["persistence_enabled"] is True

    def test_get_history_all(self, registry):
        registry.record_history(capability_id="c1", success=True)
        registry.record_history(capability_id="c2", success=False)
        all_h = registry.get_history()
        assert len(all_h) >= 2


class TestRestartRecovery:
    def test_scores_recomputed_on_new_instance(self, store):
        reg1 = CapabilityRegistry(store=store)
        reg1.register_v2("skill.recover", "Recovery Cap")
        reg1.record_history(
            capability_id="skill.recover", success=True,
            latency_ms=50.0, cost=0.001, idempotency_key="rk1",
        )
        reg1.record_history(
            capability_id="skill.recover", success=True,
            latency_ms=60.0, cost=0.002, idempotency_key="rk2",
        )

        reg2 = CapabilityRegistry(store=store)
        score = reg2.get_score("skill.recover")
        assert score is not None
        assert score.historical_success_rate == 1.0
        assert score.evidence_count >= 0


class TestInvocationCounting:
    """Each invocation counts once regardless of evidence count."""

    def test_single_invocation_with_multiple_evidence(self, store):
        reg = CapabilityRegistry(store=store)
        reg.register_v2("skill.multi", "Multi Evidence Cap")
        score = reg.update_score(
            "skill.multi", True, 100.0, 0.005,
            evidence_ids=["e1", "e2", "e3"],
            provider="mock", model="mock-v1",
            mission_id="m_multi", idempotency_key="multi-key",
        )
        assert score is not None
        history = reg.get_history("skill.multi")
        # Only one history entry per invocation, regardless of evidence count
        assert len(history) == 1
        # Evidence references stored in the outcome dict
        assert history[0].get("evidence_ids") == ["e1", "e2", "e3"]

    def test_invocation_without_evidence(self, store):
        reg = CapabilityRegistry(store=store)
        reg.register_v2("skill.noev", "No Evidence Cap")
        score = reg.update_score(
            "skill.noev", True, 50.0, 0.001,
            provider="mock", model="mock-v1",
            mission_id="m_noev", idempotency_key="noev-key",
        )
        assert score is not None
        history = reg.get_history("skill.noev")
        assert len(history) == 1

    def test_multiple_invocations_count_separately(self, store):
        reg = CapabilityRegistry(store=store)
        reg.register_v2("skill.seq", "Sequential Cap")
        reg.update_score(
            "skill.seq", True, 80.0, 0.002,
            evidence_ids=["a1"],
            provider="mock", model="mock-v1",
            mission_id="m_seq", idempotency_key="seq1",
        )
        reg.update_score(
            "skill.seq", True, 90.0, 0.003,
            evidence_ids=["a2", "a3"],
            provider="mock", model="mock-v1",
            mission_id="m_seq", idempotency_key="seq2",
        )
        history = reg.get_history("skill.seq")
        assert len(history) == 2  # each invocation is one record


class TestCapabilityIdempotentReplay:
    """P2 Codex: replay returns original record, count unchanged, no score side effects."""

    def test_replay_returns_original_record(self, store):
        """Write A, write B, replay A → returns A, B untouched."""
        reg = CapabilityRegistry(store=store)
        reg.register_v2("skill.replay", "Replay Cap")

        # Write A
        a1 = reg.record_history(
            capability_id="skill.replay",
            mission_id="m_replay",
            success=True,
            latency_ms=100.0,
            cost=0.005,
            idempotency_key="replay-key-A",
        )
        assert a1.record_id.startswith("caphist_")

        # Write B
        b1 = reg.record_history(
            capability_id="skill.replay",
            mission_id="m_replay",
            success=False,
            latency_ms=200.0,
            cost=0.010,
            idempotency_key="replay-key-B",
        )
        assert b1.record_id.startswith("caphist_")

        history_before = reg.get_history("skill.replay")
        assert len(history_before) == 2

        # Replay A — must return the original record
        a2 = reg.record_history(
            capability_id="skill.replay",
            mission_id="m_replay",
            success=True,
            latency_ms=100.0,
            cost=0.005,
            idempotency_key="replay-key-A",
        )
        # Replay returns the same record_id, not a new one
        assert a2.record_id == a1.record_id
        assert a2.success == a1.success
        assert a2.latency_ms == a1.latency_ms
        assert a2.cost == a1.cost

        # Count unchanged — B is still there, no extra entries
        history_after = reg.get_history("skill.replay")
        assert len(history_after) == 2
        assert history_after[0].get("idempotency_key") == "replay-key-A"
        assert history_after[1].get("idempotency_key") == "replay-key-B"

    def test_replay_no_score_side_effects(self, store):
        """update_score replay must not change count or score."""
        reg = CapabilityRegistry(store=store)
        reg.register_v2("skill.noside", "No Side Effect Cap")

        # First update
        s1 = reg.update_score(
            "skill.noside", True, 120.0, 0.003,
            provider="mock", model="mock-v1",
            mission_id="m_noside", idempotency_key="noside-key",
            evidence_ids=["e_x"],
        )
        assert s1 is not None
        count_before = len(reg.get_history("skill.noside"))
        assert count_before == 1

        # Replay same key — must not create a new entry
        s2 = reg.update_score(
            "skill.noside", True, 120.0, 0.003,
            provider="mock", model="mock-v1",
            mission_id="m_noside", idempotency_key="noside-key",
            evidence_ids=["e_x"],
        )
        assert s2 is not None
        count_after = len(reg.get_history("skill.noside"))
        assert count_after == 1, "replay must not add a new history entry"

        # Score unchanged
        assert s2.historical_success_rate == s1.historical_success_rate
        assert s2.evidence_count == s1.evidence_count
        assert s2.confidence == s1.confidence
