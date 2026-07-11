from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .models import ModelRoutingDecision, new_id, now_iso


# ── Provider definitions ─────────────────────────────────────────────────────


@dataclass
class ProviderInfo:
    """Static metadata about a supported model provider."""

    name: str
    model_name: str
    tier: str  # "flash" or "pro"
    supports_context_size: int
    typical_latency_ms: int
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float


_PROVIDERS: dict[str, ProviderInfo] = {
    "mock": ProviderInfo(
        name="mock",
        model_name="mock",
        tier="flash",
        supports_context_size=32_000,
        typical_latency_ms=10,
        cost_per_1k_input_tokens=0.0,
        cost_per_1k_output_tokens=0.0,
    ),
    "deepseek-v4-flash": ProviderInfo(
        name="deepseek-v4-flash",
        model_name="deepseek-v4-flash",
        tier="flash",
        supports_context_size=64_000,
        typical_latency_ms=800,
        cost_per_1k_input_tokens=0.00015,
        cost_per_1k_output_tokens=0.00060,
    ),
    "deepseek-v4-pro": ProviderInfo(
        name="deepseek-v4-pro",
        model_name="deepseek-v4-pro",
        tier="pro",
        supports_context_size=128_000,
        typical_latency_ms=2000,
        cost_per_1k_input_tokens=0.00200,
        cost_per_1k_output_tokens=0.00800,
    ),
}


# ── Circuit Breaker ──────────────────────────────────────────────────────────


@dataclass
class CircuitBreakerState:
    """Per-provider circuit breaker tracking failure count and open state."""

    failure_count: int = 0
    open: bool = False
    opened_at: float = 0.0


class CircuitBreaker:
    """Tracks failure counts per provider.  When a provider exceeds
    `threshold` consecutive failures the breaker opens and stays open for
    `timeout_s` seconds, after which it auto-resets on the next check."""

    def __init__(self, threshold: int = 3, timeout_s: int = 60) -> None:
        self._threshold = threshold
        self._timeout_s = timeout_s
        self._states: dict[str, CircuitBreakerState] = {}

    def _get(self, provider: str) -> CircuitBreakerState:
        if provider not in self._states:
            self._states[provider] = CircuitBreakerState()
        return self._states[provider]

    def is_open(self, provider: str) -> bool:
        state = self._get(provider)
        if not state.open:
            return False
        # Auto-reset after timeout
        if time.monotonic() - state.opened_at >= self._timeout_s:
            state.open = False
            state.failure_count = 0
            return False
        return True

    def record_success(self, provider: str) -> None:
        state = self._get(provider)
        state.failure_count = 0
        state.open = False

    def record_failure(self, provider: str) -> None:
        state = self._get(provider)
        state.failure_count += 1
        if state.failure_count >= self._threshold:
            state.open = True
            state.opened_at = time.monotonic()


# ── Model Router ─────────────────────────────────────────────────────────────


