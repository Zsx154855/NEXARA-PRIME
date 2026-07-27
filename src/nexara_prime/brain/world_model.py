"""GovernedWorldModel — fact/inference/forecast separation with provenance tracking."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ..models import now_iso, new_id
from .cognitive_models import WorldEntity

if TYPE_CHECKING:
    from .memory_controller import MemoryController


class GovernedWorldModel:
    """Maintains structured world state with strict fact/inference/forecast separation."""

    VALID_CLASSIFICATIONS = {"FACT", "INFERENCE", "HYPOTHESIS", "FORECAST", "DISPUTED", "STALE", "RETRACTED"}

    def __init__(self, memory_controller: MemoryController) -> None:
        self._mc = memory_controller

    def ingest_observation(self, entity_type: str, source: str, content: dict[str, Any],
                           confidence: float = 0.5, evidence_refs: list[str] | None = None,
                           classification: str = "FACT") -> str:
        if classification not in self.VALID_CLASSIFICATIONS:
            classification = "HYPOTHESIS"
        entity = WorldEntity(
            id=f"we_{new_id('we')}", type=entity_type, source=source,
            provenance=source, observed_at=now_iso(), freshness=1.0,
            confidence=min(1.0, max(0.1, confidence)),
            evidence_refs=evidence_refs or [],
            classification=classification,
        )
        content_json = json.dumps({
            "type": entity.type, "source": entity.source, "content": content,
            "classification": entity.classification, "confidence": entity.confidence,
            "evidence_refs": entity.evidence_refs, "observed_at": entity.observed_at,
        })
        return self._mc.commit(
            mission_id="global", key=f"world:{entity.id}",
            content=content_json, kind="procedural", confidence=entity.confidence,
        )

    def update_entity(self, entity_id: str, updates: dict[str, Any]) -> str | None:
        records = self._mc.recall("global", layer="procedural")
        for r in records:
            if r.get("key") == f"world:{entity_id}":
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                data.update(updates)
                return self._mc.commit(
                    mission_id="global", key=f"world:{entity_id}",
                    content=json.dumps(data), kind="procedural", confidence=data.get("confidence", 0.5),
                )
        return None

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        records = self._mc.recall("global", layer="procedural")
        for r in records:
            if r.get("key") == f"world:{entity_id}":
                return json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
        return None

    def resolve_conflicts(self, entity_type: str) -> list[dict[str, Any]]:
        records = self._mc.recall("global", layer="procedural")
        entities = []
        for r in records:
            if r.get("key", "").startswith("world:"):
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                if data.get("type") == entity_type and data.get("classification") == "DISPUTED":
                    entities.append(data)
        return entities

    def detect_stale(self, max_age_hours: int = 168) -> list[str]:
        records = self._mc.recall("global", layer="procedural")
        stale = []
        for r in records:
            if r.get("key", "").startswith("world:"):
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                if data.get("classification") == "STALE":
                    stale.append(r.get("key", ""))
        return stale

    def expire_unverified(self) -> int:
        records = self._mc.recall("global", layer="procedural")
        count = 0
        for r in records:
            if r.get("key", "").startswith("world:"):
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                if not data.get("evidence_refs") or data.get("classification") == "HYPOTHESIS":
                    count += 1
        return count

    def classify_entity(self, entity_id: str, new_classification: str) -> bool:
        if new_classification not in self.VALID_CLASSIFICATIONS:
            return False
        return self.update_entity(entity_id, {"classification": new_classification}) is not None

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall("global", layer="procedural")
        world = [r for r in records if r.get("key", "").startswith("world:")]
        facts = sum(1 for r in world if json.loads(r.get("content", "{}")).get("classification") == "FACT")
        inferences = sum(1 for r in world if json.loads(r.get("content", "{}")).get("classification") == "INFERENCE")
        return {"total_entities": len(world), "facts": facts, "inferences": inferences}
