"""G3-C: TelemetryService Contract Tests."""
from __future__ import annotations

import pytest

from nexara_prime.telemetry import TelemetryService, TelemetrySnapshot


class FakeStore:
    def execute(self, *a, **kw): return None
    def fetchone(self, *a, **kw): return None
    def fetchall(self, *a, **kw): return []
    def commit(self, *a, **kw): pass


class TestTelemetryService:
    @pytest.fixture
    def service(self) -> TelemetryService:
        from nexara_prime.events import EventBus
        store = FakeStore()
        return TelemetryService(EventBus(store))  # type: ignore[arg-type]

    def test_starts_and_stops(self, service: TelemetryService) -> None:
        assert not service.running
        service.start()
        assert service.running
        service.stop()
        assert not service.running

    def test_health_reflects_state(self, service: TelemetryService) -> None:
        service.start()
        h = service.health()
        assert h["service"] == "telemetry"
        assert h["status"] == "healthy"

    def test_record_health_tracks_components(self, service: TelemetryService) -> None:
        service.start()
        service.record_health("connector.http", "healthy", "ok")
        service.record_health("connector.db", "degraded", "slow")
        snap = service.snapshot()
        assert snap.status == "degraded"
        assert len(snap.health_checks) == 2

    def test_snapshot_when_healthy(self, service: TelemetryService) -> None:
        service.start()
        service.record_health("test", "healthy")
        snap = service.snapshot()
        assert snap.status == "healthy"
        assert isinstance(snap, TelemetrySnapshot)

    def test_health_checks_capped_at_100(self, service: TelemetryService) -> None:
        service.start()
        for i in range(120):
            service.record_health(f"comp_{i}", "healthy")
        assert len(service._health_checks) <= 100

    def test_stopped_service_reports_stopped(self, service: TelemetryService) -> None:
        h = service.health()
        assert h["status"] == "stopped"
