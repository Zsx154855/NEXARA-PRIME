"""G3-D: KnowledgeService Contract Tests."""
from __future__ import annotations

import pytest

from nexara_prime.knowledge import KnowledgeService


class FakeStore:
    def execute(self, *a, **kw): return None
    def fetchone(self, *a, **kw): return None
    def fetchall(self, *a, **kw): return []
    def list_records(self, *a, **kw): return []
    def commit(self, *a, **kw): pass


class TestKnowledgeService:
    @pytest.fixture
    def service(self) -> KnowledgeService:
        from nexara_prime.events import EventBus
        from nexara_prime.memory import MemoryKernel
        store = FakeStore()
        events = EventBus(store)  # type: ignore[arg-type]
        memory = MemoryKernel(store, events)  # type: ignore[arg-type]
        return KnowledgeService(memory)

    def test_starts_and_stops(self, service: KnowledgeService) -> None:
        assert not service.running
        service.start()
        assert service.running
        service.stop()
        assert not service.running

    def test_health_reflects_state(self, service: KnowledgeService) -> None:
        service.start()
        h = service.health()
        assert h["service"] == "knowledge"
        assert h["status"] == "healthy"
        assert h["memory_available"]

    def test_query_returns_list(self, service: KnowledgeService) -> None:
        service.start()
        results = service.query()
        assert isinstance(results, list)

    def test_query_with_kind_filter(self, service: KnowledgeService) -> None:
        service.start()
        results = service.query(kind_filter="fact")
        assert isinstance(results, list)

    def test_query_candidates_returns_list(self, service: KnowledgeService) -> None:
        service.start()
        candidates = service.query_candidates()
        assert isinstance(candidates, list)

    def test_stopped_service_reports_stopped(self, service: KnowledgeService) -> None:
        h = service.health()
        assert h["status"] == "stopped"

    def test_memory_module_untouched(self) -> None:
        from nexara_prime import memory as mem_mod
        assert hasattr(mem_mod, "MemoryKernel")
