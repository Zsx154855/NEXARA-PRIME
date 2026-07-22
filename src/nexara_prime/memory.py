from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from .db import SQLiteStore
from .events import EventBus
from .models import MemoryKind, MemoryRecord, new_id, now_iso

if TYPE_CHECKING:
    from .evidence import EvidenceStore
    from .rag_pipeline import RAGPipeline


# ── Four-layer memory classification ──

class MemoryLayer:
    """Four-layer memory architecture."""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"

    @classmethod
    def from_kind(cls, kind: MemoryKind) -> str:
        mapping: dict[MemoryKind, str] = {
            MemoryKind.SHORT_TERM: cls.WORKING,
            MemoryKind.TEMPORARY_CONTEXT: cls.WORKING,
            MemoryKind.FACT: cls.SEMANTIC,
            MemoryKind.DECISION: cls.EPISODIC,
            MemoryKind.FAILURE: cls.EPISODIC,
            MemoryKind.FAILURE_EXPERIENCE: cls.SEMANTIC,
            MemoryKind.PATCH: cls.PROCEDURAL,
            MemoryKind.SKILL_IMPROVEMENT: cls.PROCEDURAL,
            MemoryKind.SYSTEM_RULE: cls.PROCEDURAL,
            MemoryKind.USER_FACT: cls.SEMANTIC,
            MemoryKind.PROJECT_FACT: cls.SEMANTIC,
            MemoryKind.PREFERENCE: cls.SEMANTIC,
            MemoryKind.UNVERIFIED_INFERENCE: cls.WORKING,
        }
        return mapping.get(kind, cls.SEMANTIC)


@dataclass
class PatchReview:
    """Memory Patch Review — structured review of a proposed memory patch."""
    review_id: str = field(default_factory=lambda: new_id("patch_review"))
    memory_id: str = ""
    patch_key: str = ""
    patch_content: str = ""
    reviewer: str = ""
    decision: str = "pending"  # approved, rejected, changes_requested
    reason: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    decided_at: str = ""



def _safe_memory_kind(kind_str: str, default: "MemoryKind" = None) -> "MemoryKind":
    '''Parse MemoryKind safely, falling back to default on bad input.'''
    from .models import MemoryKind
    try:
        return MemoryKind(kind_str)
    except ValueError:
        return default or MemoryKind.FACT

