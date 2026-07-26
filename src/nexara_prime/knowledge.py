"""KnowledgeService — unified knowledge retrieval, conflict detection, and fabric integration.

Phase 2 (KMA): Adds supersession detection, KnowledgeCommit validation,
and evidence-bound conflict tracking. Does NOT modify memory.py.
"""
from __future__ import annotations

from typing import Any

from .memory import MemoryKernel
from .models import KnowledgeCommit, MemoryKind, now_iso, new_id


class KnowledgeService:
    """Unified knowledge retrieval and conflict/supersession service.

    Wraps MemoryKernel with:
    - kind/key-based filtering (V1)
    - supersession detection (Phase 2)
    - KnowledgeCommit validation (Phase 2)
    - conflict tracking with evidence binding (Phase 2)
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

    # ── V1 API (preserved) ──

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

    # ── Phase 2: Supersession Detection ──

    def detect_supersession(
        self, key: str, content: str, mission_id: str | None = None
    ) -> dict[str, Any]:
        """Check whether a new knowledge entry supersedes an existing canonical entry.

        Rules:
        - Same key + different content + existing canonical entry → supersedes
        - Same key + same content → duplicate (idempotent replay, no supersession)
        - No existing canonical entry → new
        - Returns structured result with relation metadata.
        """
        existing = self._memory.inspect(mission_id)
        canonical = [
            r for r in existing
            if r.get("key") == key and r.get("status") == "committed"
        ]
        if not canonical:
            return {
                "action": "new",
                "key": key,
                "supersedes": [],
                "conflicts_with": [],
            }

        duplicates = [r for r in canonical if r.get("content") == content]
        if duplicates:
            return {
                "action": "duplicate",
                "key": key,
                "duplicate_of": duplicates[0].get("memory_id"),
                "supersedes": [],
                "conflicts_with": [],
            }

        superseded = [r["memory_id"] for r in canonical]
        return {
            "action": "supersedes",
            "key": key,
            "supersedes": superseded,
            "conflicts_with": [],
        }

    def detect_conflicts(
        self, key: str, content: str, mission_id: str | None = None
    ) -> dict[str, Any]:
        """Detect conflicts between proposed and existing knowledge.

        Returns structured conflict metadata traceable to evidence IDs.
        """
        existing = self._memory.inspect(mission_id)
        conflicts = [
            r for r in existing
            if r.get("key") == key
            and r.get("content") != content
            and r.get("status") == "committed"
        ]
        return {
            "has_conflicts": len(conflicts) > 0,
            "key": key,
            "conflicts": [
                {
                    "memory_id": r.get("memory_id"),
                    "content_preview": (r.get("content") or "")[:200],
                    "source_evidence_id": r.get("source_evidence_id"),
                }
                for r in conflicts
            ],
        }

    # ── Phase 2: KnowledgeCommit Validation ──

    def validate_commit(self, commit: KnowledgeCommit) -> dict[str, Any]:
        """Validate a KnowledgeCommit against KMA rules.

        Returns {valid: bool, errors: list[str], supersession: dict}.
        Does NOT execute the commit — only validates the input.
        """
        errors: list[str] = []

        if not commit.key.strip():
            errors.append("key_required")
        if not commit.content.strip():
            errors.append("content_required")
        if not commit.trace_id:
            errors.append("trace_id_required")

        if commit.kind == MemoryKind.UNVERIFIED_INFERENCE and commit.auto_commit:
            errors.append("unverified_inference_cannot_auto_commit")

        if commit.confidence < 0.0 or commit.confidence > 1.0:
            errors.append("confidence_out_of_range")

        supersession = {}
        if not errors:
            supersession = self.detect_supersession(
                commit.key, commit.content, commit.mission_id
            )
            supersession_check = self.detect_conflicts(
                commit.key, commit.content, commit.mission_id
            )
            if supersession_check["has_conflicts"] and not commit.auto_commit:
                # Conflicts don't block validation, but they are noted.
                # auto_commit will still require evidence backing.
                pass

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "supersession": supersession,
        }

    def query_non_superseded(
        self,
        kind_filter: str = "",
        key_filter: str = "",
        mission_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query only non-superseded canonical records.

        Superseded records (those that have been replaced by a newer version)
        are excluded from results. Use for recall that should return only
        the current canonical knowledge.
        """
        records = self._memory.inspect(mission_id)
        committed = [r for r in records if r.get("status") == "committed"]

        # Find superseded IDs by looking for keys with multiple committed entries
        # with different content (the oldest one with the same key is superseded).
        keys_seen: dict[str, list[dict[str, Any]]] = {}
        for r in committed:
            k = r.get("key", "")
            keys_seen.setdefault(k, []).append(r)

        superseded_ids: set[str] = set()
        for k, entries in keys_seen.items():
            if len(entries) > 1:
                entries.sort(key=lambda e: e.get("created_at", ""))
                # All but the newest are superseded
                for older in entries[:-1]:
                    superseded_ids.add(older.get("memory_id", ""))

        results = [r for r in committed if r.get("memory_id") not in superseded_ids]
        if kind_filter:
            results = [r for r in results if r.get("kind", "") == kind_filter]
        if key_filter:
            results = [r for r in results if key_filter.lower() in r.get("key", "").lower()]
        return results

    # ── Health ──

    def health(self) -> dict[str, Any]:
        return {
            "service": "knowledge",
            "status": "healthy" if self._started else "stopped",
            "started_at": self._started_at,
            "memory_available": self._memory is not None,
            "features": {
                "supersession_detection": True,
                "conflict_detection": True,
                "commit_validation": True,
            },
            "timestamp": now_iso(),
        }
