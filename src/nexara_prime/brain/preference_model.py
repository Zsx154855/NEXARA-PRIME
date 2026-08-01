"""PreferenceModel — learns and applies user preferences from observed behavior."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..models import now_iso

if TYPE_CHECKING:
    from .memory_controller import MemoryController


@dataclass
class PreferenceEntity:
    key: str
    category: str
    value: str
    weight: float
    confidence: float
    evidence_id: str
    mission_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    status: str = "active"


class PreferenceModel:
    """Learns user preferences from behavior, applies decay, resolves conflicts."""

    def __init__(self, memory_controller: MemoryController) -> None:
        self._mc = memory_controller

    def record_preference(
        self, mission_id: str, key: str, category: str, value: str,
        weight: float = 1.0, confidence: float = 0.5, evidence_id: str | None = None,
    ) -> str:
        """Create preference entry. Key uniqueness enforced at application level."""
        return self._mc.commit(
            mission_id=mission_id, key=f"pref:{key}", content=self._serialize_pref(
                key=key, category=category, value=value, weight=weight,
                confidence=confidence, evidence_id=evidence_id or "",
                mission_id=mission_id,
            ),
            kind="preference", evidence_id=evidence_id, confidence=confidence,
        )

    def get_preference(self, mission_id: str, key: str) -> PreferenceEntity | None:
        """Retrieve a specific preference by key from mission records. Returns most recent."""
        records = self._mc.recall(mission_id, layer="semantic")
        found: dict | None = None
        for r in records:
            if r.get("kind") == "preference" and r.get("key") == f"pref:{key}":
                found = r
        return self._deserialize_pref(found) if found else None

    def get_all_preferences(self, mission_id: str = "global") -> list[PreferenceEntity]:
        records = self._mc.recall(mission_id, layer="semantic")
        return [self._deserialize_pref(r) for r in records if r.get("kind") == "preference" and r.get("status") == "active"]

    def rank_preferences(self, keywords: str, top_k: int = 10) -> list[PreferenceEntity]:
        records = self._mc.rank_retrieve(query=keywords, top_k=top_k * 2, layers=["semantic"], min_confidence=0.1)
        prefs = [self._deserialize_pref(r) for r in records if r.get("kind") == "preference" and r.get("status") == "active"]
        return sorted(prefs, key=lambda p: p.weight * p.confidence, reverse=True)[:top_k]

    def apply_decay(self, mission_id: str, half_life_hours: int = 168) -> int:
        """Decay preferences. Returns count of affected entries."""
        decay_factor = 0.5 ** (1.0 / max(half_life_hours, 1))
        prefs = self.get_all_preferences(mission_id)
        decayed = 0
        for p in prefs:
            new_weight = p.weight * decay_factor
            new_confidence = p.confidence * decay_factor
            self._mc.commit(mission_id, key=f"pref:{p.key}", content=self._serialize_pref(
                key=p.key, category=p.category, value=p.value,
                weight=round(new_weight, 3), confidence=round(new_confidence, 3),
                evidence_id=p.evidence_id, mission_id=mission_id,
            ), kind="preference", confidence=p.confidence)
            decayed += 1
        return decayed

    def resolve_conflict(self, mission_id: str, key: str, new_value: str, confidence: float, evidence_id: str | None = None) -> str:
        existing = self.get_preference(mission_id, key)
        if not existing:
            return self.record_preference(mission_id, key, "general", new_value, confidence=confidence, evidence_id=evidence_id)
        new_score = 99.0 if evidence_id else confidence
        old_score = existing.weight * existing.confidence
        if new_score >= old_score:
            return self.record_preference(mission_id, key, existing.category, new_value, weight=0.8, confidence=confidence, evidence_id=evidence_id)
        return self._mc.commit(mission_id, key=f"pref:{key}", content=self._serialize_pref(
            key=key, category=existing.category, value=existing.value,
            weight=existing.weight * 1.05, confidence=existing.confidence,
            evidence_id=existing.evidence_id, mission_id=mission_id,
        ), kind="preference")

    def get_profile(self, mission_id: str = "global") -> dict[str, Any]:
        prefs = self.get_all_preferences(mission_id)
        return {"total_preferences": len(prefs), "categories": list({p.category for p in prefs}), "top_keys": [(p.key, p.weight) for p in sorted(prefs, key=lambda x: x.weight, reverse=True)[:10]]}

    def summarize(self) -> dict[str, Any]:
        return self.get_profile()

    @staticmethod
    def _serialize_pref(key: str, category: str, value: str, weight: float, confidence: float, evidence_id: str, mission_id: str) -> str:
        return json.dumps({"key": key, "category": category, "value": value, "weight": weight, "confidence": confidence, "evidence_id": evidence_id, "mission_id": mission_id, "updated_at": now_iso()})

    @staticmethod
    def _deserialize_pref(record: dict) -> PreferenceEntity:
        content = record.get("content", "{}")
        data = json.loads(content) if isinstance(content, str) else content
        return PreferenceEntity(
            key=data.get("key", ""), category=data.get("category", "general"),
            value=data.get("value", ""), weight=float(data.get("weight", record.get("weight", 1.0))),
            confidence=float(data.get("confidence", record.get("confidence", 0.5))),
            evidence_id=data.get("evidence_id", record.get("evidence_id", "")),
            mission_id=record.get("mission_id", ""), status=record.get("status", "active"),
        )
