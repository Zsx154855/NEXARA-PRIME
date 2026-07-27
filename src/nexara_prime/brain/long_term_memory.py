"""LongTermMemory — LTM operations: consolidation, reinforcement, supersession, GC, provenance.

Wraps MemoryController for long-term memory-specific operations.
Phase 1: Memory Foundation (MemoryBrain + LongTermMemory).
"""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso

from .db import BrainDB
from .memory_controller import MemoryController
from .decay_config import compute_decayed_confidence, get_half_life, get_min_confidence
from .consolidation_rules import (
    should_promote_working_to_semantic,
    should_promote_semantic_to_procedural,
    classify_layer,
)


class LongTermMemory:
    """Long-term memory operations wrapping MemoryController."""

    name = "long_term_memory"

    def __init__(self, controller: MemoryController, db: BrainDB | None = None) -> None:
        self._controller = controller
        self._db = db or controller._db

    # ── Consolidation: promote short-term → long-term ──

    def consolidate_to_ltm(
        self, memory_id: str, force: bool = False,
    ) -> dict[str, Any] | None:
        """Promote a memory to long-term if it meets thresholds."""
        record = self._db.get_memory(memory_id)
        if not record:
            return None

        layer = record.get("layer", "")
        access_count = int(record.get("access_count", 0))
        confidence = float(record.get("confidence", 1.0))
        kind = record.get("kind", "")

        promoted = False
        new_layer = layer

        if layer == "working" and (
            force or should_promote_working_to_semantic(access_count)
        ):
            new_layer = "semantic"
            promoted = True
        elif layer == "semantic" and (
            force or should_promote_semantic_to_procedural(confidence, access_count)
        ):
            new_layer = "procedural"
            promoted = True

        if promoted:
            target_id = new_id("mem")
            new_record = dict(record)
            new_record["memory_id"] = target_id
            new_record["layer"] = new_layer
            new_record["consolidated_from"] = memory_id
            new_record["confidence"] = max(confidence, 0.9)
            new_record["created_at"] = now_iso()
            new_record["updated_at"] = now_iso()
            new_record["access_count"] = 0

            self._db.insert_memory(new_record)
            self._db.log_consolidation(
                source_id=memory_id,
                target_id=target_id,
                from_layer=layer,
                to_layer=new_layer,
                trigger="ltm_consolidation",
            )
            return new_record

        return None

    # ── Reinforcement: boost confidence on access ──

    def reinforce(self, memory_id: str) -> dict[str, Any] | None:
        """Increment access_count, update last_accessed, recalculate confidence."""
        record = self._db.get_memory(memory_id)
        if not record:
            return None

        access_count = int(record.get("access_count", 0)) + 1
        kind = record.get("kind", "")
        half_life = get_half_life(kind)
        confidence = float(record.get("confidence", 1.0))

        # Reinforcement: slight confidence boost, capped at 1.0
        if half_life > 0:
            confidence = min(1.0, confidence + 0.05)

        updates = {
            "access_count": access_count,
            "last_accessed": now_iso(),
            "confidence": confidence,
        }
        self._db.update_memory(memory_id, updates)
        self._db.log_access(memory_id, "reinforce")

        record.update(updates)
        return record

    # ── Supersession detection ──

    def detect_supersession(
        self, key: str, new_content: str, mission_id: str = "global",
    ) -> list[str]:
        """Find conflicting memories and flag them as superseded."""
        existing = self._db.get_memory_by_key(key, mission_id)
        superseded_ids: list[str] = []

        for entry in existing:
            old_content = entry.get("content", "")
            if old_content and old_content != new_content:
                # Flag old entry as superseded by the new one
                self._db.update_memory(
                    entry["memory_id"],
                    {"superseded_by": "superseded", "status": "superseded"},
                )
                superseded_ids.append(entry["memory_id"])

        return superseded_ids

    # ── Garbage collection ──

    def garbage_collect(
        self, min_confidence: float = 0.1, max_age_days: float = 365,
    ) -> dict[str, Any]:
        """Archive low-confidence stale memories. Returns count of archived."""
        all_records = self._db.recall(status="active")
        archived = 0

        for r in all_records:
            confidence = float(r.get("confidence", 1.0))
            if confidence >= min_confidence:
                continue

            kind = r.get("kind", "")
            half_life = get_half_life(kind)
            if half_life <= 0:
                continue  # never-decay kinds are not GCed (superseded instead)

            self._db.update_status(r["memory_id"], "archived")
            archived += 1

        return {"archived_count": archived, "gc_at": now_iso()}

    # ── Provenance chain ──

    def get_provenance_chain(self, memory_id: str) -> dict[str, Any] | None:
        return self._controller.get_provenance(memory_id)

    # ── Decay tick (delegates to MemoryController) ──

    def decay_tick(self) -> dict[str, Any]:
        return self._controller.decay_tick()

    # ── Health report ──

    def health_report(self) -> dict[str, Any]:
        base = self._controller.health_report()

        # LTM-specific: consolidation rate, supersession rate, GC candidates
        active = base.get("active_count", 0)
        consolidated = 0
        superseded = 0

        all_records = self._db.recall()
        for r in all_records:
            if r.get("consolidated_from"):
                consolidated += 1
            if r.get("superseded_by"):
                superseded += 1

        base["ltm_consolidation_rate"] = round(consolidated / active, 3) if active > 0 else 0.0
        base["ltm_supersession_rate"] = round(superseded / active, 3) if active > 0 else 0.0
        base["ltm_gc_candidates"] = sum(
            1 for r in all_records
            if float(r.get("confidence", 1.0)) < 0.1 and r.get("status") == "active"
        )

        return base
