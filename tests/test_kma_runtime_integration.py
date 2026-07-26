"""KMA Phase 2 — Runtime Integration & Call Chain Tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.models import MemoryKind


@pytest.fixture
def runtime():
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=0,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


class TestEvidenceStoreAPIIntegration:
    def test_get_by_id_after_mission_create(self, runtime):
        mission = runtime.create_mission("integration test")
        evidence_list = runtime.evidence.list(mission.mission_id)
        assert len(evidence_list) >= 1
        artifact = runtime.evidence.get_by_id(evidence_list[0]["evidence_id"])
        assert artifact.mission_id == mission.mission_id

    def test_receipt_status_integrated(self, runtime):
        mission = runtime.create_mission("receipt integration")
        status = runtime.evidence.receipt_status(mission.mission_id)
        assert "status" in status
        assert "chain_intact" in status


class TestCapabilityRegistryIntegration:
    def test_registry_with_store(self, runtime):
        from nexara_prime.capabilities import CapabilityRegistry
        cr = CapabilityRegistry(store=runtime.store)
        cr.register_v2("integration.cap", "Integration Cap")
        rec = cr.record_history(
            capability_id="integration.cap",
            success=True, latency_ms=50.0, cost=0.001,
            idempotency_key="int-key",
        )
        assert rec.record_id.startswith("caphist_")
        assert len(cr.get_history("integration.cap")) >= 1
        agg = cr.get_aggregates()
        assert agg["total_history_records"] >= 1
        assert agg["persistence_enabled"] is True


class TestNoRawStoreBypassIntegration:
    def test_runtime_inspect_uses_receipt_status(self, runtime):
        import inspect
        source = inspect.getsource(runtime.inspect_mission)
        # Verify the old self-judgment code is gone
        assert "receipt_present = any(" not in source
        assert "evidence.receipt_status" in source

    def test_get_evidence_by_idempotency_uses_api(self, runtime):
        import inspect
        source = inspect.getsource(runtime._get_evidence_by_idempotency)
        assert "store.find_record" not in source
        assert "evidence.find_by_idempotency" in source


class TestKnowledgeServiceIntegration:
    def test_knowledge_service_with_runtime_memory(self, runtime):
        from nexara_prime.knowledge import KnowledgeService
        ks = KnowledgeService(runtime.memory)
        ks.start()
        _ = ks.validate_commit(
            type("KC", (), {
                "kind": MemoryKind.FACT,
                "key": "k1",
                "content": "c1",
                "trace_id": "t1",
                "mission_id": None,
                "source_evidence_id": None,
                "idempotency_key": None,
                "confidence": 1.0,
                "receipt_id": None,
                "auto_commit": False,
                "provenance": "runtime",
            })()
        )
        pass


class TestProgramStateFix:
    def test_resolve_state_path_fallback(self, runtime):
        from nexara_prime.cli import _resolve_state_path
        result = _resolve_state_path(Path(tempfile.mkdtemp()))
        assert result is None


class TestReceiptChain:
    def test_receipt_chain_with_mission(self, runtime):
        mission = runtime.create_mission("chain test")
        runtime.plan_mission(mission.mission_id)
        runtime.approve_mission(mission.mission_id, approved=True)
        runtime.run_mission(mission.mission_id)
        chain = runtime.evidence.verify_receipt_chain(mission.mission_id)
        status = runtime.evidence.receipt_status(mission.mission_id)
        assert "chain" in chain
        assert "status" in status
