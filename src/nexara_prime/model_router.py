from __future__ import annotations

import time
from dataclasses import dataclass

from .models import ModelRoutingDecision, now_iso

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
    `timeout_s` seconds, after which it auto-resets on the next check.

    Backward-compatible aliases: `failure_threshold` → `threshold`,
    `cooldown_seconds` → `timeout_s`.
    """

    def __init__(
        self,
        threshold: int = 3,
        timeout_s: int = 60,
        *,
        failure_threshold: int | None = None,
        cooldown_seconds: float | None = None,
    ) -> None:
        self._threshold = (
            failure_threshold if failure_threshold is not None else threshold
        )
        if cooldown_seconds is not None:
            if cooldown_seconds < 0:
                raise ValueError(
                    f"cooldown_seconds must be non-negative, got {cooldown_seconds}"
                )
            self._timeout_s = float(cooldown_seconds)
        else:
            self._timeout_s = float(timeout_s)
        self._states: dict[str, CircuitBreakerState] = {}

    def _get(self, provider: str) -> CircuitBreakerState:
        if provider not in self._states:
            self._states[provider] = CircuitBreakerState()
        return self._states[provider]

    def is_open(self, provider: str) -> bool:
        state = self._get(provider)
        if not state.open:
            return False
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

    def get_state(self, provider: str) -> CircuitBreakerState:
        return self._get(provider)

    # ── Backward-compatible aliases ──

    _DEFAULT_PROVIDER = "default"

    def failure(self) -> None:
        self.record_failure(self._DEFAULT_PROVIDER)

    def success(self) -> None:
        self.record_success(self._DEFAULT_PROVIDER)

    def before_call(self) -> None:
        from .model_gateway import ProviderUnavailable

        if self.is_open(self._DEFAULT_PROVIDER):
            raise ProviderUnavailable("provider_circuit_open")


# ── Model Router ─────────────────────────────────────────────────────────────


class ModelRouter:
    """Routes mission requests via V1 (direct) or V2 (Governed Adaptive Composite).

    V1: Uses tier-based routing with CircuitBreaker.
    V2: Uses CompositeOrchestrationEngine with Portfolio, Profiler, Reroute.

    Backward-compatible: All V1 callers continue to work.
    Enable V2 with: router = ModelRouter(use_composite_v2=True)
    """

    def __init__(
        self,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout_s: int = 60,
        breaker: CircuitBreaker | None = None,
        *,
        use_composite_v2: bool = False,
    ) -> None:
        self.breaker = (
            breaker
            if breaker is not None
            else CircuitBreaker(
                threshold=circuit_breaker_threshold,
                timeout_s=circuit_breaker_timeout_s,
            )
        )
        self._v2_enabled = use_composite_v2
        self._reroute_controller = None  # type: ignore
        if use_composite_v2:
            from .composite_orchestration import CompositeOrchestrationEngine
            from .governed_reroute import GovernedRerouteController
            from .model_portfolio_registry import ModelPortfolioRegistry

            self._portfolio = ModelPortfolioRegistry()
            self._orchestrator = CompositeOrchestrationEngine(self._portfolio)
            self._reroute_controller = GovernedRerouteController()

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
        provider_health: dict[str, bool] | None = None,
    ) -> ModelRoutingDecision:
        """Select the best model provider for the given mission parameters.

        When use_composite_v2=True, dispatches through V2 orchestrator.
        """
        # ── V2 path: route through composite orchestrator ──
        if self._v2_enabled:
            mission = {
                "mission_id": mission_id,
                "objective": f"complexity={complexity:.2f},risk={risk:.2f}",
                "complexity": self._map_complexity(complexity),
                "risk_level": self._map_risk(risk),
                "context_size": context_size,
                "latency_target_ms": latency_target_ms,
                "token_budget": token_budget,
            }
            from .knowledge_anchor import KnowledgeAnchor

            anchors = KnowledgeAnchor()
            result = self._orchestrator.route(mission, anchors)
            # Sync circuit breaker state into portfolio health
            self._sync_breaker_to_portfolio()
            provider = result.primary_entry.provider if result.primary_entry else "mock"
            model = result.primary_entry.model_name if result.primary_entry else "mock"
            return ModelRoutingDecision(
                mission_id=mission_id,
                selected_provider=provider,
                selected_model=model,
                reason=f"V2 {result.mode.value}: {result.reason}",
                alternatives=[],
                estimated_tokens=token_budget,
                estimated_cost=0.0,
                fallback="",
                created_at=now_iso(),
            )

        # ── V1 path (original) ──
        preferred_tier = self._choose_tier(
            complexity, risk, context_size, latency_target_ms
        )
        candidates = self._rank_candidates(
            preferred_tier, context_size, latency_target_ms
        )
        primary, fallback = self._select_healthy(
            candidates, provider_health or {},
        )
        estimated_tokens = min(token_budget, context_size + 4000)
        estimated_cost = self._estimate_cost(primary, estimated_tokens)
        alternatives = [
            {"provider": p.name, "model": p.model_name, "tier": p.tier}
            for p in candidates[:5]
            if p.name != primary.name
        ]
        return ModelRoutingDecision(
            mission_id=mission_id,
            selected_provider=primary.name,
            selected_model=primary.model_name,
            reason=(
                f"Tier={preferred_tier}, complexity={complexity:.2f}, "
                f"risk={risk:.2f}, context={context_size}, "
                f"latency_target={latency_target_ms}ms → selected {primary.name}"
            ),
            alternatives=alternatives,
            estimated_tokens=estimated_tokens,
            estimated_cost=estimated_cost,
            fallback=fallback.name if fallback else "",
            created_at=now_iso(),
        )

    # ── V1-V2 mapping helpers ────────────────────────────────────────────────

    @staticmethod
    def _map_complexity(score: float) -> str:
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _map_risk(score: float) -> str:
        if score >= 0.8:
            return "R4"
        if score >= 0.6:
            return "R3"
        if score >= 0.4:
            return "R2"
        if score >= 0.2:
            return "R1"
        return "R0"

    def _sync_breaker_to_portfolio(self) -> None:
        """Sync CircuitBreaker open state into portfolio health."""
        if not self._v2_enabled:
            return
        for provider_name in _PROVIDERS:
            if self.breaker.is_open(provider_name):
                try:
                    self._portfolio.update_health(
                        provider_name,
                        __import__("nexara_prime.model_portfolio_registry", fromlist=["ModelHealth"]).ModelHealth.UNHEALTHY,
                    )
                except (KeyError, ValueError):
                    pass

    # ── Track result ─────────────────────────────────────────────────────────

    def track_result(
        self,
        provider: str,
        success: bool,
        latency_ms: int,
        tokens: int,
    ) -> None:
        if success:
            self.breaker.record_success(provider)
        else:
            self.breaker.record_failure(provider)
        # Sync breaker state into V2 portfolio if enabled
        self._sync_breaker_to_portfolio()

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _choose_tier(
        complexity: float,
        risk: float,
        context_size: int,
        latency_target_ms: int,
    ) -> str:
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
        primary: ProviderInfo | None = None
        fallback: ProviderInfo | None = None
        for p in candidates:
            if health and p.name in health and not health[p.name]:
                if fallback is None:
                    fallback = p
                continue
            if self.breaker.is_open(p.name):
                if fallback is None:
                    fallback = p
                continue
            if primary is None:
                primary = p
            elif fallback is None:
                fallback = p
        if primary is None:
            primary = _PROVIDERS["mock"]
        return primary, fallback

    @staticmethod
    def _estimate_cost(provider: ProviderInfo, tokens: int) -> float:
        input_cost = (tokens / 1000.0) * provider.cost_per_1k_input_tokens
        output_cost = ((tokens * 0.25) / 1000.0) * provider.cost_per_1k_output_tokens
        return round(input_cost + output_cost, 8)

    # ── V2 Governed Adaptive Composite ────────────────────────────────────────

    def route_v2(
        self, mission: dict, anchors=None, force_mode: str = ""
    ):
        """Route via composite orchestration engine. Returns RouteResult."""
        if not self._v2_enabled:
            # V1 fallback: map mission dict to V1 route() parameters
            try:
                return self.route(
                    mission_id=mission.get("mission_id", "v1-fallback"),
                    complexity={
                        "trivial": 0.1, "low": 0.2, "medium": 0.5,
                        "high": 0.7, "extreme": 0.9,
                    }.get(mission.get("complexity", "medium"), 0.5),
                    risk={
                        "R0": 0.05, "R1": 0.25, "R2": 0.5,
                        "R3": 0.75, "R4": 0.95,
                        "none": 0.05, "low": 0.2, "medium": 0.5,
                        "high": 0.8, "critical": 0.95,
                    }.get(mission.get("risk_level", "medium"), 0.5),
                    context_size=mission.get("context_size", 0) or 0,
                    latency_target_ms=mission.get("latency_target_ms", 0) or 10_000,
                    token_budget=mission.get("token_budget", 100_000),
                )
            except (TypeError, ValueError, KeyError):
                from .models import ModelRoutingDecision
                return ModelRoutingDecision(
                    mission_id=mission.get("mission_id", "error"),
                    selected_provider="mock",
                    selected_model="mock",
                    reason="V1 fallback failed — explicit reject",
                    created_at=now_iso(),
                )
        from .knowledge_anchor import KnowledgeAnchor

        if anchors is None:
            anchors = KnowledgeAnchor()
        # Mandatory governance anchors check
        if not anchors.has_mandatory_anchors():
            from .composite_orchestration import OrchestrationMode, RouteResult
            return RouteResult(
                mode=OrchestrationMode.HUMAN_ESCALATION,
                reason="Missing mandatory governance anchors — fail closed",
            )
        return self._orchestrator.route(mission, anchors, force_mode)

    @property
    def v2_enabled(self) -> bool:
        return self._v2_enabled

    @property
    def portfolio(self):
        return self._portfolio if self._v2_enabled else None
