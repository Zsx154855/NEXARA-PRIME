"""L2 Memory Archive — ARCHIVED lifecycle completion.

Independent L2 module. Does NOT modify Core (models.py / memory.py /
brain/*). Extends the four-layer memory system with a five-state lifecycle
that adds ARCHIVED, and never deletes a memory record — it only marks it
ARCHIVED (with archived_at / archive_reason / superseded_by / version).

Core status strings ("committed", "superseded", ...) are mapped onto the
new lifecycle; the archive transition is ACTIVE / VALIDATED / SUPERSEDED
→ ARCHIVED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

try:
    from .models import new_id, now_iso
except Exception:  # pragma: no cover - standalone import fallback
    import uuid
    from datetime import datetime, timezone

    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class MemoryLifecycle(str, Enum):
    """Five-state memory lifecycle. ARCHIVED is the terminal, non-destructive state."""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


# Core status strings → lifecycle states (committed memory is ACTIVE).
_STATUS_TO_LIFECYCLE: dict[str, MemoryLifecycle] = {
    "candidate": MemoryLifecycle.CANDIDATE,
    "pending_review": MemoryLifecycle.CANDIDATE,
    "validated": MemoryLifecycle.VALIDATED,
    "verified": MemoryLifecycle.VALIDATED,
    "committed": MemoryLifecycle.ACTIVE,
    "active": MemoryLifecycle.ACTIVE,
    "superseded": MemoryLifecycle.SUPERSEDED,
    "archived": MemoryLifecycle.ARCHIVED,
}

_ARCHIVABLE = {
    MemoryLifecycle.ACTIVE,
    MemoryLifecycle.VALIDATED,
    MemoryLifecycle.SUPERSEDED,
}

# Fields every ARCHIVED record must carry.
ARCHIVED_FIELDS = ("archived_at", "archive_reason", "superseded_by", "version")


def _lifecycle_of(status: str | None) -> MemoryLifecycle | None:
    if not status:
        return None
    return _STATUS_TO_LIFECYCLE.get(status)


@dataclass
class ArchiveResult:
    """Result of an archive transition."""

    memory_id: str
    status: str
    archived_at: str
    archive_reason: str
    superseded_by: str | None
    version: int
    record: dict[str, Any] = field(default_factory=dict)


class MemoryArchive:
    """Archive layer over the memory store. Mark-only, never deletes."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def archive_memory(
        self,
        memory_id: str,
        reason: str,
        superseded_by: str | None = None,
        *,
        actor: str = "system",
        trace_id: str = "",
    ) -> ArchiveResult:
        """ACTIVE / VALIDATED / SUPERSEDED → ARCHIVED (mark-only, no delete).

        Writes archived_at + archive_reason + superseded_by + version onto the
        existing record payload and persists it in place under the same
        record_id. Already-ARCHIVED records are returned unchanged (idempotent).
        CANDIDATE / unknown records are rejected — they are never archived.
        """
        payload = self.store.get_record(memory_id)
        if payload is None:
            raise KeyError(f"memory_not_found:{memory_id}")

        envelope = self.store.get_record_envelope(memory_id)
        mission_id = (envelope or {}).get("mission_id") or payload.get("mission_id")

        current = _lifecycle_of(payload.get("status"))
        if current is MemoryLifecycle.ARCHIVED:
            return ArchiveResult(
                memory_id=memory_id,
                status=MemoryLifecycle.ARCHIVED.value,
                archived_at=payload.get("archived_at", ""),
                archive_reason=payload.get("archive_reason", reason),
                superseded_by=payload.get("superseded_by"),
                version=int(payload.get("version") or 0),
                record=payload,
            )
        if current not in _ARCHIVABLE:
            raise ValueError(
                f"memory_not_archivable:{memory_id}:status={payload.get('status')}"
            )

        version = int(payload.get("version") or 0) + 1
        archived_at = now_iso()

        archived = dict(payload)
        archived["status"] = MemoryLifecycle.ARCHIVED.value
        archived["archived_at"] = archived_at
        archived["archive_reason"] = reason
        archived["superseded_by"] = superseded_by
        archived["version"] = version

        self.store.save_record(
            memory_id,
            "memory",
            archived,
            payload.get("created_at") or archived_at,
            mission_id,
        )
        return ArchiveResult(
            memory_id=memory_id,
            status=MemoryLifecycle.ARCHIVED.value,
            archived_at=archived_at,
            archive_reason=reason,
            superseded_by=superseded_by,
            version=version,
            record=archived,
        )

    def list_active(self, mission_id: str | None = None) -> list[dict[str, Any]]:
        """Return memory records, excluding ARCHIVED by default."""
        return [
            r
            for r in self.store.list_records("memory", mission_id)
            if r.get("status") != MemoryLifecycle.ARCHIVED.value
        ]

    def list_archived(self, mission_id: str | None = None) -> list[dict[str, Any]]:
        """Return only ARCHIVED records."""
        return [
            r
            for r in self.store.list_records("memory", mission_id)
            if r.get("status") == MemoryLifecycle.ARCHIVED.value
        ]


def archive_memory(
    store: Any,
    memory_id: str,
    reason: str,
    superseded_by: str | None = None,
    **kwargs: Any,
) -> ArchiveResult:
    """Module-level convenience: archive a memory in ``store``."""
    return MemoryArchive(store).archive_memory(
        memory_id, reason, superseded_by, **kwargs
    )


__all__ = [
    "MemoryLifecycle",
    "MemoryArchive",
    "ArchiveResult",
    "ARCHIVED_FIELDS",
    "archive_memory",
]
