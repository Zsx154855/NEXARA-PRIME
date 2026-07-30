"""
NEXARA Model Portfolio Registry V1

Governed registry of all model providers, capabilities, and health.
Replaces in-code provider constants with versioned, auditable provider records.

NSEC V2.1 §5.A — Provider must come from versioned registry.
Mock is test-only, production must fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import now_iso


class DataSovereignty(str, Enum):
    LOCAL_ONLY = "local_only"
    CLOUD_REGIONAL = "cloud_regional"
    CLOUD_GLOBAL = "cloud_global"


class ModelHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ProviderCapability:
    supports_tools: bool = False
    supports_vision: bool = False
    supports_audio: bool = False
    supports_structured_output: bool = False
    max_context_tokens: int = 4096
    max_output_tokens: int = 4096
    typical_latency_ms: int = 2000
    estimated_cost_per_1k_input: float = 0.0
    estimated_cost_per_1k_output: float = 0.0
    reliability_score: float = 0.95  # 0.0-1.0


@dataclass(frozen=True)
class ModelPortfolioEntry:
    """A single model registered in the portfolio."""

    portfolio_id: str  # unique, e.g. "deepseek-v4-pro"
    provider: str  # e.g. "deepseek", "openai"
    model_name: str  # e.g. "deepseek-v4-pro"
    display_name: str
    capability: ProviderCapability
    sovereignty: DataSovereignty = DataSovereignty.CLOUD_GLOBAL
    health: ModelHealth = ModelHealth.UNKNOWN
    enabled: bool = True
    is_mock: bool = False
    tier: int = 2  # 0=mock, 1=flash, 2=pro, 3=specialist
    tags: tuple[str, ...] = ()
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)


class ModelPortfolioRegistry:
    """
    Single source of truth for all model providers.

    Production sorting excludes: mock, disabled, unhealthy.
    Mock providers never appear in production candidate lists.
    """

    def __init__(self) -> None:
        self._entries: dict[str, ModelPortfolioEntry] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Register the two real providers currently available."""
        self.register(ModelPortfolioEntry(
            portfolio_id="deepseek-v4-pro",
            provider="deepseek",
            model_name="deepseek-v4-pro",
            display_name="DeepSeek V4 Pro",
            capability=ProviderCapability(
                supports_tools=True,
                supports_structured_output=True,
                max_context_tokens=128_000,
                max_output_tokens=8192,
                typical_latency_ms=3000,
                estimated_cost_per_1k_input=0.001,
                estimated_cost_per_1k_output=0.002,
                reliability_score=0.92,
            ),
            sovereignty=DataSovereignty.CLOUD_GLOBAL,
            health=ModelHealth.HEALTHY,
            tier=2,
            tags=("reasoning", "coding", "research"),
        ))
        self.register(ModelPortfolioEntry(
            portfolio_id="deepseek-v4-flash",
            provider="deepseek",
            model_name="deepseek-v4-flash",
            display_name="DeepSeek V4 Flash",
            capability=ProviderCapability(
                supports_tools=True,
                supports_structured_output=True,
                max_context_tokens=32_000,
                max_output_tokens=4096,
                typical_latency_ms=800,
                estimated_cost_per_1k_input=0.0003,
                estimated_cost_per_1k_output=0.0005,
                reliability_score=0.88,
            ),
            sovereignty=DataSovereignty.CLOUD_GLOBAL,
            health=ModelHealth.HEALTHY,
            tier=1,
            tags=("fast", "classification", "summarization"),
        ))

    # ── registration ──────────────────────────────────────

    def register(self, entry: ModelPortfolioEntry) -> None:
        if entry.portfolio_id in self._entries:
            raise ValueError(f"Portfolio ID already registered: {entry.portfolio_id}")
        self._entries[entry.portfolio_id] = entry

    def update_health(self, portfolio_id: str, health: ModelHealth) -> None:
        old = self._entries[portfolio_id]
        self._entries[portfolio_id] = ModelPortfolioEntry(
            portfolio_id=old.portfolio_id,
            provider=old.provider,
            model_name=old.model_name,
            display_name=old.display_name,
            capability=old.capability,
            sovereignty=old.sovereignty,
            health=health,
            enabled=old.enabled,
            is_mock=old.is_mock,
            tier=old.tier,
            tags=old.tags,
            created_at=old.created_at,
        )

    def disable(self, portfolio_id: str) -> None:
        old = self._entries[portfolio_id]
        self._entries[portfolio_id] = ModelPortfolioEntry(
            portfolio_id=old.portfolio_id,
            provider=old.provider,
            model_name=old.model_name,
            display_name=old.display_name,
            capability=old.capability,
            sovereignty=old.sovereignty,
            health=old.health,
            enabled=False,
            is_mock=old.is_mock,
            tier=old.tier,
            tags=old.tags,
            created_at=old.created_at,
        )

    # ── query ────────────────────────────────────────────

    def get(self, portfolio_id: str) -> ModelPortfolioEntry | None:
        return self._entries.get(portfolio_id)

    def list_all(self) -> list[ModelPortfolioEntry]:
        return sorted(self._entries.values(), key=lambda e: e.tier)

    def list_production(self) -> list[ModelPortfolioEntry]:
        """Production-eligible entries only. Mock, disabled, unhealthy excluded."""
        return [
            e for e in self.list_all()
            if e.enabled and not e.is_mock and e.health != ModelHealth.UNHEALTHY
        ]

    def list_by_tier(self, tier: int) -> list[ModelPortfolioEntry]:
        return [e for e in self.list_production() if e.tier == tier]

    def has_real_provider(self) -> bool:
        return len(self.list_production()) > 0

    @property
    def entries(self) -> dict[str, ModelPortfolioEntry]:
        return dict(self._entries)
