"""MemoryController — four-layer memory governance with persistence, ranking, decay, and health.

Layers: Working → Episodic → Semantic → Procedural
Every memory write MUST be bound to evidence for non-working layers.
Phase 1 enhancement: persistent storage via BrainDB, ranked retrieval, decay model, health metrics.

Existing interface preserved: commit(), recall(), consolidate(), summary().
New methods: rank_retrieve(), cross_layer_query(), health_report(), decay_tick(), get_provenance().
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import new_id, now_iso

from .db import BrainDB
from .decay_config import (
    compute_decayed_confidence,
    get_half_life,
    get_min_confidence,
)
from .consolidation_rules import (
    classify_layer,
    should_promote_working_to_semantic,
    can_consolidate_episodic_to_semantic,
)
from .provenance import ProvenanceTracker


# Kind classification that requires evidence binding
EVIDENCE_REQUIRED_KINDS: set[str] = {
    "decision", "experience", "failure", "failure_experience", "patch",
    "skill_improvement", "system_rule",
    "fact", "user_fact", "project_fact", "preference",
}

EVIDENCE_OPTIONAL_KINDS: set[str] = {
    "short_term", "temporary_context", "unverified_inference",
}


class MemoryController:
    """Governs memory operations across four layers with persistence."""

    name = "memory_controller"

    def __init__(self, db: BrainDB | None = None, persist: bool = True) -> None:
        self._db = db or BrainDB()
        self._persist = persist
        self._provenance = ProvenanceTracker(self._db)

        # In-memory caches (fast path, backed by DB when persist=True)
        self._working: list[dict[str, Any]] = []
        self._episodic: list[dict[str, Any]] = []
        self._semantic: list[dict[str, Any]] = []
        self._procedural: list[dict[str, Any]] = []

    # ── Core: commit (enhanced with persistence + evidence binding) ──

    def commit(
        self,
        mission_id: str,
        key: str,
        content: str,
        kind: str,
        evidence_id: str | None = None,
        confidence: float = 1.0,
        provenance_source_file: str = "",
        provenance_commit_sha: str = "",
    ) -> str:
        """Commit a memory with mandatory evidence binding for non-working layers."""
        memory_id = new_id("mem")
        layer = self._classify_layer(kind)
        half_life = get_half_life(kind) if kind in EVIDENCE_REQUIRED_KINDS else None
        now = now_iso()

        # Enforce evidence binding
        if kind in EVIDENCE_REQUIRED_KINDS and not evidence_id:
            raise ValueError(
                f"memory_evidence_required: kind={kind} requires evidence_id"
            )

        entry = {
            "memory_id": memory_id,
            "mission_id": mission_id,
            "key": key,
            "content": content,
            "kind": kind,
            "layer": layer,
            "confidence": confidence,
            "decay_rate": 0.0,
            "half_life_seconds": half_life,
            "evidence_id": evidence_id,
            "provenance_chain": "",
            "access_count": 0,
            "last_accessed": None,
            "consolidated_from": None,
            "superseded_by": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        # Persist to DB
        if self._persist:
            self._db.insert_memory(entry)

        # Record provenance if evidence-bound
        if evidence_id:
            self._provenance.record(
                memory_id=memory_id,
                evidence_id=evidence_id,
                source_file=provenance_source_file,
                commit_sha=provenance_commit_sha,
            )
            entry["provenance_chain"] = f"{memory_id}→{evidence_id}"

        # In-memory cache
        target = getattr(self, f"_{layer}")
        target.append(entry)

        return memory_id

    # ── Core: recall (enhanced with ranking support) ──

    def recall(
        self, mission_id: str, layer: str | None = None
    ) -> list[dict[str, Any]]:
        """Recall memories for a mission, optionally filtered by layer."""
        if self._persist:
            records = self._db.recall(mission_id=mission_id, layer=layer)
        else:
            records = []
            layers = [layer] if layer else ["working", "episodic", "semantic", "procedural"]
            for lyr in layers:
                target = getattr(self, f"_{lyr}", [])
                records.extend(e for e in target if e.get("mission_id") == mission_id)

        # Log access
        for r in records:
            mid = r.get("memory_id", "")
            if mid:
                self._db.log_access(mid, "recall")

        return records

    # ── Core: consolidate (enhanced with DB logging) ──

    def consolidate(self, mission_id: str) -> list[str]:
        """Consolidate episodic memories into semantic. Returns consolidated IDs."""
        consolidated: list[str] = []
        episodic = [e for e in self._episodic if e.get("mission_id") == mission_id]
        if self._persist:
            episodic = self._db.recall(
                mission_id=mission_id, layer="episodic"
            ) or episodic

        for entry in episodic:
            if not can_consolidate_episodic_to_semantic(
                entry.get("kind", ""), entry.get("layer", "")
            ):
                continue

            new_id_val = new_id("mem")
            semantic_entry = dict(entry)
            semantic_entry["memory_id"] = new_id_val
            semantic_entry["layer"] = "semantic"
            semantic_entry["consolidated_from"] = entry["memory_id"]
            semantic_entry["created_at"] = now_iso()
            semantic_entry["updated_at"] = now_iso()

            if self._persist:
                self._db.insert_memory(semantic_entry)
                self._db.log_consolidation(
                    source_id=entry["memory_id"],
                    target_id=new_id_val,
                    from_layer="episodic",
                    to_layer="semantic",
                    trigger="mission_complete",
                )

            self._semantic.append(semantic_entry)
            consolidated.append(new_id_val)

        return consolidated

    # ── Core: summary ──

    def summary(self) -> dict[str, Any]:
        if self._persist:
            layer_counts = self._db.count_by_layer()
            return {
                "working_count": layer_counts.get("working", 0),
                "episodic_count": layer_counts.get("episodic", 0),
                "semantic_count": layer_counts.get("semantic", 0),
                "procedural_count": layer_counts.get("procedural", 0),
                "total": sum(layer_counts.values()),
            }
        return {
            "working_count": len(self._working),
            "episodic_count": len(self._episodic),
            "semantic_count": len(self._semantic),
            "procedural_count": len(self._procedural),
            "total": len(self._working) + len(self._episodic) + len(self._semantic) + len(self._procedural),
        }

    # ── NEW: Ranked retrieval ──

    def rank_retrieve(
        self,
        query: str,
        top_k: int = 10,
        layers: list[str] | None = None,
        min_confidence: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Ranked retrieval with relevance + recency + confidence scoring."""
        records = self._db.recall() if self._persist else (
            self._working + self._episodic + self._semantic + self._procedural
        )
        records = [r for r in records if r.get("status") == "active"]

        if layers:
            records = [r for r in records if r.get("layer") in layers]

        query_lower = query.lower()
        scored: list[tuple[dict[str, Any], float]] = []

        for r in records:
            confidence = float(r.get("confidence", 1.0))
            if confidence < min_confidence:
                continue

            # Relevance score (keyword match)
            content = (r.get("content") or "").lower()
            key = (r.get("key") or "").lower()
            terms = query_lower.split()
            relevance = sum(1.0 for t in terms if t in content or t in key) / max(len(terms), 1)

            # Recency score (exponential decay from creation)
            created = r.get("created_at", "")
            recency = 0.5
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                    recency = max(0.1, 1.0 - min(age_hours / (24 * 30), 0.9))  # decays over ~30 days
                except (ValueError, TypeError):
                    pass

            # Combined score: relevance 0.5 + recency 0.25 + confidence 0.25
            combined = relevance * 0.5 + recency * 0.25 + confidence * 0.25
            scored.append((r, combined))

        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for r, score in scored[:top_k]:
            entry = dict(r)
            entry["relevance_score"] = score
            results.append(entry)
            # Log access
            self._db.log_access(r.get("memory_id", ""), "rank_retrieve", query)

        return results

    # ── NEW: Cross-layer query ──

    def cross_layer_query(
        self, query: str, min_confidence: float = 0.3
    ) -> dict[str, Any]:
        """Transparent query across all 4 layers. Returns grouped results."""
        result: dict[str, Any] = {
            "working": [],
            "episodic": [],
            "semantic": [],
            "procedural": [],
            "total_count": 0,
        }

        for layer in ["working", "episodic", "semantic", "procedural"]:
            ranked = self.rank_retrieve(
                query=query, top_k=25, layers=[layer], min_confidence=min_confidence,
            )
            result[layer] = ranked
            result["total_count"] += len(ranked)

        return result

    # ── NEW: Health metrics ──

    def health_report(self) -> dict[str, Any]:
        """Generate memory health report with coverage, freshness, consistency."""
        active = self._db.count_active() if self._persist else sum(
            len(getattr(self, f"_{lyr}")) for lyr in ["_working", "_episodic", "_semantic", "_procedural"]
        )
        stale = self._db.count_stale() if self._persist else 0
        archived = 0  # archived entries not tracked in Phase 1 in-memory

        layer_dist = self._db.count_by_layer() if self._persist else {
            "working": len(self._working),
            "episodic": len(self._episodic),
            "semantic": len(self._semantic),
            "procedural": len(self._procedural),
        }
        kind_dist = self._db.count_by_kind() if self._persist else {}

        # Coverage: how many of 13 kinds have at least 1 active record
        coverage = sum(1 for k in kind_dist if kind_dist[k] > 0) / 13.0 if kind_dist else 0.0

        # Freshness: ratio of active to total (including archived)
        total = active + stale + archived
        freshness = active / total if total > 0 else 0.0

        # Consistency: ratio of records with evidence binding
        evidence_bound = 0
        if self._persist:
            all_records = self._db.recall()
            evidence_bound = sum(1 for r in all_records if r.get("evidence_id"))
        consistency = evidence_bound / active if active > 0 else 0.0

        snapshot = {
            "snapshot_id": new_id("health"),
            "total_memories": total,
            "active_count": active,
            "stale_count": stale,
            "archived_count": archived,
            "coverage_score": round(coverage, 3),
            "freshness_score": round(freshness, 3),
            "consistency_score": round(consistency, 3),
            "layer_distribution": layer_dist,
            "kind_distribution": kind_dist,
            "taken_at": now_iso(),
        }

        if self._persist:
            self._db.save_health_snapshot(snapshot)

        return snapshot

    # ── NEW: Decay tick ──

    def decay_tick(self) -> dict[str, Any]:
        """Apply decay to all active memories. Returns affected counts per kind."""
        if not self._persist:
            return {"affected": 0, "by_kind": {}}

        all_records = self._db.recall()
        now_dt = datetime.now(timezone.utc)
        affected: dict[str, int] = {}

        for r in all_records:
            kind = r.get("kind", "")
            half_life = get_half_life(kind)
            if half_life <= 0:
                continue  # never decays

            created_str = r.get("created_at", "")
            if not created_str:
                continue

            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                elapsed = (now_dt - created_dt).total_seconds()
            except (ValueError, TypeError):
                continue

            confidence = float(r.get("confidence", 1.0))
            min_conf = get_min_confidence(kind)
            new_confidence = compute_decayed_confidence(
                confidence, half_life, elapsed, min_conf,
            )

            if new_confidence < confidence:
                self._db.update_memory(r["memory_id"], {"confidence": new_confidence})
                affected[kind] = affected.get(kind, 0) + 1

        return {
            "affected": sum(affected.values()),
            "by_kind": affected,
            "tick_at": now_iso(),
        }

    # ── NEW: Provenance ──

    def get_provenance(self, memory_id: str) -> dict[str, Any] | None:
        return self._provenance.get_chain(memory_id)

    def verify_provenance(self, memory_id: str) -> bool:
        return self._provenance.verify_chain(memory_id)

    # ── Classification ──

    @staticmethod
    def _classify_layer(kind: str) -> str:
        return classify_layer(kind)

    def classify_with_confidence(
        self, kind: str, content: str, access_count: int = 0,
    ) -> tuple[str, float, float]:
        """Classify with confidence and decay_rate output."""
        layer = self._classify_layer(kind)
        half_life = get_half_life(kind)
        confidence = 1.0
        if half_life > 0:
            confidence = get_min_confidence(kind) + 0.5  # initial above floor

        # Adjust for promoted memories
        if should_promote_working_to_semantic(access_count) and layer == "working":
            layer = "semantic"
            confidence = 0.9

        decay_rate = 0.0 if half_life <= 0 else 1.0 / half_life
        return layer, confidence, decay_rate
