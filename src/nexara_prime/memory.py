from __future__ import annotations

from .db import SQLiteStore
from .events import EventBus
from .models import MemoryKind, MemoryRecord, new_id


class MemoryKernel:
    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    def write(self, kind: MemoryKind, key: str, content: str, trace_id: str, mission_id: str | None = None, source_evidence_id: str | None = None, confidence: float = 1.0) -> MemoryRecord:
        if kind == MemoryKind.UNVERIFIED_INFERENCE:
            return self.propose(kind, key, content, trace_id, mission_id, source_evidence_id, confidence)
        record = MemoryRecord(
            memory_id=new_id("memory"), mission_id=mission_id, kind=kind, key=key,
            content=content, source_evidence_id=source_evidence_id, confidence=confidence,
            status="committed", verified=bool(source_evidence_id), canonical=bool(source_evidence_id),
        )
        self.store.save_record(record.memory_id, "memory", record.model_dump(mode="json"), record.created_at, mission_id)
        self.events.publish("memory.written", mission_id or "global", "mission" if mission_id else "memory", "memory_kernel", trace_id, {"memory_id": record.memory_id, "kind": kind.value})
        return record

    def patch(self, mission_id: str, key: str, content: str, trace_id: str, evidence_id: str | None = None) -> MemoryRecord:
        return self.propose(MemoryKind.PATCH, key, content, trace_id, mission_id, evidence_id, 1.0, auto_commit=True)

    def propose(
        self,
        kind: MemoryKind,
        key: str,
        content: str,
        trace_id: str,
        mission_id: str | None = None,
        source_evidence_id: str | None = None,
        confidence: float = 1.0,
        *,
        auto_commit: bool = False,
    ) -> MemoryRecord:
        """Candidate → Validate → Deduplicate → Conflict Check → Commit.

        Unverified inferences remain candidates and are never written to canonical memory.
        Safe patches may use the explicit auto policy when backed by evidence.
        """
        if not key.strip() or not content.strip():
            raise ValueError("memory_candidate_requires_key_and_content")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("memory_confidence_out_of_range")
        duplicate = next((item for item in self.inspect(mission_id) if item.get("key") == key and item.get("content") == content and item.get("status") == "committed"), None)
        if duplicate:
            return MemoryRecord.model_validate(duplicate)
        existing = [item for item in self.inspect(mission_id) if item.get("key") == key and item.get("status") == "committed"]
        conflict_keys = [item["memory_id"] for item in existing if item.get("content") != content]
        should_commit = auto_commit and kind != MemoryKind.UNVERIFIED_INFERENCE and confidence >= 0.8 and bool(source_evidence_id) and not conflict_keys
        status = "committed" if should_commit else ("conflict" if conflict_keys else "candidate")
        record = MemoryRecord(
            memory_id=new_id("memory"), mission_id=mission_id, kind=kind, key=key, content=content,
            source_evidence_id=source_evidence_id, confidence=confidence, status=status,
            verified=should_commit, canonical=should_commit, conflict_keys=conflict_keys,
        )
        target_type = "memory" if should_commit else "memory_candidate"
        self.store.save_record(record.memory_id, target_type, record.model_dump(mode="json"), record.created_at, mission_id)
        event_type = "memory.committed" if should_commit else "memory.candidate.created"
        self.events.publish(event_type, mission_id or "global", "mission" if mission_id else "memory", "memory_kernel", trace_id, {"memory_id": record.memory_id, "kind": kind.value, "status": status})
        if conflict_keys:
            self.store.save_record(new_id("memory_conflict"), "memory_conflict", {"memory_id": record.memory_id, "key": key, "conflicts": conflict_keys}, record.created_at, mission_id)
            self.events.publish("memory.conflict.detected", mission_id or "global", "mission" if mission_id else "memory", "memory_kernel", trace_id, {"memory_id": record.memory_id, "conflicts": conflict_keys})
        return record

    def commit_candidate(self, memory_id: str, trace_id: str, actor: str = "human") -> MemoryRecord:
        raw = self.store.get_record(memory_id)
        if not raw:
            raise KeyError(f"memory_candidate_not_found:{memory_id}")
        candidate = MemoryRecord.model_validate(raw)
        if candidate.kind == MemoryKind.UNVERIFIED_INFERENCE:
            raise PermissionError("unverified_inference_cannot_be_canonical")
        if candidate.conflict_keys:
            raise ValueError("memory_candidate_has_conflict")
        candidate.status = "committed"
        candidate.verified = True
        candidate.canonical = True
        self.store.save_record(candidate.memory_id, "memory", candidate.model_dump(mode="json"), candidate.created_at, candidate.mission_id)
        self.events.publish("memory.committed", candidate.mission_id or "global", "mission" if candidate.mission_id else "memory", actor, trace_id, {"memory_id": candidate.memory_id, "manual": True})
        return candidate

    def inspect(self, mission_id: str | None = None) -> list[dict]:
        return self.store.list_records("memory", mission_id)

    def candidates(self, mission_id: str | None = None) -> list[dict]:
        return self.store.list_records("memory_candidate", mission_id)
