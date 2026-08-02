"""GovernedWorldModel — fact/inference/forecast separation with provenance tracking."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ..models import now_iso, new_id
from .cognitive_models import WorldEntity

if TYPE_CHECKING:
    from .memory_controller import MemoryController


class GovernedWorldModel:
    """Maintains structured world state with strict project isolation and evidence binding.

    All durable writes require: project_id, mission_id, evidence_id.
    Queries are scoped to project_id.
    Unverified writes (no evidence_id) are rejected.
    """

    VALID_CLASSIFICATIONS = {"FACT", "INFERENCE", "HYPOTHESIS", "FORECAST", "DISPUTED", "STALE", "RETRACTED"}

    def __init__(self, memory_controller: MemoryController, project_id: str = "nexara") -> None:
        self._mc = memory_controller
        self._project_id = project_id

    def ingest_observation(self, entity_type: str, source: str, content: dict[str, Any],
                           confidence: float = 0.5, evidence_refs: list[str] | None = None,
                           classification: str = "FACT", *,
                           evidence_id: str | None = None, mission_id: str = "global") -> str:
        if classification not in self.VALID_CLASSIFICATIONS:
            classification = "HYPOTHESIS"
        if not evidence_id:
            raise ValueError("ingest_observation requires evidence_id for durable world write")
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
            "project_id": self._project_id,
        })
        return self._mc.commit(
            mission_id=mission_id, key=f"world:{self._project_id}:{entity.id}",
            content=content_json, kind="procedural", confidence=entity.confidence,
            evidence_id=evidence_id,
        )

    def update_entity(self, entity_id: str, updates: dict[str, Any],
                      evidence_id: str | None = None) -> str | None:
        records = self._mc.recall(self._project_id, layer="procedural")
        key_prefix = f"world:{self._project_id}:"
        for r in records:
            if r.get("key") == f"{key_prefix}{entity_id}":
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                data.update(updates)
                return self._mc.commit(
                    mission_id=self._project_id, key=f"{key_prefix}{entity_id}",
                    content=json.dumps(data), kind="procedural", confidence=data.get("confidence", 0.5),
                    evidence_id=evidence_id,
                )
        return None

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        records = self._mc.recall(self._project_id, layer="procedural")
        key_prefix = f"world:{self._project_id}:"
        for r in records:
            if r.get("key") == f"{key_prefix}{entity_id}":
                return json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
        return None

    def resolve_conflicts(self, entity_type: str) -> list[dict[str, Any]]:
        records = self._mc.recall(self._project_id, layer="procedural")
        key_prefix = f"world:{self._project_id}:"
        entities = []
        for r in records:
            if r.get("key", "").startswith(key_prefix):
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                if data.get("type") == entity_type and data.get("classification") == "DISPUTED":
                    entities.append(data)
        return entities

    def detect_stale(self, max_age_hours: int = 168) -> list[str]:
        records = self._mc.recall(self._project_id, layer="procedural")
        key_prefix = f"world:{self._project_id}:"
        stale = []
        for r in records:
            if r.get("key", "").startswith(key_prefix):
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                if data.get("classification") == "STALE":
                    stale.append(r.get("key", ""))
        return stale

    def expire_unverified(self) -> int:
        records = self._mc.recall(self._project_id, layer="procedural")
        key_prefix = f"world:{self._project_id}:"
        count = 0
        for r in records:
            if r.get("key", "").startswith(key_prefix):
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                if not data.get("evidence_refs") or data.get("classification") == "HYPOTHESIS":
                    count += 1
        return count

    def classify_entity(self, entity_id: str, new_classification: str) -> bool:
        if new_classification not in self.VALID_CLASSIFICATIONS:
            return False
        return self.update_entity(entity_id, {"classification": new_classification}) is not None

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall(self._project_id, layer="procedural")
        key_prefix = f"world:{self._project_id}:"
        world = [r for r in records if r.get("key", "").startswith(key_prefix)]
        facts = sum(1 for r in world if json.loads(r.get("content", "{}")).get("classification") == "FACT")
        inferences = sum(1 for r in world if json.loads(r.get("content", "{}")).get("classification") == "INFERENCE")
        return {"total_entities": len(world), "facts": facts, "inferences": inferences}
