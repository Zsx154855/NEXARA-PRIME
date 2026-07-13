from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .models import Event, EvidenceArtifact, new_id


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
    def _idempotent_event_id(idempotency_key: str) -> str:
        digest = hashlib.sha256(
            f"evidence-event:{idempotency_key}".encode("utf-8")
        ).hexdigest()
        return f"evt_{digest[:12]}"

    @staticmethod
    def _artifact_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if key in EvidenceArtifact.model_fields
        }

    @staticmethod
    def _request_from_payload(
        payload: dict[str, Any],
        *,
        verification_status: str,
        source_event_id: str | None,
    ) -> dict[str, Any]:
        return {
            "mission_id": payload.get("mission_id"),
            "kind": payload.get("kind"),
            "title": payload.get("title"),
            "content": payload.get("content"),
            "task_id": payload.get("task_id"),
            "tool_invocation_id": payload.get("tool_invocation_id"),
            "actor": payload.get("actor"),
            "mime_type": payload.get("mime_type"),
            "source": payload.get("source"),
            "parent_evidence": payload.get("parent_evidence", []),
            "idempotency_key": payload.get("idempotency_key"),
            "source_event_id": source_event_id,
            "verification_status": verification_status,
        }

    def _origin_projection(
        self,
        envelope: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[str, str | None] | None:
        statuses = {
            str(payload.get("verification_status", "unverified")),
            "unverified",
            "verified",
        }
        sources: set[str | None] = {payload.get("source_event_id")}
        if not payload.get("request_sha256"):
            sources.add(None)
        for status in statuses:
            for source_event_id in sources:
                candidate = dict(payload)
                candidate["verification_status"] = status
                candidate["source_event_id"] = source_event_id
                candidate["envelope_sha256"] = self._envelope_sha256(candidate)
                request_sha256 = candidate.get("request_sha256")
                if request_sha256:
                    request = self._request_from_payload(
                        candidate,
                        verification_status=status,
                        source_event_id=source_event_id,
                    )
                    request_matches = hmac.compare_digest(
                        str(request_sha256), self._request_sha256(request)
                    )
                    if not request_matches and source_event_id is not None:
                        legacy_request = dict(request)
                        legacy_request["source_event_id"] = None
                        request_matches = hmac.compare_digest(
                            str(request_sha256),
                            self._request_sha256(legacy_request),
                        )
                    if not request_matches:
                        continue
                if self.store.record_origin_matches(envelope, candidate):
                    return status, source_event_id
        return None

    def _origin_is_valid(
        self,
        envelope: dict[str, Any],
        payload: dict[str, Any],
    ) -> bool:
        return self._origin_projection(envelope, payload) is not None

    def _origin_record(
        self,
        envelope: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        projection = self._origin_projection(envelope, payload)
        if projection is None:
            return None
        status, source_event_id = projection
        origin = dict(payload)
        origin["verification_status"] = status
        origin["source_event_id"] = source_event_id
        origin["envelope_sha256"] = self._envelope_sha256(origin)
        return origin

    def _verification_transition_is_valid(
        self,
        evidence_id: str,
        payload: dict[str, Any],
        origin_status: str,
    ) -> bool:
        if origin_status == "verified":
            return True
        digest = str(payload.get("sha256"))
        idempotency_key = f"evidence.verify:{evidence_id}:{digest}"
        expected_event_id = self._idempotent_event_id(idempotency_key)
        for event in self.store.list_events(evidence_id):
            event_payload = event.get("payload", {})
            if (
                event.get("event_id") == expected_event_id
                and event.get("event_type") == "evidence.verified"
                and event.get("aggregate_id") == evidence_id
                and event.get("aggregate_type") == "evidence"
                and event.get("actor") == "evidence_store"
                and event.get("idempotency_key") == idempotency_key
                and event_payload.get("evidence_id") == evidence_id
                and event_payload.get("sha256") == digest
                and event_payload.get("verification_status") == "verified"
                and set(event_payload) == {
                    "evidence_id",
                    "sha256",
                    "verification_status",
                }
            ):
                return True
        return False

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
            or envelope.get("mission_id") != expected_request.get("mission_id")
        ):
            raise ValueError("evidence_idempotency_record_invalid")
        stored = envelope["payload"]
        if (
            stored.get("evidence_id") != evidence_id
            or stored.get("mission_id") != envelope.get("mission_id")
            or stored.get("sha256")
            != hashlib.sha256(
                str(stored.get("content", "")).encode("utf-8")
            ).hexdigest()
            or stored.get("envelope_sha256") != self._envelope_sha256(stored)
        ):
            raise ValueError("evidence_idempotency_record_invalid")
        if not self._origin_is_valid(envelope, stored):
            raise ValueError("evidence_idempotency_conflict")
        immutable_request_matches = all(
            stored.get(key) == expected_request.get(key)
            for key in {
                "mission_id",
                "kind",
                "title",
                "content",
                "task_id",
                "tool_invocation_id",
                "actor",
                "mime_type",
                "source",
                "parent_evidence",
                "idempotency_key",
            }
        ) and (
            expected_request.get("source_event_id") is None
            or stored.get("source_event_id")
            == expected_request.get("source_event_id")
        )
        request_sha256 = stored.get("request_sha256")
        if request_sha256:
            request_candidates = [expected_request]
            generated_source_event = self._idempotent_event_id(
                str(stored.get("idempotency_key"))
            )
            if (
                expected_request.get("source_event_id") is None
                and stored.get("source_event_id") == generated_source_event
            ):
                bound_request = dict(expected_request)
                bound_request["source_event_id"] = stored.get("source_event_id")
                request_candidates.append(bound_request)
            request_matches = any(
                hmac.compare_digest(
                    str(request_sha256), self._request_sha256(candidate)
                )
                for candidate in request_candidates
            ) and immutable_request_matches
        else:
            request_matches = immutable_request_matches
        if not request_matches:
            raise ValueError("evidence_idempotency_conflict")
        return EvidenceArtifact.model_validate(self._artifact_payload(stored))

    def _replay_and_repair_event(
        self,
        evidence_id: str,
        expected_request: dict[str, Any],
        trace_id: str,
    ) -> EvidenceArtifact:
        """Replay an artifact and repair a missing legacy creation event."""
        for _ in range(2):
            artifact = self._replay_artifact(evidence_id, expected_request)
            if not artifact.idempotency_key:
                return artifact
            envelope = self.store.get_record_envelope(evidence_id)
            if not envelope:
                raise ValueError("evidence_idempotency_record_invalid")
            origin_record = self._origin_record(envelope, envelope["payload"])
            if origin_record is None:
                raise ValueError("evidence_idempotency_record_invalid")
            existing_event = self.store.get_event_by_idempotency(
                artifact.idempotency_key
            )
            if existing_event is None:
                expected_payload = {
                    "evidence_id": artifact.evidence_id,
                    "kind": artifact.kind,
                }
                candidates: list[dict[str, Any]] = []
                if artifact.source_event_id:
                    source_event = self.store.get_event(artifact.source_event_id)
                    if source_event is not None:
                        candidates.append(source_event)
                candidates.extend(self.store.list_events(artifact.mission_id))
                matching_events = {
                    str(candidate["event_id"]): candidate
                    for candidate in candidates
                    if candidate.get("event_type") == "evidence.created"
                    and candidate.get("aggregate_id") == artifact.mission_id
                    and candidate.get("aggregate_type") == "mission"
                    and candidate.get("actor") == "evidence_store"
                    and (
                        candidate.get("payload") == expected_payload
                        or candidate.get("payload")
                        == {**expected_payload, "record": origin_record}
                    )
                    and candidate.get("idempotency_key") in {
                        None,
                        artifact.idempotency_key,
                    }
                }
                if len(matching_events) > 1:
                    raise ValueError("evidence_creation_event_ambiguous")
                if matching_events:
                    existing_event = next(iter(matching_events.values()))
            event_id = (
                str(existing_event["event_id"])
                if existing_event is not None
                else self._idempotent_event_id(artifact.idempotency_key)
            )
            event = Event(
                event_id=event_id,
                event_type="evidence.created",
                aggregate_id=artifact.mission_id,
                aggregate_type="mission",
                actor="evidence_store",
                trace_id=trace_id,
                timestamp=artifact.created_at,
                payload=(
                    dict(existing_event["payload"])
                    if existing_event is not None
                    else {**expected_payload, "record": origin_record}
                ),
                idempotency_key=artifact.idempotency_key,
            )
            repaired_payload = dict(envelope["payload"])
            # source_event_id may intentionally identify an upstream event
            # supplied by the caller. Only fill it from the creation event
            # when the legacy record never received a source binding.
            repaired_payload["source_event_id"] = (
                artifact.source_event_id or event_id
            )
            repaired_payload["envelope_sha256"] = self._envelope_sha256(
                repaired_payload
            )
            repaired = self.store.repair_record_event(
                evidence_id,
                record_type="evidence",
                expected_integrity_sha256=envelope["integrity_sha256"],
                new_payload=repaired_payload,
                event=event.model_dump(mode="json"),
            )
            if repaired is None:
                continue
            event_inserted, persisted_event = repaired
            if event_inserted:
                self.events.notify_persisted(
                    Event.model_validate(persisted_event)
                )
            return self._replay_artifact(evidence_id, expected_request)
        raise RuntimeError("evidence_idempotency_repair_conflict")

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
            existing = self.store.find_record_envelope(
                "evidence", "idempotency_key", idempotency_key
            )
            if existing is not None:
                return self._replay_and_repair_event(
                    str(existing["record_id"]), expected_request, trace_id
                )
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
        event_key = idempotency_key or f"evidence.create:{artifact.evidence_id}"
        event = Event(
            event_id=self._idempotent_event_id(event_key),
            event_type="evidence.created",
            aggregate_id=mission_id,
            aggregate_type="mission",
            actor="evidence_store",
            trace_id=trace_id,
            payload={"evidence_id": artifact.evidence_id, "kind": kind},
            idempotency_key=event_key,
        )
        artifact.source_event_id = artifact.source_event_id or event.event_id
        payload = artifact.model_dump(mode="json")
        fingerprint_request = dict(expected_request)
        fingerprint_request["source_event_id"] = artifact.source_event_id
        payload["request_sha256"] = self._request_sha256(fingerprint_request)
        payload["envelope_sha256"] = self._envelope_sha256(payload)
        event.payload["record"] = dict(payload)
        record_inserted, event_inserted, persisted_event = (
            self.store.save_record_and_event_if_absent(
                artifact.evidence_id,
                "evidence",
                payload,
                artifact.created_at,
                event.model_dump(mode="json"),
                mission_id,
            )
        )
        if event_inserted and persisted_event is not None:
            self.events.notify_persisted(Event.model_validate(persisted_event))
        if idempotency_key:
            return self._replay_artifact(artifact.evidence_id, expected_request)
        if not record_inserted:
            raise RuntimeError("evidence_record_conflict")
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
        event_type = "evidence.verified" if verified else "evidence.verification_failed"
        idempotency_key = (
            f"evidence.verify:{evidence_id}:{digest}"
            if verified
            else f"evidence.verify:{evidence_id}:{digest}:corrupt"
        )
        event = Event(
            event_id=self._idempotent_event_id(idempotency_key),
            event_type=event_type,
            aggregate_id=evidence_id,
            aggregate_type="evidence",
            actor="evidence_store",
            trace_id=f"verify:{evidence_id}",
            idempotency_key=idempotency_key,
            payload={
                "evidence_id": evidence_id,
                "sha256": digest,
                "verification_status": raw["verification_status"],
            },
        )
        result = self.store.repair_record_event(
            evidence_id,
            record_type="evidence",
            expected_integrity_sha256=envelope["integrity_sha256"],
            new_payload=raw,
            event=event.model_dump(mode="json"),
        )
        if result is None:
            raise RuntimeError("evidence_verification_conflict")
        event_inserted, persisted = result
        if event_inserted:
            self.events.notify_persisted(Event.model_validate(persisted))
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
        origin = self._origin_projection(envelope, raw)
        if origin is None:
            return False
        origin_status, _ = origin
        if not self._verification_transition_is_valid(
            evidence_id, raw, origin_status
        ):
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
