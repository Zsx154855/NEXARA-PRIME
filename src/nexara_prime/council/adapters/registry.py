"""NEXARA Council V2 — Adapter Registry

Central registry for all model adapters. Discovers, validates,
and manages adapter lifecycle.
"""

from __future__ import annotations

from typing import Optional

from nexara_prime.council.adapters.base import BaseAdapter
from nexara_prime.council.adapters.schemas import AdapterDiscovery, AdapterStatus
from nexara_prime.council.adapters.openai_adapter import OpenAIAdapter
from nexara_prime.council.adapters.anthropic_adapter import AnthropicAdapter
from nexara_prime.council.adapters.codex_cli_adapter import CodexCLIAdapter
from nexara_prime.council.adapters.xai_adapter import XAIAdapter
from nexara_prime.council.adapters.deepseek_adapter import DeepSeekAdapter
from nexara_prime.council.adapters.hermes_adapter import HermesAdapter


class AdapterRegistry:
    """Registry of all council model adapters."""

    _adapters: dict[str, BaseAdapter] = {}

    @classmethod
    def initialize(cls) -> None:
        """Initialize all adapters."""
        cls._adapters = {
            "openai": OpenAIAdapter(),
            "anthropic": AnthropicAdapter(),
            "codex_cli": CodexCLIAdapter(),
            "xai": XAIAdapter(),
            "deepseek_staff": DeepSeekAdapter(seat="H-STAFF"),
            "deepseek_mem": DeepSeekAdapter(seat="H-MEM"),
            "hermes": HermesAdapter(),
        }

    @classmethod
    def get(cls, adapter_id: str) -> Optional[BaseAdapter]:
        if not cls._adapters:
            cls.initialize()
        return cls._adapters.get(adapter_id)

    @classmethod
    def discover_all(cls) -> dict[str, AdapterDiscovery]:
        """Run discovery on all adapters. Returns dict of adapter_id -> discovery."""
        if not cls._adapters:
            cls.initialize()
        results = {}
        for aid, adapter in cls._adapters.items():
            results[aid] = adapter.discover()
        return results

    @classmethod
    def all_adapters(cls) -> list[BaseAdapter]:
        if not cls._adapters:
            cls.initialize()
        return list(cls._adapters.values())

    @classmethod
    def ready_adapters(cls) -> list[BaseAdapter]:
        """Return only adapters that passed discovery."""
        discoveries = cls.discover_all()
        return [
            adapter for aid, adapter in cls._adapters.items()
            if discoveries[aid].status == AdapterStatus.READY
        ]

    @classmethod
    def ready_count(cls) -> int:
        return len(cls.ready_adapters())


# Auto-init on import
AdapterRegistry.initialize()
