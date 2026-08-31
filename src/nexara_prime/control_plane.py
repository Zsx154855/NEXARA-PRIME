"""L2 Control Plane — READ_ONLY unified observation over the store.

Independent L2 module. Does NOT modify Core or write any data. Provides a
single read-only vantage point over the SQLiteStore: per-record-type counts
(summary) and total + distribution (health). All reads go through
``store.list_records(type)`` / ``store.count("records")``; nothing is written.
"""

from __future__ import annotations

from typing import Any

# Canonical record types observed by the control plane.
RECORD_TYPES: tuple[str, ...] = (
    "mission",
    "conversation",
    "memory",
    "session",
    "evidence",
    "audit_entry",
    "tool",
)


class ControlPlane:
    """Read-only unified observer over the durable store."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def summary(self) -> dict[str, Any]:
        """Per-record-type counts for the canonical types, plus total."""
        counts: dict[str, int] = {}
        for record_type in RECORD_TYPES:
            counts[record_type] = len(self.store.list_records(record_type))
        return {
            "records": counts,
            "total": sum(counts.values()),
        }

    def health(self, store: Any = None) -> dict[str, Any]:
        """Total record count + full record_type distribution (read-only)."""
        store = store or self.store
        total = int(store.count("records"))
        distribution = self._distribution(store)
        return {
            "total_records": total,
            "record_type_distribution": distribution,
        }

    def _distribution(self, store: Any) -> dict[str, int]:
        """Record-type → count over every record type in the store.

        Prefers a single GROUP BY over the connection; falls back to counting
        the canonical types via ``list_records`` if direct access is unsafe.
        """
        try:
            with store._lock:  # noqa: SLF001 - read-only observation
                rows = store._conn.execute(
                    "SELECT record_type, COUNT(*) AS n "
                    "FROM records GROUP BY record_type"
                ).fetchall()
            return {str(r["record_type"]): int(r["n"]) for r in rows}
        except Exception:
            dist: dict[str, int] = {}
            for record_type in RECORD_TYPES:
                dist[record_type] = len(store.list_records(record_type))
            return dist


__all__ = [
    "ControlPlane",
    "RECORD_TYPES",
]
