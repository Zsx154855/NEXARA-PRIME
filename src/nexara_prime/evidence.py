from __future__ import annotations

import hashlib
import json
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .models import EvidenceArtifact, new_id


class EvidenceStore:
    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    def add(
        self,
        mission_id: str,
        kind: str,
        title: str,
        content: str,
        trace_id: str,
        source_event_id: str | None = None,
        *,
        task_id: str | None = None,
        tool_invocation_id: str | None = None,
        actor: str = "system",
        mime_type: str = "text/plain",
        source: str = "runtime",
        verification_status: str = "unverified",
        parent_evidence: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> EvidenceArtifact:
        if idempotency_key:
            existing = self.store.find_record("evidence", "idempotency_key", idempotency_key)
            if existing:
                return EvidenceArtifact.model_validate(existing)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        artifact = EvidenceArtifact(
            evidence_id=new_id("evidence"),
            mission_id=mission_id,
            kind=kind,
            title=title,
            content=content,
            sha256=digest,
            task_id=task_id,
            tool_invocation_id=tool_invocation_id,
            actor=actor,
            mime_type=mime_type,
            source=source,
            verification_status=verification_status,
            parent_evidence=parent_evidence or [],
            idempotency_key=idempotency_key,
            source_event_id=source_event_id,
        )
        payload = artifact.model_dump(mode="json")
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        self.store.save_record(artifact.evidence_id, "evidence", payload, artifact.created_at, mission_id)
        event = self.events.publish("evidence.created", mission_id, "mission", "evidence_store", trace_id, {"evidence_id": artifact.evidence_id, "kind": kind}, idempotency_key=idempotency_key)
        artifact.source_event_id = artifact.source_event_id or event.event_id
        return artifact

    def verify(self, evidence_id: str) -> bool:
        raw = self.store.get_record(evidence_id)
        if not raw:
            raise KeyError(f"evidence_not_found:{evidence_id}")
        digest = hashlib.sha256(str(raw.get("content", "")).encode("utf-8")).hexdigest()
        verified = digest == raw.get("sha256")
        raw["verification_status"] = "verified" if verified else "corrupt"
        self.store.save_record(evidence_id, "evidence", raw, raw.get("created_at", ""), raw.get("mission_id"))
        return verified

    def verify_all(self, mission_id: str | None = None) -> dict[str, Any]:
        artifacts = self.list(mission_id)
        valid = sum(1 for item in artifacts if hashlib.sha256(str(item.get("content", "")).encode("utf-8")).hexdigest() == item.get("sha256"))
        return {"total": len(artifacts), "valid": valid, "invalid": len(artifacts) - valid, "coverage": (valid / len(artifacts)) if artifacts else 0.0}

    def state_change(self, mission_id: str, from_state: str, to_state: str, trace_id: str, event_id: str | None = None) -> EvidenceArtifact:
        return self.add(
            mission_id,
            "state_transition",
            f"{from_state} → {to_state}",
            f"Mission {mission_id} transitioned from {from_state} to {to_state}.",
            trace_id,
            event_id,
            actor="state_machine",
            source="mission.state_changed",
            verification_status="verified",
        )

    def list(self, mission_id: str | None = None) -> list[dict]:
        return self.store.list_records("evidence", mission_id)