class ModelRouter:
    """Routes mission requests to the most appropriate model provider based on
    complexity, risk, context size, latency targets, and token budget.

    Supports three providers: `mock`, `deepseek-v4-flash`, `deepseek-v4-pro`.
    Uses a circuit breaker to fall back when providers are failing.

    Rules:
      - S0 / S1 missions default to flash (or mock when no budget).
      - S2 / S3 missions default to pro.
      - Context > 64K tokens forces pro.
      - Latency target < 2000 ms forces flash.
      - Circuit breaker redirects to fallback when primary is open.

    Usage::

        router = ModelRouter()
        decision = router.route("mission-001", complexity=0.1, risk=0.1, ...)
        # ... call provider ...
        router.track_result(decision.selected_provider, success=True, ...)
    """

    def __init__(self, circuit_breaker_threshold: int = 3, circuit_breaker_timeout_s: int = 60) -> None:
        self.breaker = CircuitBreaker(
            threshold=circuit_breaker_threshold,
            timeout_s=circuit_breaker_timeout_s,
        )

    # ── Available providers ──────────────────────────────────────────────────

    @property
    def available_providers(self) -> dict[str, ProviderInfo]:
        return dict(_PROVIDERS)

    # ── Route ────────────────────────────────────────────────────────────────

    def route(
        self,
        mission_id: str,
        complexity: float,
        risk: float,
        context_size: int,
        latency_target_ms: int,
        token_budget: int,
        provider_health: dict[str, bool] | None = None,  # external liveness
    ) -> ModelRoutingDecision:
        """Select the best model provider for the given mission parameters.

        Parameters
        ----------
        mission_id : str
            Unique mission identifier.
        complexity : float
            Complexity score from MissionTriageEngine (0.0–1.0).
        risk : float
            Risk score from MissionTriageEngine (0.0–1.0).
        context_size : int
            Estimated context size in tokens.
        latency_target_ms : int
            Maximum acceptable latency in milliseconds.
        token_budget : int
            Total token budget allocated to the mission.
        provider_health : dict[str, bool] | None
            External liveness check per provider (True = healthy).  When
            provided, unhealthy providers are skipped even if the breaker is
            closed.

        Returns
        -------
        ModelRoutingDecision with the selected provider and fallback info.
        """
        # 1. Determine the preferred tier from mission characteristics
        preferred_tier = self._choose_tier(complexity, risk, context_size, latency_target_ms)

        # 2. Rank providers by tier match, cost, and latency
        candidates = self._rank_candidates(preferred_tier, context_size, latency_target_ms)

        # 3. Apply circuit breaker and health checks, pick the first healthy
        primary, fallback = self._select_healthy(
            candidates, provider_health or {},
        )

        # 4. Rough cost estimate
        estimated_tokens = min(token_budget, context_size + 4000)  # assume ~4K output
        estimated_cost = self._estimate_cost(primary, estimated_tokens)

        alternatives = [
            {"provider": p.name, "model": p.model_name, "tier": p.tier}
            for p in candidates[:5]
            if p.name != primary.name
        ]

        record = ModelRoutingDecision(
            mission_id=mission_id,
            selected_provider=primary.name,
            selected_model=primary.model_name,
            reason=(
                f"Tier={preferred_tier}, complexity={complexity:.2f}, risk={risk:.2f}, "
                f"context={context_size}, latency_target={latency_target_ms}ms → "
                f"selected {primary.name}"
            ),
            alternatives=alternatives,
            estimated_tokens=estimated_tokens,
            estimated_cost=estimated_cost,
            fallback=fallback.name if fallback else "",
            created_at=now_iso(),
        )
        return record

    # ── Track result ─────────────────────────────────────────────────────────

    def track_result(
        self,
        provider: str,
        success: bool,
        latency_ms: int,
        tokens: int,
    ) -> None:
        """Report a provider result so the circuit breaker can update its state.

        Call this after each model invocation.
        """
        if success:
            self.breaker.record_success(provider)
        else:
            self.breaker.record_failure(provider)

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _choose_tier(
        complexity: float,
        risk: float,
        context_size: int,
        latency_target_ms: int,
    ) -> str:
        """Choose 'flash' or 'pro' based on mission characteristics.

        Rules (in priority order):
          1. context_size > 64K → pro
          2. latency_target < 2000 ms → flash
          3. complexity >= 0.4 or risk >= 0.4 → pro
          4. default → flash
        """
        if context_size > 64_000:
            return "pro"
        if latency_target_ms < 2000:
            return "flash"
        if complexity >= 0.4 or risk >= 0.4:
            return "pro"
        return "flash"

    def _rank_candidates(
        self,
        preferred_tier: str,
        context_size: int,
        latency_target_ms: int,
    ) -> list[ProviderInfo]:
        """Rank supported providers: exact tier match first, then cost
        ascending, then latency ascending."""
        candidates = list(_PROVIDERS.values())

        def sort_key(p: ProviderInfo) -> tuple:
            tier_bonus = 0 if p.tier == preferred_tier else 1
            cost = p.cost_per_1k_input_tokens + p.cost_per_1k_output_tokens
            latency_penalty = max(0, p.typical_latency_ms - latency_target_ms)
            return (tier_bonus, cost, latency_penalty)

        candidates.sort(key=sort_key)
        return candidates

    def _select_healthy(
        self,
        candidates: list[ProviderInfo],
        health: dict[str, bool],
    ) -> tuple[ProviderInfo, ProviderInfo | None]:
        """Pick the first candidate that is neither circuit-broken nor
        externally unhealthy.  Returns (primary, fallback)."""
        primary: ProviderInfo | None = None
        fallback: ProviderInfo | None = None

        for p in candidates:
            # Check external health (if provided)
            if health and p.name in health and not health[p.name]:
                if fallback is None:
                    fallback = p
                continue
            # Check circuit breaker
            if self.breaker.is_open(p.name):
                if fallback is None:
                    fallback = p
                continue
            # Healthy
            if primary is None:
                primary = p
            elif fallback is None:
                fallback = p

        # If no healthy candidate found at all, fall back to mock
        if primary is None:
            primary = _PROVIDERS["mock"]
        return primary, fallback

    @staticmethod
    def _estimate_cost(provider: ProviderInfo, tokens: int) -> float:
        """Rough per-invocation cost estimate (input + output * 1K ratio)."""
        input_cost = (tokens / 1000.0) * provider.cost_per_1k_input_tokens
        output_cost = ((tokens * 0.25) / 1000.0) * provider.cost_per_1k_output_tokens
        return round(input_cost + output_cost, 8)
