from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .models import EvidenceArtifact, new_id


class EvidenceStore:
    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    @staticmethod
    def _envelope_sha256(payload: dict[str, Any]) -> str:
        envelope = {
            "evidence_id": payload.get("evidence_id"),
            "mission_id": payload.get("mission_id"),
            "kind": payload.get("kind"),
            "sha256": payload.get("sha256"),
            "task_id": payload.get("task_id"),
            "tool_invocation_id": payload.get("tool_invocation_id"),
            "actor": payload.get("actor"),
            "source": payload.get("source"),
            "source_event_id": payload.get("source_event_id"),
            "verification_status": payload.get("verification_status"),
            "request_sha256": payload.get("request_sha256"),
        }
        encoded = json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _request_sha256(request: dict[str, Any]) -> str:
        encoded = json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _idempotent_evidence_id(idempotency_key: str) -> str:
        digest = hashlib.sha256(
            f"evidence:{idempotency_key}".encode("utf-8")
        ).hexdigest()
        return f"evidence_{digest[:12]}"

    @staticmethod
    def _artifact_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if key in EvidenceArtifact.model_fields
        }

    def _replay_artifact(
        self,
        evidence_id: str,
        expected_request: dict[str, Any],
    ) -> EvidenceArtifact:
        envelope = self.store.get_record_envelope(evidence_id)
        if (
            not envelope
            or envelope.get("record_type") != "evidence"
            or envelope.get("record_id") != evidence_id
        ):
            raise ValueError("evidence_idempotency_record_invalid")
        stored = envelope["payload"]
        if (
            stored.get("evidence_id") != evidence_id
            or stored.get("envelope_sha256") != self._envelope_sha256(stored)
        ):
            raise ValueError("evidence_idempotency_record_invalid")
        request_sha256 = stored.get("request_sha256")
        if request_sha256:
            request_matches = hmac.compare_digest(
                str(request_sha256), self._request_sha256(expected_request)
            )
        else:
            request_matches = all(
                stored.get(key) == value
                for key, value in expected_request.items()
                if key not in {"source_event_id"}
            ) and (
                expected_request.get("source_event_id") is None
                or stored.get("source_event_id") == expected_request.get("source_event_id")
            )
        if not request_matches:
            raise ValueError("evidence_idempotency_conflict")
        return EvidenceArtifact.model_validate(self._artifact_payload(stored))

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
        expected_request = {
            "mission_id": mission_id,
            "kind": kind,
            "title": title,
            "content": content,
            "task_id": task_id,
            "tool_invocation_id": tool_invocation_id,
            "actor": actor,
            "mime_type": mime_type,
            "source": source,
            "parent_evidence": parent_evidence or [],
            "idempotency_key": idempotency_key,
            "source_event_id": source_event_id,
            "verification_status": verification_status,
        }
        if idempotency_key:
            existing = self.store.find_record("evidence", "idempotency_key", idempotency_key)
            if existing:
                evidence_id = existing.get("evidence_id")
                if not evidence_id:
                    raise ValueError("evidence_idempotency_record_invalid")
                return self._replay_artifact(str(evidence_id), expected_request)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        artifact = EvidenceArtifact(
            evidence_id=(
                self._idempotent_evidence_id(idempotency_key)
                if idempotency_key
                else new_id("evidence")
            ),
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
        event = self.events.publish(
            "evidence.created",
            mission_id,
            "mission",
            "evidence_store",
            trace_id,
            {"evidence_id": artifact.evidence_id, "kind": kind},
            idempotency_key=idempotency_key,
        )
        artifact.source_event_id = artifact.source_event_id or event.event_id
        payload = artifact.model_dump(mode="json")
        payload["request_sha256"] = self._request_sha256(expected_request)
        payload["envelope_sha256"] = self._envelope_sha256(payload)
        if idempotency_key:
            self.store.save_record_if_absent(
                artifact.evidence_id,
                "evidence",
                payload,
                artifact.created_at,
                mission_id,
            )
            return self._replay_artifact(artifact.evidence_id, expected_request)
        self.store.save_record(
            artifact.evidence_id, "evidence", payload, artifact.created_at, mission_id
        )
        return artifact

    def verify(self, evidence_id: str) -> bool:
        envelope = self.store.get_record_envelope(evidence_id)
        if not envelope:
            raise KeyError(f"evidence_not_found:{evidence_id}")
        if envelope.get("record_type") != "evidence":
            raise ValueError("evidence_record_type_invalid")
        raw = envelope["payload"]
        if (
            raw.get("evidence_id") != evidence_id
            or raw.get("mission_id") != envelope.get("mission_id")
            or raw.get("envelope_sha256") != self._envelope_sha256(raw)
        ):
            raise ValueError("evidence_integrity_invalid")
        digest = hashlib.sha256(str(raw.get("content", "")).encode("utf-8")).hexdigest()
        verified = digest == raw.get("sha256")
        raw["verification_status"] = "verified" if verified else "corrupt"
        raw["envelope_sha256"] = self._envelope_sha256(raw)
        updated = self.store.replace_record_payload_if_integrity_matches(
            evidence_id,
            record_type="evidence",
            expected_integrity_sha256=envelope["integrity_sha256"],
            new_payload=raw,
        )
        if not updated:
            raise RuntimeError("evidence_verification_conflict")
        return verified

    def is_preverified_and_integrity_bound(self, evidence_id: str) -> bool:
        envelope = self.store.get_record_envelope(evidence_id)
        if not envelope or envelope.get("record_type") != "evidence":
            return False
        raw = envelope["payload"]
        if (
            raw.get("evidence_id") != evidence_id
            or raw.get("mission_id") != envelope.get("mission_id")
            or raw.get("verification_status") != "verified"
        ):
            return False
        content_digest = hashlib.sha256(
            str(raw.get("content", "")).encode("utf-8")
        ).hexdigest()
        if content_digest != raw.get("sha256"):
            return False
        envelope_digest = raw.get("envelope_sha256")
        return bool(envelope_digest) and envelope_digest == self._envelope_sha256(raw)

    def verify_all(self, mission_id: str | None = None) -> dict[str, Any]:
        envelopes, corrupt_ids = self.store.audit_record_envelopes(
            "evidence", mission_id
        )
        valid = 0
        for envelope in envelopes:
            evidence_id = envelope.get("record_id")
            if evidence_id and self.is_preverified_and_integrity_bound(evidence_id):
                valid += 1
        total = len(envelopes) + len(corrupt_ids)
        return {
            "total": total,
            "valid": valid,
            "invalid": total - valid,
            "coverage": (valid / total) if total else 0.0,
        }

    def state_change(
        self,
        mission_id: str,
        from_state: str,
        to_state: str,
        trace_id: str,
        event_id: str | None = None,
    ) -> EvidenceArtifact:
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
