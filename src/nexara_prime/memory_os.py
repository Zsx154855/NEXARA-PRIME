"""L2 Memory OS — five-type memory + five-state lifecycle + provenance.

Independent L2 module. Does NOT modify Core (models.py / memory.py / db.py).
Wraps the MemoryLifecycle five-state lifecycle (candidate/validated/active/
superseded/archived) with a five-type classification and per-entry provenance.
Works standalone (in-memory) or over a SQLiteStore (`record_type="memory"`,
reusing memory.py's persistence) without importing anything from Core besides
the id/time helpers.

Types (MemoryType): EPISODIC / SEMANTIC / PROCEDURAL / PREFERENCE / OPERATIONAL.
Lifecycle: CANDIDATE → VALIDATED → ACTIVE → SUPERSEDED / ARCHIVED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .memory_archive import MemoryLifecycle

try:
    from .models import new_id, now_iso
except Exception:  # pragma: no cover - standalone import fallback
    import uuid
    from datetime import datetime, timezone

    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class MemoryType(str, Enum):
    """Five-type memory classification (OS layer)."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PREFERENCE = "preference"
    OPERATIONAL = "operational"


def _as_type(value: MemoryType | str) -> str:
    """Normalize a MemoryType / string to its canonical string value."""
    if isinstance(value, MemoryType):
        return value.value
    if isinstance(value, str):
        try:
            return MemoryType(value).value
        except ValueError:
            return value
    raise TypeError(f"unsupported_memory_type:{value!r}")


@dataclass
class MemoryEntry:
    """A single memory record with type, lifecycle status, and provenance."""

    memory_id: str
    type: str
    content: str
    source: str
    created_at: str
    updated_at: str
    confidence: float = 1.0
    scope: str = "global"
    version: int = 1
    status: str = MemoryLifecycle.ACTIVE.value
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "type": self.type,
            "content": self.content,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confidence": self.confidence,
            "scope": self.scope,
            "version": self.version,
            "status": self.status,
            "provenance": dict(self.provenance),
        }


def _entry_from(payload: dict[str, Any]) -> MemoryEntry:
    return MemoryEntry(
        memory_id=payload.get("memory_id", ""),
        type=payload.get("type", ""),
        content=payload.get("content", ""),
        source=payload.get("source", ""),
        created_at=payload.get("created_at", ""),
        updated_at=payload.get("updated_at", ""),
        confidence=float(payload.get("confidence", 1.0)),
        scope=payload.get("scope", "global"),
        version=int(payload.get("version") or 1),
        status=payload.get("status", MemoryLifecycle.ACTIVE.value),
        provenance=dict(payload.get("provenance") or {}),
    )


# Lifecycle states eligible for supersede / archive (never CANDIDATE/ARCHIVED).
_SUPERSEDABLE = {
    MemoryLifecycle.ACTIVE,
    MemoryLifecycle.VALIDATED,
}
_ARCHIVABLE = {
    MemoryLifecycle.ACTIVE,
    MemoryLifecycle.VALIDATED,
    MemoryLifecycle.SUPERSEDED,
}


