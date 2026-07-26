"""KnowledgeService — unified knowledge retrieval and fabric integration.

G3-D: Wraps MemoryKernel queries into a unified service.
Does NOT modify memory.py.
"""
from __future__ import annotations

from typing import Any

from .memory import MemoryKernel
from .models import now_iso


class KnowledgeService:
    """Unified knowledge retrieval service.

    Wraps MemoryKernel.inspect() + candidates() with kind-based filtering.
    """

    def __init__(self, memory: MemoryKernel) -> None:
        self._memory = memory
        self._started = False
        self._started_at = ""

    def start(self) -> None:
        self._started = True
        self._started_at = now_iso()

    def stop(self) -> None:
        self._started = False

    @property
    def running(self) -> bool:
        return self._started

    def query(self, kind_filter: str = "", key_filter: str = "") -> list[dict[str, Any]]:
        """Query memory records, optionally filtered by kind and key."""
        records = self._memory.inspect()
        if kind_filter:
            records = [r for r in records if r.get("kind", "") == kind_filter]
        if key_filter:
            records = [r for r in records if key_filter.lower() in r.get("key", "").lower()]
        return records

    def query_candidates(self) -> list[dict[str, Any]]:
        """Query proposed memory patches (candidates)."""
        return self._memory.candidates()

    def health(self) -> dict[str, Any]:
        return {
            "service": "knowledge",
            "status": "healthy" if self._started else "stopped",
            "started_at": self._started_at,
            "memory_available": self._memory is not None,
            "timestamp": now_iso(),
        }
