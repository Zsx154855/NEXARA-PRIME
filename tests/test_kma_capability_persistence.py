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
    def test_record_history_persists(self, registry):
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