class MemoryKernel:
    def __init__(self, store: SQLiteStore, events: EventBus, evidence: "EvidenceStore | None" = None):
        self.store = store
        self.events = events
        self.evidence = evidence

    def write(self, kind: MemoryKind, key: str, content: str, trace_id: str, mission_id: str | None = None, source_evidence_id: str | None = None, confidence: float = 1.0) -> MemoryRecord:
        if kind == MemoryKind.UNVERIFIED_INFERENCE:
            return self.propose(kind, key, content, trace_id, mission_id, source_evidence_id, confidence)
        # Evidence-binding enforcement: mission-scoped committed memories SHOULD have
        # evidence linkage per NSEC 第四十三条. DECISION/FAILURE/FAILURE_EXPERIENCE/PATCH
        # require evidence when tied to a mission. System-level kinds and working memory
        # are exempt.
        _EVIDENCE_REQUIRED_KINDS = {
            MemoryKind.DECISION, MemoryKind.FAILURE,
            MemoryKind.FAILURE_EXPERIENCE, MemoryKind.PATCH,
        }
        evidence_bound = bool(source_evidence_id)
        if not evidence_bound and kind in _EVIDENCE_REQUIRED_KINDS and mission_id:
            raise ValueError(
                f"memory_requires_evidence: kind={kind.value} requires "
                f"source_evidence_id when bound to a mission"
            )
        record = MemoryRecord(
            memory_id=new_id("memory"), mission_id=mission_id, kind=kind, key=key,
            content=content, source_evidence_id=source_evidence_id, confidence=confidence,
            status="committed", verified=evidence_bound, canonical=evidence_bound,
        )
        self.store.save_record(record.memory_id, "memory", record.model_dump(mode="json"), record.created_at, mission_id)
        self.events.publish("memory.written", mission_id or "global", "mission" if mission_id else "memory", "memory_kernel", trace_id, {"memory_id": record.memory_id, "kind": kind.value, "evidence_bound": evidence_bound})
        return record

    def verify_evidence_binding(self, mission_id: str | None = None) -> dict[str, Any]:
        """Verify that all committed memories have valid evidence bindings.

        Returns a structured report of violations and integrity status.
        """
        records = self.inspect(mission_id)
        violations: list[dict[str, Any]] = []
        bound = 0
        unbound = 0
        exempt = 0

        for r in records:
            if r.get("status") != "committed":
                continue
            kind_str = r.get("kind", "")
            try:
                kind = MemoryKind(kind_str)
            except ValueError:
                kind = MemoryKind.FACT

            evidence_id = str(r.get("source_evidence_id") or "")
            evidence_valid = False
            if evidence_id and self.evidence is not None:
                try:
                    envelope = self.store.get_record_envelope(evidence_id)
                    evidence_valid = bool(
                        envelope
                        and envelope.get("mission_id") == r.get("mission_id")
                        and self.evidence.verify(evidence_id)
                    )
                except (KeyError, ValueError, RuntimeError):
                    evidence_valid = False
            elif evidence_id:
                envelope = self.store.get_record_envelope(evidence_id)
                evidence_valid = bool(envelope and envelope.get("mission_id") == r.get("mission_id"))
            is_exempt = kind in {MemoryKind.SHORT_TERM, MemoryKind.TEMPORARY_CONTEXT, MemoryKind.UNVERIFIED_INFERENCE}

            if evidence_valid:
                bound += 1
            elif is_exempt:
                exempt += 1
            else:
                unbound += 1
                violations.append({
                    "memory_id": r.get("memory_id"),
                    "kind": kind_str,
                    "key": r.get("key"),
                    "has_evidence": bool(evidence_id),
                    "evidence_valid": evidence_valid,
                    "source_evidence_id": evidence_id,
                })

        return {
            "total_committed": bound + unbound + exempt,
            "evidence_bound": bound,
            "unbound": unbound,
            "exempt": exempt,
            "violations": violations,
            "all_bound": unbound == 0,
        }

    def patch(self, mission_id: str, key: str, content: str, trace_id: str, evidence_id: str | None = None, *, idempotency_key: str | None = None) -> MemoryRecord:
        if idempotency_key:
            raw_idem = self.store.find_record("memory_idempotency", "idempotency_key", idempotency_key)
            idem_envelope = self.store.find_record_envelope("memory_idempotency", "idempotency_key", idempotency_key)

            if raw_idem and not idem_envelope:
                raise ValueError("memory_idempotency_integrity_invalid")

            if idem_envelope:
                mapping = idem_envelope["payload"]
                if (
                    idem_envelope.get("mission_id") != mission_id
                    or mapping.get("idempotency_key") != idempotency_key
                    or not mapping.get("memory_id")
                ):
                    raise ValueError("memory_idempotency_conflict")

                mem_id = mapping["memory_id"]
                raw_mem = self.store.get_record(mem_id)
                mem_envelope = self.store.get_record_envelope(mem_id)

                if raw_mem and not mem_envelope:
                    raise ValueError("memory_record_integrity_invalid")

                if not mem_envelope:
                    raise ValueError("memory_record_not_found")

                if mem_envelope.get("record_type") != "memory":
                    raise ValueError("memory_record_type_invalid")

                if mem_envelope.get("mission_id") != mission_id:
                    raise ValueError("memory_mission_mismatch")

                memory = MemoryRecord.model_validate(mem_envelope["payload"])
                if (
                    memory.key != key
                    or memory.content != content
                    or memory.source_evidence_id != evidence_id
                ):
                    raise ValueError("memory_idempotency_conflict")
                return memory
        result = self.propose(MemoryKind.PATCH, key, content, trace_id, mission_id, evidence_id, 1.0, auto_commit=True)
        if idempotency_key:
            self.store.save_record(new_id("memidem"), "memory_idempotency", {"idempotency_key": idempotency_key, "memory_id": result.memory_id}, result.created_at, mission_id)
        return result

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


