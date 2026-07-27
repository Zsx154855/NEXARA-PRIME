"""KnowledgeGraph — structured entity-relation graph from semantic memory.

17 relation types (11 existing + 6 new). 6 entity types.
Reads from MemoryController.rank_retrieve() through interface.
NEVER imports runtime, evidence, or tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..models import new_id, now_iso

if TYPE_CHECKING:
    from .memory_controller import MemoryController


# ── Relation types (17 total) ──

RELATION_TYPES = {
    # Existing 11
    "RELATES_TO", "DERIVED_FROM", "SUPERSEDES", "CONFLICTS_WITH",
    "SUPPORTS", "REFUTES", "CAUSES", "PREVENTS", "REQUIRES",
    "EXEMPLIFIES", "GENERALIZES",
    # New 6
    "PREFERS", "AVOIDS", "EVOLVED_FROM", "CONTRADICTS",
    "SUPPORTS_BY_EVIDENCE", "DEPENDS_ON",
}

ENTITY_TYPES = {"Concept", "Tool", "Decision", "Pattern", "Person", "File"}


# ── Data classes ──

@dataclass
class Entity:
    entity_id: str = field(default_factory=lambda: new_id("ent"))
    entity_type: str = "Concept"
    label: str = ""
    source_memory_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    superseded_by: str | None = None


@dataclass
class Relation:
    relation_id: str = field(default_factory=lambda: new_id("rel"))
    source_entity: str = ""
    target_entity: str = ""
    relation_type: str = "RELATES_TO"
    confidence: float = 1.0
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)


@dataclass
class Subgraph:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    root_entity: str = ""
    depth: int = 0


@dataclass
class PruneResult:
    removed_count: int = 0
    superseded_count: int = 0
    pruned_at: str = field(default_factory=now_iso)


# ── Knowledge Graph ──

class KnowledgeGraph:
    """Structured entity-relation graph. 6 entity types, 17 relation types."""

    name = "knowledge_graph"

    def __init__(self, memory: "MemoryController | None" = None) -> None:
        self._entities: dict[str, Entity] = {}
        self._relations: dict[str, Relation] = {}
        self._memory = memory

    def bind(self, memory: "MemoryController") -> None:
        self._memory = memory

    # ── Entity extraction ──

    def extract_entities(self, memories: list[dict[str, Any]]) -> list[Entity]:
        """Parse memory content into typed entities."""
        entities: list[Entity] = []

        for mem in memories:
            content = str(mem.get("content", ""))
            key = str(mem.get("key", ""))
            kind = str(mem.get("kind", ""))
            confidence = float(mem.get("confidence", 1.0))
            memory_id = str(mem.get("memory_id", ""))

            # Entity type inference from memory kind
            etype = self._infer_entity_type(kind, content)

            entity = Entity(
                entity_type=etype,
                label=content[:120] if content else key,
                source_memory_ids=[memory_id] if memory_id else [],
                confidence=confidence,
                properties={"key": key, "kind": kind},
            )
            entities.append(entity)
            self._entities[entity.entity_id] = entity

        return entities

    @staticmethod
    def _infer_entity_type(kind: str, content: str) -> str:
        mapping = {
            "decision": "Decision",
            "failure": "Pattern",
            "failure_experience": "Pattern",
            "skill_improvement": "Pattern",
            "system_rule": "Concept",
            "user_fact": "Person",
            "project_fact": "Concept",
            "preference": "Pattern",
            "patch": "Tool",
            "fact": "Concept",
        }
        return mapping.get(kind, "Concept")

    # ── Relation inference ──

    def infer_relations(
        self, entities: list[Entity], memories: list[dict[str, Any]],
    ) -> list[Relation]:
        """Infer relations from entity co-occurrence and memory metadata."""
        relations: list[Relation] = []

        for i, e1 in enumerate(entities):
            for j, e2 in enumerate(entities):
                if i >= j:
                    continue

                # Co-occurrence: same mission/key overlap
                mem_ids1 = set(e1.source_memory_ids)
                mem_ids2 = set(e2.source_memory_ids)
                shared = mem_ids1 & mem_ids2

                if shared:
                    # Entities from shared memories → RELATED_TO
                    rtype = "RELATES_TO"
                    if e1.entity_type == "Decision" and e2.entity_type == "Pattern":
                        rtype = "DERIVED_FROM"
                    elif e1.entity_type == "Person" and e2.entity_type == "Pattern":
                        rtype = "PREFERS"

                    rel = Relation(
                        source_entity=e1.entity_id,
                        target_entity=e2.entity_id,
                        relation_type=rtype,
                        confidence=min(e1.confidence, e2.confidence),
                        evidence_ids=list(shared),
                    )
                    relations.append(rel)
                    self._relations[rel.relation_id] = rel

        return relations

    # ── Graph traversal ──

    def traverse(
        self,
        start_entity: str,
        max_depth: int = 3,
        relation_filter: list[str] | None = None,
    ) -> Subgraph:
        """BFS from start entity, returning connected subgraph."""
        if start_entity not in self._entities:
            return Subgraph(root_entity=start_entity)

        visited_entities: set[str] = set()
        visited_relations: set[str] = set()
        queue: list[tuple[str, int]] = [(start_entity, 0)]

        while queue:
            eid, depth = queue.pop(0)
            if eid in visited_entities:
                continue
            visited_entities.add(eid)

            if depth >= max_depth:
                continue

            for rel in self._relations.values():
                if rel.relation_id in visited_relations:
                    continue
                if relation_filter and rel.relation_type not in relation_filter:
                    continue

                if rel.source_entity == eid and rel.target_entity not in visited_entities:
                    visited_relations.add(rel.relation_id)
                    queue.append((rel.target_entity, depth + 1))
                elif rel.target_entity == eid and rel.source_entity not in visited_entities:
                    visited_relations.add(rel.relation_id)
                    queue.append((rel.source_entity, depth + 1))

        return Subgraph(
            entities=[self._entities[eid] for eid in visited_entities if eid in self._entities],
            relations=[rel for rid, rel in self._relations.items() if rid in visited_relations],
            root_entity=start_entity,
            depth=max_depth,
        )

    # ── Confidence scoring ──

    def score_confidence(self, entity: Entity) -> float:
        """Bayesian confidence: average of source memory confidences weighted by evidence count."""
        if not entity.source_memory_ids:
            return entity.confidence

        total_conf = entity.confidence
        evidence_count = len(entity.source_memory_ids)
        relation_count = sum(
            1 for r in self._relations.values()
            if r.source_entity == entity.entity_id or r.target_entity == entity.entity_id
        )

        # More relations + more evidence → higher confidence
        evidence_bonus = min(0.3, evidence_count * 0.05)
        relation_bonus = min(0.2, relation_count * 0.02)

        return min(1.0, total_conf + evidence_bonus + relation_bonus)

    # ── Pruning ──

    def prune(self, min_confidence: float = 0.2, max_age_days: int = 180) -> PruneResult:
        """Remove low-confidence entities. Superseded entities flagged, not deleted."""
        removed = 0
        superseded = 0

        to_remove = []
        for eid, entity in list(self._entities.items()):
            if entity.superseded_by:
                superseded += 1
                continue
            if entity.confidence < min_confidence:
                to_remove.append(eid)

        for eid in to_remove:
            del self._entities[eid]
            removed += 1

        # Also prune orphaned relations
        for rid, rel in list(self._relations.items()):
            if rel.source_entity not in self._entities or rel.target_entity not in self._entities:
                del self._relations[rid]

        return PruneResult(removed_count=removed, superseded_count=superseded)

    # ── Export ──

    def export_graphviz(self) -> str:
        """Export to Graphviz DOT format."""
        lines = ["digraph KnowledgeGraph {", "  rankdir=LR;", '  node [shape=box, style=rounded];']
        for eid, entity in self._entities.items():
            label = entity.label[:40].replace('"', "'")
            lines.append(f'  "{eid}" [label="{entity.entity_type}: {label}"];')
        for rel in self._relations.values():
            lines.append(f'  "{rel.source_entity}" -> "{rel.target_entity}" [label="{rel.relation_type}"];')
        lines.append("}")
        return "\n".join(lines)

    # ── Query ──

    def entity_count(self) -> int:
        return len(self._entities)

    def relation_count(self) -> int:
        return len(self._relations)

    def get_entity(self, entity_id: str) -> Entity | None:
        return self._entities.get(entity_id)

    def health(self) -> dict[str, Any]:
        return {
            "component": self.name,
            "entities": self.entity_count(),
            "relations": self.relation_count(),
            "entity_types": {t: sum(1 for e in self._entities.values() if e.entity_type == t) for t in ENTITY_TYPES},
            "relation_types": {t: sum(1 for r in self._relations.values() if r.relation_type == t) for t in RELATION_TYPES},
        }
