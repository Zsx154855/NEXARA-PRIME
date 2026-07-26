"""KMA Phase 2 — CircuitBreaker Convergence Tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.model_gateway import (
    MockProvider,
    ModelGateway,
)
from nexara_prime.model_router import CircuitBreaker, ModelRouter


class TestCircuitBreakerConsolidation:
    def test_model_gateway_imports_from_router(self):
        """Verify model_gateway.CircuitBreaker IS model_router.CircuitBreaker."""
        from nexara_prime.model_gateway import CircuitBreaker as GW_CB
        from nexara_prime.model_router import CircuitBreaker as MR_CB
        assert GW_CB is MR_CB

    def test_model_gateway_no_local_breaker_class(self):
        """Verify local CircuitBreaker class removed from model_gateway."""
        import nexara_prime.model_gateway as mg
        import inspect
        source = inspect.getsource(mg)
        assert "class CircuitBreaker:" not in source

    def test_connector_breaker_independent(self):
        """Verify connectors/health CircuitBreaker is NOT the same."""
        from nexara_prime.connectors.health import CircuitBreaker as HealthCB
        from nexara_prime.model_router import CircuitBreaker as MR_CB
        assert HealthCB is not MR_CB

    def test_model_gateway_accepts_injected_breaker(self):
        provider = MockProvider()
        breaker = CircuitBreaker()
        gw = ModelGateway(provider, breaker=breaker)
        assert gw.breaker is breaker

    def test_model_gateway_default_breaker(self):
        provider = MockProvider()
        gw = ModelGateway(provider)
        assert gw.breaker is not None
        assert isinstance(gw.breaker, CircuitBreaker)


class TestBreakerBehavior:
    def test_breaker_tracks_failures(self):
        breaker = CircuitBreaker(threshold=3, timeout_s=10)
        assert not breaker.is_open("test-provider")
        breaker.record_failure("test-provider")
        breaker.record_failure("test-provider")
        breaker.record_failure("test-provider")
        assert breaker.is_open("test-provider")

    def test_breaker_recovers_on_success(self):
        breaker = CircuitBreaker()
        breaker.record_failure("p1")
        breaker.record_success("p1")
        assert not breaker.is_open("p1")

    def test_model_gateway_delegates_to_breaker(self):
        provider = MockProvider()
        breaker = CircuitBreaker()
        gw = ModelGateway(provider, breaker=breaker)
        response = gw.complete("system", "task", trace_id="t1")
        assert response.text is not None
        assert response.provider == "mock"