class MemoryLayerManager:
    """Bridges MemoryKernel with RAGPipeline for four-layer memory operations.

    Layer-specific access patterns:
    - Working: session-scoped, auto-cleared
    - Episodic: mission-keyed, sequential access
    - Semantic: global knowledge base, semantic search
    - Procedural: reusable skills/patterns, templated retrieval

    Memory Patch Review flow:
    Propose → Validate → Peer Review → Approve/Reject → Apply → Evidence
    """

    def __init__(
        self,
        kernel: MemoryKernel,
        rag: "RAGPipeline | None" = None,
        *,
        enable_patch_review: bool = True,
        auto_clear_working: bool = True,
    ) -> None:
        self.kernel = kernel
        self.rag = rag
        self.enable_patch_review = enable_patch_review
        self.auto_clear_working = auto_clear_working
        self._reviews: dict[str, PatchReview] = {}
        self._patches: dict[str, list[dict[str, Any]]] = {}

    # ── Layer-specific write ──

    def write_working(
        self, key: str, content: str, trace_id: str,
        mission_id: str | None = None,
    ) -> MemoryRecord:
        """Write to working memory — ephemeral, session-scoped."""
        return self.kernel.write(
            MemoryKind.SHORT_TERM, key, content, trace_id,
            mission_id=mission_id, confidence=0.5,
        )

    def write_episodic(
        self, key: str, content: str, trace_id: str,
        mission_id: str, source_evidence_id: str | None = None,
    ) -> MemoryRecord:
        """Write to episodic memory — mission execution history."""
        return self.kernel.write(
            MemoryKind.DECISION, key, content, trace_id,
            mission_id=mission_id, source_evidence_id=source_evidence_id,
        )

    def write_semantic(
        self, key: str, content: str, trace_id: str,
        mission_id: str | None = None,
        source_evidence_id: str | None = None,
        confidence: float = 1.0,
    ) -> MemoryRecord:
        """Write to semantic memory — long-term facts and knowledge."""
        if confidence < 0.8:
            return self.kernel.propose(
                MemoryKind.FACT, key, content, trace_id,
                mission_id=mission_id,
                source_evidence_id=source_evidence_id,
                confidence=confidence,
            )
        return self.kernel.write(
            MemoryKind.FACT, key, content, trace_id,
            mission_id=mission_id,
            source_evidence_id=source_evidence_id,
            confidence=confidence,
        )

    def write_procedural(
        self, key: str, content: str, trace_id: str,
        mission_id: str | None = None,
        source_evidence_id: str | None = None,
    ) -> MemoryRecord:
        """Write to procedural memory — skills, templates, patterns."""
        return self.kernel.write(
            MemoryKind.PATCH, key, content, trace_id,
            mission_id=mission_id,
            source_evidence_id=source_evidence_id,
            confidence=1.0,
        )

    # ── Layer-specific read ──

    def read_working(self, mission_id: str | None = None) -> list[dict[str, Any]]:
        """Read working memory for a session."""
        records = self.kernel.inspect(mission_id)
        return [
            r for r in records
            if MemoryLayer.from_kind(_safe_memory_kind(r.get("kind", "short_term"))) == MemoryLayer.WORKING
        ]

    def read_episodic(self, mission_id: str) -> list[dict[str, Any]]:
        """Read episodic memory for a mission."""
        records = self.kernel.inspect(mission_id)
        return [
            r for r in records
            if MemoryLayer.from_kind(_safe_memory_kind(r.get("kind", "fact"))) == MemoryLayer.EPISODIC
        ]

    def read_semantic(self, key_filter: str | None = None) -> list[dict[str, Any]]:
        """Read semantic memory globally, optionally filtered by key prefix."""
        records = self.kernel.inspect(None)
        results = [
            r for r in records
            if MemoryLayer.from_kind(_safe_memory_kind(r.get("kind", "fact"))) == MemoryLayer.SEMANTIC
            and r.get("status") == "committed"
        ]
        if key_filter:
            results = [r for r in results if r.get("key", "").startswith(key_filter)]
        return results

    def read_procedural(self) -> list[dict[str, Any]]:
        """Read all procedural memory."""
        records = self.kernel.inspect(None)
        return [
            r for r in records
            if MemoryLayer.from_kind(_safe_memory_kind(r.get("kind", "patch"))) == MemoryLayer.PROCEDURAL
            and r.get("status") == "committed"
        ]

    # ── Semantic search via RAG ──

    def search(
        self, query: str, *,
        layers: list[str] | None = None,
        top_k: int = 10,
        mission_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across memory layers using RAG pipeline."""
        if not self.rag:
            # Fallback: keyword search in SQLite
            return self._keyword_search(query, layers, top_k)

        from .rag_pipeline import MemoryLayer as RAGLayer
        layer_filter = [RAGLayer(layer) for layer in layers] if layers else None
        result = self.rag.query(
            query, top_k=top_k, layer_filter=layer_filter,
            mission_id=mission_id, include_evaluation=True,
        )
        rag_results = [
            {
                "doc_id": r.chunk.doc_id,
                "content": r.chunk.content,
                "score": r.score,
                "citation": r.citation,
                "evidence_ref": r.evidence_ref,
                "layer": r.chunk.metadata.get("layer", ""),
            }
            for r in result.results
        ]
        # Fallback to keyword search when RAG returns nothing
        if not rag_results:
            return self._keyword_search(query, layers, top_k)
        return rag_results

    def _keyword_search(
        self, query: str, layers: list[str] | None, top_k: int,
    ) -> list[dict[str, Any]]:
        """Fallback keyword search in SQLite."""
        terms = query.lower().split()
        all_records = self.kernel.inspect(None)
        scored: list[tuple[dict[str, Any], int]] = []
        for r in all_records:
            content = (r.get("content") or "").lower()
            key = (r.get("key") or "").lower()
            score = sum(1 for t in terms if t in content or t in key)
            if score > 0:
                layer = MemoryLayer.from_kind(_safe_memory_kind(r.get("kind", "fact")))
                if layers and layer not in layers:
                    continue
                scored.append((r, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {"memory_id": r.get("memory_id"), "content": r.get("content"),
             "key": r.get("key"), "score": float(s),
             "layer": MemoryLayer.from_kind(_safe_memory_kind(r.get("kind", "fact"))),
             "evidence_ref": r.get("source_evidence_id", "")}
            for r, s in scored[:top_k]
        ]

    # ── Memory Patch Review Flow ──

    def propose_patch(
        self, key: str, content: str, trace_id: str,
        mission_id: str | None = None,
        evidence_id: str | None = None,
    ) -> dict[str, Any]:
        """Propose a memory patch — starts the review flow."""
        # When patch review is enabled and evidence-backed, create pending record first
        if self.enable_patch_review and evidence_id:
            # Create a pending patch that requires review before becoming canonical
            pending_id = new_id("pending_mem")
            pending_record = {
                "memory_id": pending_id,
                "key": key,
                "content": content,
                "layer": "working",
                "status": "pending_review",
                "mission_id": mission_id or "global",
                "created_at": now_iso(),
                "trace_id": trace_id,
                "source_evidence_id": evidence_id,
            }
            self.kernel.store.save_record(pending_id, "memory", pending_record, now_iso(), mission_id or "global")

            review = PatchReview(
                memory_id=pending_id,
                patch_key=key,
                patch_content=content,
                evidence_refs=[evidence_id] if evidence_id else [],
            )
            self._reviews[review.review_id] = review

            return {"memory_id": pending_id, "status": "pending_review", "review_id": review.review_id}

        # Non-evidence or review-disabled: commit directly
        record = self.kernel.patch(
            mission_id or "global", key, content, trace_id, evidence_id,
        )

        if self.enable_patch_review:
            review = PatchReview(
                memory_id=record.memory_id,
                patch_key=key,
                patch_content=content,
                evidence_refs=[evidence_id] if evidence_id else [],
            )
            self._reviews[review.review_id] = review

        patches = self._patches.setdefault(key, [])
        patches.append({
            "memory_id": record.memory_id,
            "content": content,
            "status": record.status,
            "created_at": record.created_at,
        })

        return {
            "memory_id": record.memory_id,
            "key": key,
            "status": record.status,
            "review_id": getattr(
                next((r for r in self._reviews.values() if r.memory_id == record.memory_id), None),
                "review_id", "",
            ) if self.enable_patch_review else "",
        }

    def review_patch(
        self, review_id: str, decision: str, reviewer: str, reason: str = "",
    ) -> PatchReview:
        """Review a pending patch — approve, reject, or request changes."""
        review = self._reviews.get(review_id)
        if not review:
            raise KeyError(f"patch_review_not_found:{review_id}")
        if review.decision != "pending":
            raise ValueError(f"patch_already_reviewed:{review.decision}")

        valid_decisions = {"approved", "rejected", "changes_requested"}
        if decision not in valid_decisions:
            raise ValueError(f"invalid_review_decision:{decision}")

        review.decision = decision
        review.reviewer = reviewer
        review.reason = reason
        review.decided_at = now_iso()

        # If approved, commit the candidate
        if decision == "approved":
            self.kernel.commit_candidate(review.memory_id, f"patch_review:{review_id}", reviewer)

        return review

    def get_patch_history(self, key: str) -> list[dict[str, Any]]:
        """Get the patch history for a key."""
        return self._patches.get(key, [])

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        """Get all pending patch reviews."""
        return [
            {
                "review_id": r.review_id,
                "memory_id": r.memory_id,
                "key": r.patch_key,
                "content_preview": r.patch_content[:100],
                "decision": r.decision,
                "created_at": r.created_at,
            }
            for r in self._reviews.values()
            if r.decision == "pending"
        ]

    # ── Sync with RAG ──

    def sync_to_rag(self) -> int:
        """Sync committed memories from kernel to RAG pipeline."""
        if not self.rag:
            return 0
        count = 0
        for record in self.kernel.inspect(None):
            if record.get("status") != "committed":
                continue
            kind = MemoryKind(record.get("kind", "fact"))
            content = record.get("content", "")
            if not content.strip():
                continue
            from .rag_pipeline import Document
            doc = Document(
                content=content,
                metadata={
                    "key": record.get("key", ""),
                    "kind": kind.value,
                    "memory_id": record.get("memory_id", ""),
                },
                source_evidence_id=record.get("source_evidence_id", ""),
                mission_id=record.get("mission_id", ""),
                memory_kind=kind,
            )
            n = self.rag.index_document(doc)
            count += n
        return count

    # ── Lifecycle ──

    def clear_working_for_mission(self, mission_id: str) -> int:
        """Clear working memory for a specific mission."""
        count = 0
        for record in self.read_working(mission_id):
            # Mark as cleared by updating status
            memory_id = record.get("memory_id", "")
            if memory_id:
                updated = dict(record)
                updated["status"] = "cleared"
                updated["cleared_at"] = now_iso()
                self.kernel.store.save_record(memory_id, "memory", updated, now_iso(), mission_id)
            count += 1
        return count

    def stats(self) -> dict[str, Any]:
        """Return memory statistics across all layers."""
        all_records = self.kernel.inspect(None)
        layer_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for r in all_records:
            layer = MemoryLayer.from_kind(_safe_memory_kind(r.get("kind", "fact")))
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            status = r.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "total": len(all_records),
            "layers": layer_counts,
            "statuses": status_counts,
            "pending_reviews": len(self.get_pending_reviews()),
            "rag_synced": self.rag is not None,
            "rag_stats": self.rag.stats() if self.rag else {},
        }