class MemoryOS:
    """Five-type, five-state memory system with provenance.

    Standalone (``MemoryOS()`` → in-memory dict) or persisted
    (``MemoryOS(store)`` → SQLiteStore with ``record_type="memory"``).
    """

    def __init__(self, store: Any = None) -> None:
        self.store = store
        self._mem: dict[str, dict[str, Any]] = {}

    # ── persistence helpers ────────────────────────────────────────────
    def _load(self, memory_id: str) -> dict[str, Any] | None:
        if self.store is not None:
            return self.store.get_record(memory_id)
        return self._mem.get(memory_id)

    def _save(self, payload: dict[str, Any]) -> None:
        if self.store is not None:
            self.store.save_record(
                payload["memory_id"],
                "memory",
                payload,
                payload.get("created_at") or now_iso(),
            )
        else:
            self._mem[payload["memory_id"]] = dict(payload)

    def _list_all(self) -> list[dict[str, Any]]:
        if self.store is not None:
            return self.store.list_records("memory")
        return list(self._mem.values())

    # ── lifecycle operations ───────────────────────────────────────────
    def create_entry(
        self,
        type: MemoryType | str,
        content: str,
        source: str,
        provenance: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Create a new memory entry in ACTIVE state (version 1)."""
        ts = now_iso()
        entry = MemoryEntry(
            memory_id=new_id("mem"),
            type=_as_type(type),
            content=content,
            source=source,
            created_at=ts,
            updated_at=ts,
            confidence=1.0,
            scope="global",
            version=1,
            status=MemoryLifecycle.ACTIVE.value,
            provenance=dict(provenance or {}),
        )
        self._save(entry.to_dict())
        return entry

    def supersede(self, memory_id: str, new_id: str) -> MemoryEntry:
        """Mark an existing ACTIVE/VALIDATED memory SUPERSEDED by ``new_id``."""
        payload = self._load(memory_id)
        if payload is None:
            raise KeyError(f"memory_not_found:{memory_id}")
        current = payload.get("status")
        if current not in {s.value for s in _SUPERSEDABLE}:
            raise ValueError(
                f"memory_not_supersedable:{memory_id}:status={current}"
            )
        payload = dict(payload)
        prov = dict(payload.get("provenance") or {})
        prov["superseded_by"] = new_id
        payload["provenance"] = prov
        payload["status"] = MemoryLifecycle.SUPERSEDED.value
        payload["superseded_by"] = new_id
        payload["version"] = int(payload.get("version") or 1) + 1
        payload["updated_at"] = now_iso()
        self._save(payload)
        return _entry_from(payload)

    def archive(
        self,
        memory_id: str,
        reason: str,
        superseded_by: str | None = None,
    ) -> MemoryEntry:
        """ACTIVE / VALIDATED / SUPERSEDED → ARCHIVED (mark-only, no delete)."""
        payload = self._load(memory_id)
        if payload is None:
            raise KeyError(f"memory_not_found:{memory_id}")
        current = payload.get("status")
        if current == MemoryLifecycle.ARCHIVED.value:
            return _entry_from(payload)
        if current not in {s.value for s in _ARCHIVABLE}:
            raise ValueError(f"memory_not_archivable:{memory_id}:status={current}")
        payload = dict(payload)
        archived_at = now_iso()
        prov = dict(payload.get("provenance") or {})
        prov["archived_at"] = archived_at
        prov["archive_reason"] = reason
        if superseded_by:
            prov["superseded_by"] = superseded_by
        payload["provenance"] = prov
        payload["status"] = MemoryLifecycle.ARCHIVED.value
        payload["archived_at"] = archived_at
        payload["archive_reason"] = reason
        payload["superseded_by"] = superseded_by
        payload["version"] = int(payload.get("version") or 1) + 1
        payload["updated_at"] = archived_at
        self._save(payload)
        return _entry_from(payload)

    def restore(self, memory_id: str) -> MemoryEntry:
        """ARCHIVED → ACTIVE (un-archive; version bump, never deletes)."""
        payload = self._load(memory_id)
        if payload is None:
            raise KeyError(f"memory_not_found:{memory_id}")
        if payload.get("status") != MemoryLifecycle.ARCHIVED.value:
            raise ValueError(
                f"memory_not_restorable:{memory_id}:status={payload.get('status')}"
            )
        payload = dict(payload)
        payload["status"] = MemoryLifecycle.ACTIVE.value
        payload["version"] = int(payload.get("version") or 1) + 1
        payload["updated_at"] = now_iso()
        self._save(payload)
        return _entry_from(payload)

    # ── queries ────────────────────────────────────────────────────────
    def list_by_type(self, mtype: MemoryType | str) -> list[MemoryEntry]:
        """Return all entries of a given type (any lifecycle status)."""
        target = _as_type(mtype)
        return [
            _entry_from(p)
            for p in self._list_all()
            if p.get("type") == target
        ]

    def list_active(self) -> list[MemoryEntry]:
        """Return all entries excluding ARCHIVED (and SUPERSEDED)."""
        excluded = {MemoryLifecycle.ARCHIVED.value, MemoryLifecycle.SUPERSEDED.value}
        return [
            _entry_from(p)
            for p in self._list_all()
            if p.get("status") not in excluded
        ]


__all__ = [
    "MemoryType",
    "MemoryEntry",
    "MemoryOS",
]
