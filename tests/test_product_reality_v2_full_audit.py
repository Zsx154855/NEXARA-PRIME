from __future__ import annotations

import json
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from nexara_prime.db import SQLiteStore
from nexara_prime.evidence import EvidenceStore
from nexara_prime.events import EventBus
from nexara_prime.governance import ApprovalEngine
from nexara_prime.models import (
    ApprovalRequest,
    ApprovalStatus,
    EvidenceArtifact,
    RiskLevel,
)
from nexara_prime.product_reality import (
    EvolutionPromotionGate,
    EvolutionProposal,
    EvolutionValidation,
    ProductTwinEngine,
)


def evidence_runtime(path: Path):
    store = SQLiteStore(path)
    events = EventBus(store)
    return store, events, EvidenceStore(store, events)


def test_legacy_records_receive_integrity_during_schema_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE records(record_id TEXT PRIMARY KEY, record_type TEXT NOT NULL, "
        "mission_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    payload = {"value": 1}
    connection.execute(
        "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
        ("legacy-1", "legacy", "mission-1", json.dumps(payload), "2026-01-01T00:00:00+00:00"),
    )
    connection.commit()
    connection.close()

    store = SQLiteStore(path)

    envelope = store.get_record_envelope("legacy-1")
    assert envelope is not None
    assert envelope["payload"] == payload


def test_legacy_evidence_without_creation_snapshot_is_quarantined(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy-evidence.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE records(record_id TEXT PRIMARY KEY, record_type TEXT NOT NULL, "
        "mission_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL, "
        "integrity_sha256 TEXT)"
    )
    content = "legacy proof"
    payload = {
        "evidence_id": "evidence-legacy",
        "mission_id": "mission-1",
        "kind": "verification",
        "title": "legacy",
        "content": content,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "task_id": None,
        "tool_invocation_id": None,
        "actor": "system",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "mime_type": "text/plain",
        "source": "runtime",
        "verification_status": "verified",
        "parent_evidence": [],
        "idempotency_key": None,
        "source_event_id": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    legacy_integrity = SQLiteStore._record_integrity(
        "evidence-legacy",
        "evidence",
        "mission-1",
        payload["created_at"],
        payload,
    )
    connection.execute(
        "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?)",
        (
            "evidence-legacy",
            "evidence",
            "mission-1",
            json.dumps(payload),
            payload["created_at"],
            legacy_integrity,
        ),
    )
    connection.commit()
    connection.close()

    store, _, evidence = evidence_runtime(path)

    envelope = store.get_record_envelope("evidence-legacy")
    assert envelope is None
    assert not evidence.is_preverified_and_integrity_bound("evidence-legacy")
    assert evidence.verify_all("mission-1") == {
        "total": 1,
        "valid": 0,
        "invalid": 1,
        "coverage": 0.0,
    }


def test_schema_upgrade_does_not_reseal_corrupt_legacy_evidence(tmp_path: Path) -> None:
    path = tmp_path / "corrupt-legacy-evidence.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE records(record_id TEXT PRIMARY KEY, record_type TEXT NOT NULL, "
        "mission_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL, "
        "integrity_sha256 TEXT)"
    )
    payload = {
        "evidence_id": "evidence-corrupt",
        "mission_id": "mission-1",
        "kind": "verification",
        "content": "tampered",
        "sha256": hashlib.sha256(b"original").hexdigest(),
        "verification_status": "verified",
    }
    connection.execute(
        "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?)",
        (
            "evidence-corrupt",
            "evidence",
            "mission-1",
            json.dumps(payload),
            "2026-01-01T00:00:00+00:00",
            "invalid-existing-integrity",
        ),
    )
    connection.commit()
    connection.close()

    store = SQLiteStore(path)

    assert store.get_record_envelope("evidence-corrupt") is None
    assert "envelope_sha256" not in store.get_record("evidence-corrupt")


@pytest.mark.parametrize("integrity", [None, ""])
def test_schema_upgrade_treats_present_null_hash_as_corrupt(
    tmp_path: Path, integrity: str | None
) -> None:
    path = tmp_path / "null-hash.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE records(record_id TEXT PRIMARY KEY, record_type TEXT NOT NULL, "
        "mission_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL, "
        "integrity_sha256 TEXT)"
    )
    payload = {
        "evidence_id": "evidence-null-hash",
        "mission_id": "mission-1",
        "kind": "verification",
        "content": "content",
        "sha256": hashlib.sha256(b"content").hexdigest(),
        "verification_status": "verified",
    }
    connection.execute(
        "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?)",
        (
            "evidence-null-hash",
            "evidence",
            "mission-1",
            json.dumps(payload),
            "2026-01-01T00:00:00+00:00",
            integrity,
        ),
    )
    connection.commit()
    connection.close()

    store = SQLiteStore(path)

    assert store.get_record_envelope("evidence-null-hash") is None
    assert "envelope_sha256" not in store.get_record("evidence-null-hash")


def test_schema_upgrade_preserves_malformed_row_and_audit_counts_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "malformed-legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE records(record_id TEXT PRIMARY KEY, record_type TEXT NOT NULL, "
        "mission_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    malformed = '{"mission_id":"mission-1",'
    connection.execute(
        "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
        (
            "evidence-malformed",
            "evidence",
            "mission-1",
            malformed,
            "2026-01-01T00:00:00+00:00",
        ),
    )
    connection.commit()
    connection.close()

    store, _, evidence = evidence_runtime(path)

    with store._lock:
        row = store._conn.execute(
            "SELECT payload, integrity_sha256 FROM records WHERE record_id=?",
            ("evidence-malformed",),
        ).fetchone()
    assert row["payload"] == malformed
    assert row["integrity_sha256"] is None
    assert store.get_record_envelope("evidence-malformed") is None
    valid, invalid = store.audit_record_envelopes("evidence", "mission-1")
    assert valid == []
    assert invalid == ["evidence-malformed"]
    assert evidence.verify_all("mission-1") == {
        "total": 1,
        "valid": 0,
        "invalid": 1,
        "coverage": 0.0,
    }


@pytest.mark.parametrize("non_object", ["null", "[]", '"text"', "1", "true"])
def test_schema_upgrade_preserves_non_object_json_as_corrupt(
    tmp_path: Path, non_object: str
) -> None:
    path = tmp_path / "non-object-legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE records(record_id TEXT PRIMARY KEY, record_type TEXT NOT NULL, "
        "mission_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
        (
            "evidence-non-object",
            "evidence",
            "mission-1",
            non_object,
            "2026-01-01T00:00:00+00:00",
        ),
    )
    connection.commit()
    connection.close()

    store, _, evidence = evidence_runtime(path)

    assert store.get_record_envelope("evidence-non-object") is None
    assert evidence.verify_all("mission-1") == {
        "total": 1,
        "valid": 0,
        "invalid": 1,
        "coverage": 0.0,
    }


def test_verify_refuses_to_reseal_out_of_band_evidence_tampering(tmp_path: Path) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "evidence.sqlite3")
    artifact = evidence.add(
        "mission-1", "verification", "proof", "content", "trace-1"
    )
    with store._lock, store._conn:
        raw = store.get_record(artifact.evidence_id)
        raw["mission_id"] = "mission-2"
        store._conn.execute(
            "UPDATE records SET mission_id=?, payload=? WHERE record_id=?",
            ("mission-2", json.dumps(raw), artifact.evidence_id),
        )

    with pytest.raises(KeyError):
        evidence.verify(artifact.evidence_id)
    assert store.get_record_envelope(artifact.evidence_id) is None


def test_preverified_check_requires_outer_and_inner_envelopes(tmp_path: Path) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "evidence.sqlite3")
    artifact = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace-1",
        verification_status="verified",
    )
    assert evidence.is_preverified_and_integrity_bound(artifact.evidence_id)
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE records SET mission_id=? WHERE record_id=?",
            ("mission-2", artifact.evidence_id),
        )
    assert not evidence.is_preverified_and_integrity_bound(artifact.evidence_id)


def test_concurrent_idempotent_evidence_creates_one_record_and_event(tmp_path: Path) -> None:
    path = tmp_path / "evidence.sqlite3"
    runtimes = [evidence_runtime(path), evidence_runtime(path)]
    barrier = threading.Barrier(2)
    results = []

    def add(index: int) -> None:
        barrier.wait()
        results.append(
            runtimes[index][2].add(
                "mission-1",
                "verification",
                "proof",
                "content",
                "trace-1",
                idempotency_key="same-request",
            )
        )

    threads = [threading.Thread(target=add, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 2
    assert results[0] == results[1]
    assert runtimes[0][0].count("records") == 1
    assert runtimes[0][0].count("events") == 1


def test_non_idempotent_evidence_notifies_only_after_atomic_commit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "atomic-evidence.sqlite3"
    store, events, evidence = evidence_runtime(path)
    durable_reader = SQLiteStore(path)
    observed: list[bool] = []

    def subscriber(event) -> None:
        observed.append(
            durable_reader.get_record_envelope(
                str(event.payload["evidence_id"])
            ) is not None
        )

    events.subscribe(subscriber)
    artifact = evidence.add(
        "mission-1", "verification", "proof", "content", "trace-1"
    )

    assert observed == [True]
    assert store.get_record_envelope(artifact.evidence_id) is not None
    assert store.count("records") == 1
    assert store.count("events") == 1


def test_legacy_random_idempotent_evidence_replays_without_duplication(
    tmp_path: Path,
) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "legacy-replay.sqlite3")
    content = "legacy content"
    legacy = EvidenceArtifact(
        evidence_id="evidence_legacy_random",
        mission_id="mission-1",
        kind="verification",
        title="proof",
        content=content,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        idempotency_key="legacy-request",
        source_event_id="evt_legacy_random",
    )
    payload = legacy.model_dump(mode="json")
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    store.save_record(
        legacy.evidence_id,
        "evidence",
        payload,
        legacy.created_at,
        legacy.mission_id,
    )
    store.save_event(
        {
            "event_id": "evt_legacy_random",
            "event_type": "evidence.created",
            "aggregate_id": "mission-1",
            "aggregate_type": "mission",
            "actor": "evidence_store",
            "trace_id": "legacy-trace",
            "timestamp": legacy.created_at,
            "idempotency_key": "legacy-request",
            "payload": {
                "evidence_id": legacy.evidence_id,
                "kind": legacy.kind,
            },
        }
    )

    replay = evidence.add(
        "mission-1",
        "verification",
        "proof",
        content,
        "retry-trace",
        idempotency_key="legacy-request",
    )

    assert replay.evidence_id == legacy.evidence_id
    assert replay.source_event_id == legacy.source_event_id
    assert store.count("records") == 1
    assert store.count("events") == 1


def test_verified_legacy_evidence_replay_repairs_missing_creation_event(
    tmp_path: Path,
) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "legacy-repair.sqlite3")
    notified: list[str] = []
    events.subscribe(lambda event: notified.append(event.event_id))
    content = "legacy content"
    legacy = EvidenceArtifact(
        evidence_id="evidence_legacy_missing_event",
        mission_id="mission-1",
        kind="verification",
        title="proof",
        content=content,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        idempotency_key="legacy-missing-event",
        source_event_id=None,
    )
    payload = legacy.model_dump(mode="json")
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    store.save_record(
        legacy.evidence_id,
        "evidence",
        payload,
        legacy.created_at,
        legacy.mission_id,
    )
    assert evidence.verify(legacy.evidence_id)

    replay = evidence.add(
        "mission-1",
        "verification",
        "proof",
        content,
        "retry-trace",
        idempotency_key="legacy-missing-event",
    )

    assert replay.evidence_id == legacy.evidence_id
    assert replay.verification_status == "verified"
    assert replay.source_event_id is not None
    event = store.get_event_by_idempotency("legacy-missing-event")
    assert event is not None
    assert event["event_id"] == replay.source_event_id
    assert event["payload"]["evidence_id"] == legacy.evidence_id
    assert event["payload"]["kind"] == legacy.kind
    assert event["payload"]["record"]["evidence_id"] == legacy.evidence_id
    assert event["payload"]["record"]["verification_status"] == "unverified"
    assert notified[-1] == event["event_id"]
    assert len(notified) == 2
    assert store.get_event(notified[0])["event_type"] == "evidence.verified"
    assert store.count("records") == 1
    assert store.count("events") == 2


def test_evidence_replay_rejects_integrity_valid_row_mission_alias(
    tmp_path: Path,
) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "mission-alias.sqlite3")
    artifact = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace-1",
        idempotency_key="mission-bound-request",
    )
    envelope = store.get_record_envelope(artifact.evidence_id)
    assert envelope is not None
    aliased_integrity = SQLiteStore._record_integrity(
        artifact.evidence_id,
        "evidence",
        "mission-2",
        envelope["created_at"],
        envelope["payload"],
    )
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE records SET mission_id=?, integrity_sha256=? WHERE record_id=?",
            ("mission-2", aliased_integrity, artifact.evidence_id),
        )

    with pytest.raises(
        ValueError, match="evidence_idempotency_record_invalid"
    ):
        evidence.add(
            "mission-1",
            "verification",
            "proof",
            "content",
            "trace-2",
            idempotency_key="mission-bound-request",
        )

    assert store.count("records") == 1
    assert store.count("events") == 1


def test_evidence_replay_rejects_resealed_immutable_payload_changes(
    tmp_path: Path,
) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "payload-reseal.sqlite3")
    artifact = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "original content",
        "trace-1",
        idempotency_key="immutable-request",
    )
    payload = store.get_record(artifact.evidence_id)
    assert payload is not None
    payload["title"] = "altered proof"
    payload["content"] = "altered content"
    payload["sha256"] = hashlib.sha256(
        payload["content"].encode("utf-8")
    ).hexdigest()
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    store.save_record(
        artifact.evidence_id,
        "evidence",
        payload,
        payload["created_at"],
        artifact.mission_id,
    )

    with pytest.raises(ValueError, match="evidence_idempotency_conflict"):
        evidence.add(
            "mission-1",
            "verification",
            "proof",
            "original content",
            "trace-2",
            idempotency_key="immutable-request",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_event_id", "evt_rebound_provenance"),
        ("timestamp", "2030-01-01T00:00:00+00:00"),
        ("created_at", "2030-01-01T00:00:00+00:00"),
    ],
)
def test_evidence_replay_rejects_resealed_provenance_and_chronology(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    store, _, evidence = evidence_runtime(tmp_path / f"rebound-{field}.sqlite3")
    artifact = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace-1",
        idempotency_key=f"bound-{field}",
    )
    payload = store.get_record(artifact.evidence_id)
    assert payload is not None
    payload[field] = value
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    store.save_record(
        artifact.evidence_id,
        "evidence",
        payload,
        payload["created_at"],
        artifact.mission_id,
    )

    with pytest.raises(ValueError, match="evidence_idempotency_conflict"):
        evidence.add(
            "mission-1",
            "verification",
            "proof",
            "content",
            "trace-2",
            idempotency_key=f"bound-{field}",
        )


def test_evidence_replay_rejects_omitted_explicit_source_event(
    tmp_path: Path,
) -> None:
    _, _, evidence = evidence_runtime(tmp_path / "explicit-source.sqlite3")
    evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace-1",
        source_event_id="upstream-explicit-event",
        idempotency_key="explicit-source-request",
    )

    with pytest.raises(ValueError, match="evidence_idempotency_conflict"):
        evidence.add(
            "mission-1",
            "verification",
            "proof",
            "content",
            "trace-2",
            idempotency_key="explicit-source-request",
        )


def test_direct_verified_reseal_requires_verification_transition(
    tmp_path: Path,
) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "verification-transition.sqlite3")
    artifact = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace",
    )
    payload = store.get_record(artifact.evidence_id)
    assert payload is not None
    payload["verification_status"] = "verified"
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    store.save_record(
        artifact.evidence_id,
        "evidence",
        payload,
        payload["created_at"],
        artifact.mission_id,
    )
    fake_key = f"evidence.verify:{artifact.evidence_id}:{artifact.sha256}"
    EventBus(store).publish(
        "evidence.verified",
        artifact.evidence_id,
        "evidence",
        "evidence_store",
        "forged-verification",
        {
            "evidence_id": artifact.evidence_id,
            "sha256": artifact.sha256,
            "verification_status": "verified",
        },
        idempotency_key=fake_key,
    )

    assert not evidence.is_preverified_and_integrity_bound(artifact.evidence_id)


def test_missing_origin_does_not_bless_current_verified_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing-evidence-origin.sqlite3"
    store, _, evidence = evidence_runtime(path)
    artifact = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace",
        idempotency_key="legacy-summary-event",
    )
    envelope = store.get_record_envelope(artifact.evidence_id)
    assert envelope is not None
    payload = dict(envelope["payload"])
    payload["verification_status"] = "verified"
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    resealed_integrity = SQLiteStore._record_integrity(
        artifact.evidence_id,
        "evidence",
        artifact.mission_id,
        envelope["created_at"],
        payload,
    )
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE records SET payload=?, integrity_sha256=?, origin_sha256=NULL "
            "WHERE record_id=?",
            (
                SQLiteStore._canonical_payload(payload),
                resealed_integrity,
                artifact.evidence_id,
            ),
        )
        store._conn.execute(
            "UPDATE events SET payload=? WHERE idempotency_key=?",
            (
                json.dumps(
                    {"evidence_id": artifact.evidence_id, "kind": artifact.kind}
                ),
                artifact.idempotency_key,
            ),
        )
    store.close()

    migrated = SQLiteStore(path)
    assert migrated.get_record_envelope(artifact.evidence_id) is None
    assert not EvidenceStore(
        migrated, EventBus(migrated)
    ).is_preverified_and_integrity_bound(artifact.evidence_id)


def test_preverified_evidence_rejects_resealed_provenance(tmp_path: Path) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "provenance.sqlite3")
    artifact = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace",
        actor="reviewer",
        source="test",
        verification_status="verified",
        idempotency_key="provenance-bound",
    )
    payload = store.get_record(artifact.evidence_id)
    assert payload is not None
    payload["actor"] = "attacker"
    payload["source"] = "rebound"
    payload["title"] = "rewritten proof"
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    store.save_record(
        artifact.evidence_id,
        "evidence",
        payload,
        payload["created_at"],
        artifact.mission_id,
    )

    assert not evidence.is_preverified_and_integrity_bound(artifact.evidence_id)


def test_legacy_creation_event_without_idempotency_is_claimed_not_duplicated(
    tmp_path: Path,
) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "legacy-event.sqlite3")
    notified: list[str] = []
    events.subscribe(lambda event: notified.append(event.event_id))
    content = "legacy content"
    legacy = EvidenceArtifact(
        evidence_id="evidence_legacy_pre_idempotency_event",
        mission_id="mission-1",
        kind="verification",
        title="proof",
        content=content,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        idempotency_key="legacy-pre-idempotency-event",
        source_event_id=None,
    )
    payload = legacy.model_dump(mode="json")
    payload["envelope_sha256"] = EvidenceStore._envelope_sha256(payload)
    store.save_record(
        legacy.evidence_id,
        "evidence",
        payload,
        legacy.created_at,
        legacy.mission_id,
    )
    store.save_event(
        {
            "event_id": "evt_legacy_pre_idempotency",
            "event_type": "evidence.created",
            "aggregate_id": legacy.mission_id,
            "aggregate_type": "mission",
            "actor": "evidence_store",
            "trace_id": "legacy-trace",
            "timestamp": legacy.created_at,
            "idempotency_key": None,
            "payload": {
                "evidence_id": legacy.evidence_id,
                "kind": legacy.kind,
            },
        }
    )

    replay = evidence.add(
        "mission-1",
        "verification",
        "proof",
        content,
        "retry-trace",
        idempotency_key="legacy-pre-idempotency-event",
    )

    assert replay.evidence_id == legacy.evidence_id
    assert replay.source_event_id == "evt_legacy_pre_idempotency"
    assert store.get_event_by_idempotency(
        "legacy-pre-idempotency-event"
    )["event_id"] == "evt_legacy_pre_idempotency"
    assert notified == []
    assert store.count("records") == 1
    assert store.count("events") == 1


def test_concurrent_conflicting_evidence_atomically_binds_winning_event(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence-conflict.sqlite3"
    runtimes = [evidence_runtime(path), evidence_runtime(path)]
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def add(index: int) -> None:
        barrier.wait()
        try:
            runtimes[index][2].add(
                "mission-1",
                f"kind-{index}",
                "proof",
                f"content-{index}",
                f"trace-{index}",
                idempotency_key="conflicting-request",
            )
            outcomes.append("success")
        except ValueError as error:
            assert str(error) == "evidence_idempotency_conflict"
            outcomes.append("conflict")

    threads = [threading.Thread(target=add, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["conflict", "success"]
    records = runtimes[0][0].list_record_envelopes("evidence")
    events = runtimes[0][0].list_events()
    assert len(records) == 1
    assert len(events) == 1
    assert events[0]["event_id"] == records[0]["payload"]["source_event_id"]
    assert events[0]["payload"]["evidence_id"] == records[0]["record_id"]
    assert events[0]["payload"]["kind"] == records[0]["payload"]["kind"]
    assert events[0]["payload"]["record"] == records[0]["payload"]


def test_event_collision_cannot_leave_an_unpaired_evidence_record(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "event-collision.sqlite3")
    events.publish(
        "approval.requested",
        "mission-1",
        "mission",
        "governance",
        "trace-1",
        {},
        idempotency_key="shared-key",
    )

    with pytest.raises(ValueError, match="event_idempotency_identity_conflict"):
        evidence.add(
            "mission-1",
            "verification",
            "proof",
            "content",
            "trace-2",
            idempotency_key="shared-key",
        )

    assert store.count("records") == 0
    assert store.count("events") == 1


@pytest.mark.parametrize(
    "override",
    [
        {"source_event_id": "different-source"},
        {"verification_status": "verified"},
    ],
)
def test_evidence_replay_binds_source_event_and_status(
    tmp_path: Path, override: dict[str, str]
) -> None:
    _, _, evidence = evidence_runtime(tmp_path / "replay.sqlite3")
    evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace",
        idempotency_key="request-1",
    )
    with pytest.raises(ValueError, match="evidence_idempotency_conflict"):
        evidence.add(
            "mission-1",
            "verification",
            "proof",
            "content",
            "trace",
            idempotency_key="request-1",
            **override,
        )


def test_idempotent_replay_preserves_explicit_upstream_source_event(
    tmp_path: Path,
) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "source-replay.sqlite3")
    original = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace-1",
        source_event_id="upstream-event",
        idempotency_key="request-with-upstream",
    )

    replay = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "content",
        "trace-2",
        source_event_id="upstream-event",
        idempotency_key="request-with-upstream",
    )

    assert replay == original
    assert replay.source_event_id == "upstream-event"
    assert store.count("records") == 1
    assert store.count("events") == 1


def test_event_idempotency_keeps_first_persisted_event(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "events.sqlite3")
    events = EventBus(store)
    original = events.publish(
        "evidence.created",
        "mission-1",
        "mission",
        "evidence_store",
        "trace-1",
        {"value": 1},
        idempotency_key="event-1",
    )
    replay = events.publish(
        "evidence.created",
        "mission-1",
        "mission",
        "evidence_store",
        "trace-2",
        {"value": 2},
        idempotency_key="event-1",
    )
    assert replay.event_id == original.event_id
    assert replay.payload == original.payload
    assert store.count("events") == 1


def test_event_idempotency_rejects_cross_producer_collision(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "event-collision.sqlite3")
    events = EventBus(store)
    events.publish(
        "approval.requested",
        "mission-1",
        "mission",
        "governance",
        "trace-1",
        {},
        idempotency_key="shared-key",
    )

    with pytest.raises(ValueError, match="event_idempotency_identity_conflict"):
        events.publish(
            "evidence.created",
            "mission-1",
            "mission",
            "evidence_store",
            "trace-2",
            {},
            idempotency_key="shared-key",
        )


def test_verify_all_reports_corrupt_and_moved_evidence_rows(tmp_path: Path) -> None:
    store, _, evidence = evidence_runtime(tmp_path / "verify-all.sqlite3")
    valid = evidence.add(
        "mission-1",
        "verification",
        "valid",
        "valid",
        "trace",
        verification_status="verified",
    )
    corrupt = evidence.add(
        "mission-1",
        "verification",
        "corrupt",
        "corrupt",
        "trace",
        verification_status="verified",
    )
    with store._lock, store._conn:
        payload = store.get_record(corrupt.evidence_id)
        payload["evidence_id"] = valid.evidence_id
        store._conn.execute(
            "UPDATE records SET mission_id=?, payload=? WHERE record_id=?",
            ("mission-moved", json.dumps(payload), corrupt.evidence_id),
        )

    result = evidence.verify_all("mission-1")

    assert result == {"total": 2, "valid": 1, "invalid": 1, "coverage": 0.5}


def test_concurrent_approval_decisions_have_one_winner(tmp_path: Path) -> None:
    path = tmp_path / "approval.sqlite3"
    stores = [SQLiteStore(path), SQLiteStore(path)]
    approvals = [ApprovalEngine(store, EventBus(store)) for store in stores]
    request = approvals[0].request(
        "mission-1",
        "product_reality.promote:proposal-1",
        RiskLevel.R3,
        "test",
        ["product"],
        "trace-request",
        executor_id="executor-1",
    )
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def decide(index: int) -> None:
        barrier.wait()
        try:
            approvals[index].decide(
                request.approval_id,
                index == 0,
                f"human-{index}",
                "decision",
                f"trace-{index}",
            )
            outcomes.append("success")
        except (RuntimeError, ValueError):
            outcomes.append("conflict")

    threads = [threading.Thread(target=decide, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["conflict", "success"]
    assert approvals[0].get(request.approval_id).status in {
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
    }


def test_approval_decision_refuses_corrupt_record(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "approval.sqlite3")
    approvals = ApprovalEngine(store, EventBus(store))
    request = approvals.request(
        "mission-1", "action", RiskLevel.R3, "test", [], "trace"
    )
    with store._lock, store._conn:
        raw = store.get_record(request.approval_id)
        raw["action"] = "rebound"
        store._conn.execute(
            "UPDATE records SET payload=? WHERE record_id=?",
            (json.dumps(raw), request.approval_id),
        )
    with pytest.raises(KeyError):
        approvals.decide(
            request.approval_id, True, "human", "approve", "trace-decision"
        )


def test_approval_list_rejects_resealed_cross_mission_alias(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "approval-list.sqlite3")
    approvals = ApprovalEngine(store, EventBus(store))
    original = approvals.request(
        "mission-2", "action", RiskLevel.R2, "test", [], "trace"
    )
    payload = original.model_dump(mode="json")
    store.save_record(
        "approval-alias",
        "approval",
        payload,
        original.created_at,
        "mission-1",
    )

    with pytest.raises(ValueError, match="approval_integrity_invalid"):
        approvals.list("mission-1")


def test_product_twin_lookup_requires_integrity_envelope(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "twin.sqlite3")
    twin = ProductTwinEngine(store)
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    assert twin.get_checkpoint(checkpoint.checkpoint_id) == checkpoint
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE records SET mission_id=? WHERE record_id=?",
            ("mission-2", checkpoint.checkpoint_id),
        )
    assert twin.get_checkpoint(checkpoint.checkpoint_id) is None


def test_product_twin_lookup_rejects_resealed_stale_snapshot_hash(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "twin-stale-hash.sqlite3")
    twin = ProductTwinEngine(store)
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    payload = store.get_record(checkpoint.checkpoint_id)
    assert payload is not None
    payload["expected"]["state"] = {"version": 999}
    store.save_record(
        checkpoint.checkpoint_id,
        "product_twin_checkpoint",
        payload,
        payload["created_at"],
        checkpoint.mission_id,
    )

    with pytest.raises(
        ValueError, match="product_twin_checkpoint_integrity_invalid"
    ):
        twin.get_checkpoint(checkpoint.checkpoint_id)


def test_product_twin_lookup_rejects_resealed_drift_findings(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "twin-findings.sqlite3")
    twin = ProductTwinEngine(store)
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 2},
    )
    assert checkpoint.drift_findings
    payload = store.get_record(checkpoint.checkpoint_id)
    assert payload is not None
    payload["drift_findings"] = []
    store.save_record(
        checkpoint.checkpoint_id,
        "product_twin_checkpoint",
        payload,
        payload["created_at"],
        checkpoint.mission_id,
    )

    with pytest.raises(
        ValueError, match="product_twin_checkpoint_integrity_invalid"
    ):
        twin.get_checkpoint(checkpoint.checkpoint_id)


def test_product_twin_lookup_rejects_resealed_state_and_matching_hash(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "twin-repoint.sqlite3")
    twin = ProductTwinEngine(store)
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    payload = store.get_record(checkpoint.checkpoint_id)
    assert payload is not None
    payload["expected"]["state"] = {"version": 999}
    payload["expected"]["state_sha256"] = ProductTwinEngine._state_sha256(
        payload["expected"]["state"]
    )
    store.save_record(
        checkpoint.checkpoint_id,
        "product_twin_checkpoint",
        payload,
        payload["created_at"],
        checkpoint.mission_id,
    )

    with pytest.raises(
        ValueError, match="product_twin_checkpoint_integrity_invalid"
    ):
        twin.get_checkpoint(checkpoint.checkpoint_id)


def test_proposal_rejects_blank_duplicate_and_fake_recovery_fields() -> None:
    with pytest.raises(ValidationError):
        EvolutionProposal(
            mission_id="mission-1",
            title="change",
            observed_problem={},
            proposed_changes=["change"],
            risk_level=RiskLevel.R2,
            evidence_refs=["evidence-1", " evidence-1 "],
            rollback_plan=[" "],
            rollback_checkpoint_id=" ",
            rollback_evidence_refs=["rollback-1"],
        )


def test_gate_rejects_future_approval_decision_time(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "gate.sqlite3")
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    proof = evidence.add(
        "mission-1", "verification", "proof", "proof", "trace", verification_status="verified"
    )
    rollback = evidence.add(
        "mission-1", "verification", "rollback", "rollback", "trace", verification_status="verified"
    )
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    proposal = EvolutionProposal(
        proposal_id="proposal-1",
        mission_id="mission-1",
        title="change",
        observed_problem={},
        proposed_changes=["change"],
        risk_level=RiskLevel.R3,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=checkpoint.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    approval = approvals.request(
        proposal.mission_id,
        proposal.promotion_action,
        RiskLevel.R3,
        "approve",
        [],
        "trace",
        executor_id="executor-1",
        proposal_sha256=proposal.content_sha256,
    )
    approvals.decide(
        approval.approval_id, True, "human-1", "approve", "trace-decision"
    )
    raw = store.get_record(approval.approval_id)
    raw["decided_at"] = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).isoformat()
    store.save_record(
        approval.approval_id, "approval", raw, raw["created_at"], proposal.mission_id
    )
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )

    decision = gate.assess(
        proposal,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
            approval_id=approval.approval_id,
            actor_id="executor-1",
        ),
    )
    assert not decision.allowed
    assert "stored promotion approval has invalid decision time" in decision.required_actions


def test_gate_rejects_checkpoint_payload_copied_under_alias(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "checkpoint-alias.sqlite3")
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    proof = evidence.add(
        "mission-1", "verification", "proof", "proof", "trace", verification_status="verified"
    )
    rollback = evidence.add(
        "mission-1", "verification", "rollback", "rollback", "trace", verification_status="verified"
    )
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    alias_id = "checkpoint-alias"
    store.save_record(
        alias_id,
        "product_twin_checkpoint",
        checkpoint.model_dump(mode="json"),
        checkpoint.created_at,
        checkpoint.mission_id,
    )
    proposal = EvolutionProposal(
        mission_id="mission-1",
        title="change",
        observed_problem={},
        proposed_changes=["change"],
        risk_level=RiskLevel.R2,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=alias_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )

    decision = gate.assess(
        proposal,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
        ),
    )

    assert not decision.allowed
    assert "stored rollback checkpoint identity mismatch" in decision.required_actions


def test_gate_binds_approval_to_immutable_proposal_content(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "proposal-binding.sqlite3")
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    proof = evidence.add(
        "mission-1", "verification", "proof", "proof", "trace", verification_status="verified"
    )
    rollback = evidence.add(
        "mission-1", "verification", "rollback", "rollback", "trace", verification_status="verified"
    )
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    original = EvolutionProposal(
        proposal_id="proposal-stable-id",
        mission_id="mission-1",
        title="benign change",
        observed_problem={},
        proposed_changes=["change label"],
        risk_level=RiskLevel.R3,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=checkpoint.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    approval = approvals.request(
        original.mission_id,
        original.promotion_action,
        original.risk_level,
        "approve exact proposal",
        [],
        "trace",
        executor_id="executor-1",
        proposal_sha256=original.content_sha256,
    )
    approvals.decide(
        approval.approval_id, True, "human-1", "approve", "trace-decision"
    )
    substituted = original.model_copy(
        update={"title": "destructive replacement", "proposed_changes": ["replace system"]}
    )
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )

    decision = gate.assess(
        substituted,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
            approval_id=approval.approval_id,
            actor_id="executor-1",
        ),
    )

    assert not decision.allowed
    assert "stored promotion approval proposal content mismatch" in decision.required_actions


def test_gate_rejects_resealed_checkpoint_reversible_flag(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "reversible-origin.sqlite3")
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    proof = evidence.add(
        "mission-1", "verification", "proof", "proof", "trace",
        verification_status="verified",
    )
    rollback = evidence.add(
        "mission-1", "verification", "rollback", "rollback", "trace",
        verification_status="verified",
    )
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
        reversible=False,
    )
    payload = store.get_record(checkpoint.checkpoint_id)
    assert payload is not None
    payload["reversible"] = True
    store.save_record(
        checkpoint.checkpoint_id,
        "product_twin_checkpoint",
        payload,
        payload["created_at"],
        checkpoint.mission_id,
    )
    proposal = EvolutionProposal(
        mission_id="mission-1",
        title="change",
        observed_problem={},
        proposed_changes=["change"],
        risk_level=RiskLevel.R2,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=checkpoint.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )

    decision = gate.assess(
        proposal,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
        ),
    )

    assert not decision.allowed
    assert (
        "stored rollback checkpoint original binding mismatch"
        in decision.required_actions
    )


def test_gate_recomputes_first_write_checkpoint_drift(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "stale-first-write.sqlite3")
    approvals = ApprovalEngine(store, events)
    proof = evidence.add(
        "mission-1", "verification", "proof", "proof", "trace",
        verification_status="verified",
    )
    rollback = evidence.add(
        "mission-1", "verification", "rollback", "rollback", "trace",
        verification_status="verified",
    )
    checkpoint = ProductTwinEngine().capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 2},
    )
    assert checkpoint.drift_findings
    stale = checkpoint.model_copy(update={"drift_findings": []})
    store.save_record(
        stale.checkpoint_id,
        "product_twin_checkpoint",
        stale.model_dump(mode="json"),
        stale.created_at,
        stale.mission_id,
    )
    proposal = EvolutionProposal(
        mission_id="mission-1",
        title="change",
        observed_problem={},
        proposed_changes=["change"],
        risk_level=RiskLevel.R2,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=stale.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )

    decision = gate.assess(
        proposal,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
        ),
    )

    assert not decision.allowed
    assert (
        "stored rollback checkpoint drift findings mismatch"
        in decision.required_actions
    )


def test_gate_rejects_resealed_approval_request_repurposing(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "approval-origin.sqlite3")
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    proof = evidence.add(
        "mission-1", "verification", "proof", "proof", "trace",
        verification_status="verified",
    )
    rollback = evidence.add(
        "mission-1", "verification", "rollback", "rollback", "trace",
        verification_status="verified",
    )
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    original = EvolutionProposal(
        proposal_id="proposal-original",
        mission_id="mission-1",
        title="original",
        observed_problem={},
        proposed_changes=["original change"],
        risk_level=RiskLevel.R3,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=checkpoint.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    approval = approvals.request(
        original.mission_id,
        original.promotion_action,
        original.risk_level,
        "approve",
        [],
        "trace",
        executor_id="executor-1",
        proposal_sha256=original.content_sha256,
    )
    approvals.decide(
        approval.approval_id, True, "human-1", "approve", "decision-trace"
    )
    substituted = original.model_copy(
        update={
            "proposal_id": "proposal-substituted",
            "title": "substituted",
            "proposed_changes": ["different change"],
        }
    )
    payload = store.get_record(approval.approval_id)
    assert payload is not None
    payload["action"] = substituted.promotion_action
    payload["proposal_sha256"] = substituted.content_sha256
    store.save_record(
        approval.approval_id,
        "approval",
        payload,
        payload["created_at"],
        approval.mission_id,
    )
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )

    decision = gate.assess(
        substituted,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
            approval_id=approval.approval_id,
            actor_id="executor-1",
        ),
    )

    assert not decision.allowed
    assert (
        "stored promotion approval original request mismatch"
        in decision.required_actions
    )


def test_gate_requires_durable_approval_decision_transition(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "decision-transition.sqlite3")
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    proof = evidence.add(
        "mission-1", "verification", "proof", "proof", "trace",
        verification_status="verified",
    )
    rollback = evidence.add(
        "mission-1", "verification", "rollback", "rollback", "trace",
        verification_status="verified",
    )
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    proposal = EvolutionProposal(
        mission_id="mission-1",
        title="change",
        observed_problem={},
        proposed_changes=["change"],
        risk_level=RiskLevel.R3,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=checkpoint.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    approval = approvals.request(
        proposal.mission_id,
        proposal.promotion_action,
        proposal.risk_level,
        "approve",
        [],
        "trace",
        executor_id="executor-1",
        proposal_sha256=proposal.content_sha256,
    )
    payload = store.get_record(approval.approval_id)
    assert payload is not None
    payload.update(
        {
            "status": "approved",
            "decided_by": "human-1",
            "decision_note": "forged",
            "decision_action": "approved",
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    store.save_record(
        approval.approval_id,
        "approval",
        payload,
        payload["created_at"],
        approval.mission_id,
    )
    forged = ApprovalRequest.model_validate(payload)
    events.publish(
        "approval.decided",
        approval.mission_id,
        "mission",
        "human-1",
        "forged-decision",
        {
            "approval_id": approval.approval_id,
            "status": ApprovalStatus.APPROVED.value,
            "decision": "approved",
            "scope": approval.approval_scope,
            "action": approval.action,
            "risk_level": approval.risk_level.value,
            "executor_id": approval.executor_id,
            "proposal_sha256": approval.proposal_sha256,
            "decided_at": forged.decided_at,
        },
        idempotency_key=f"approval.decided:{approval.approval_id}",
    )
    with pytest.raises(ValueError, match="approval_integrity_invalid"):
        approvals.get(approval.approval_id)
    with pytest.raises(ValueError, match="approval_integrity_invalid"):
        approvals.list(approval.mission_id)
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )

    decision = gate.assess(
        proposal,
        EvolutionValidation(
            simulation_passed=True,
            verification_passed=True,
            accessibility_passed=True,
            governance_passed=True,
            approval_id=approval.approval_id,
            actor_id="executor-1",
        ),
    )

    assert not decision.allowed
    assert (
        "stored promotion approval has no durable decision transition"
        in decision.required_actions
    )


def test_approval_scope_remains_anchored_on_approve_once(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "approval-scope.sqlite3")
    approvals = ApprovalEngine(store, EventBus(store))
    approval = approvals.request(
        "mission-1",
        "mission-wide-action",
        RiskLevel.R2,
        "approve",
        [],
        "trace",
        approval_scope="mission",
    )

    decided = approvals.decide(
        approval.approval_id,
        True,
        "human-1",
        "approve once",
        "decision-trace",
        decision="approve_once",
    )

    assert decided.approval_scope == "mission"
    assert approvals.get(approval.approval_id).approval_scope == "mission"


def test_migration_reconstructs_decided_approval_origin(tmp_path: Path) -> None:
    path = tmp_path / "approval-migration.sqlite3"
    store = SQLiteStore(path)
    approvals = ApprovalEngine(store, EventBus(store))
    approval = approvals.request(
        "mission-1",
        "action",
        RiskLevel.R2,
        "approve",
        [],
        "trace",
        approval_scope="single_action",
    )
    approvals.decide(
        approval.approval_id,
        True,
        "human-1",
        "approved",
        "decision-trace",
    )
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("ALTER TABLE records DROP COLUMN origin_sha256")
    connection.commit()
    connection.close()

    migrated_store = SQLiteStore(path)
    migrated = ApprovalEngine(
        migrated_store, EventBus(migrated_store)
    ).get(approval.approval_id)

    assert migrated is not None
    assert migrated.status == ApprovalStatus.APPROVED
    assert migrated.approval_scope == "single_action"


def test_migration_does_not_bless_repurposed_approval_request_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / "approval-repurposed-migration.sqlite3"
    store = SQLiteStore(path)
    approvals = ApprovalEngine(store, EventBus(store))
    approval = approvals.request(
        "mission-1",
        "original-action",
        RiskLevel.R2,
        "approve",
        [],
        "trace",
        approval_scope="single_action",
    )
    approvals.decide(
        approval.approval_id,
        True,
        "human-1",
        "approved",
        "decision-trace",
    )
    envelope = store.get_record_envelope(approval.approval_id)
    assert envelope is not None
    payload = dict(envelope["payload"])
    payload.update(
        {
            "action": "repurposed-action",
            "risk_level": RiskLevel.R4.value,
            "approval_scope": "mission",
        }
    )
    repurposed_integrity = SQLiteStore._record_integrity(
        approval.approval_id,
        "approval",
        approval.mission_id,
        envelope["created_at"],
        payload,
    )
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE records SET payload=?, integrity_sha256=? WHERE record_id=?",
            (
                SQLiteStore._canonical_payload(payload),
                repurposed_integrity,
                approval.approval_id,
            ),
        )
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("ALTER TABLE records DROP COLUMN origin_sha256")
    connection.commit()
    connection.close()

    migrated_store = SQLiteStore(path)
    with pytest.raises(ValueError, match="approval_integrity_invalid"):
        ApprovalEngine(migrated_store, EventBus(migrated_store)).get(
            approval.approval_id
        )


def test_migration_quarantines_summary_only_approval_request_events(
    tmp_path: Path,
) -> None:
    path = tmp_path / "approval-summary-migration.sqlite3"
    store = SQLiteStore(path)
    approvals = ApprovalEngine(store, EventBus(store))
    approval = approvals.request(
        "mission-1",
        "action",
        RiskLevel.R3,
        "approve",
        [],
        "trace",
        executor_id="executor-1",
        proposal_sha256="proposal-digest",
    )
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE events SET payload=? WHERE event_type='approval.requested' "
            "AND aggregate_id=?",
            (
                json.dumps(
                    {
                        "approval_id": approval.approval_id,
                        "risk_level": approval.risk_level.value,
                        "action": approval.action,
                        "scope": approval.approval_scope,
                    }
                ),
                approval.mission_id,
            ),
        )
        store._conn.execute(
            "UPDATE records SET origin_sha256=NULL WHERE record_id=?",
            (approval.approval_id,),
        )
    store.close()

    migrated = SQLiteStore(path)
    assert migrated.get_record_envelope(approval.approval_id) is None
    assert ApprovalEngine(migrated, EventBus(migrated)).get(
        approval.approval_id
    ) is None


def test_partial_upgrade_backfills_every_missing_origin_idempotently(
    tmp_path: Path,
) -> None:
    path = tmp_path / "partial-origin-upgrade.sqlite3"
    store, events, evidence = evidence_runtime(path)
    approvals = ApprovalEngine(store, events)
    approval = approvals.request(
        "mission-1", "action", RiskLevel.R2, "approve", [], "trace"
    )
    artifact = evidence.add(
        "mission-1", "verification", "proof", "content", "trace"
    )
    checkpoint = ProductTwinEngine(store).capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    record_ids = [
        approval.approval_id,
        artifact.evidence_id,
        checkpoint.checkpoint_id,
    ]
    with store._lock, store._conn:
        store._conn.executemany(
            "UPDATE records SET origin_sha256=NULL WHERE record_id=?",
            [(record_id,) for record_id in record_ids],
        )
    store.close()

    migrated = SQLiteStore(path)
    assert all(migrated.get_record_envelope(record_id) for record_id in record_ids)
    migrated.close()
    reopened = SQLiteStore(path)
    assert all(reopened.get_record_envelope(record_id) for record_id in record_ids)


def test_approval_decision_event_conflict_rolls_back_record_transition(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "approval-decision-atomic.sqlite3")
    events = EventBus(store)
    approvals = ApprovalEngine(store, events)
    approval = approvals.request(
        "mission-1", "action", RiskLevel.R3, "approve", [], "trace"
    )
    events.publish(
        "attacker.conflict",
        approval.mission_id,
        "mission",
        "attacker",
        "conflict",
        {"approval_id": approval.approval_id},
        idempotency_key=f"approval.decided:{approval.approval_id}",
    )

    with pytest.raises(ValueError, match="event_idempotency_identity_conflict"):
        approvals.decide(
            approval.approval_id,
            True,
            "human-1",
            "approved",
            "decision-trace",
        )

    persisted = approvals.get(approval.approval_id)
    assert persisted is not None
    assert persisted.status == ApprovalStatus.PENDING
    assert not approvals.decision_transition_is_valid(persisted)


def test_approval_request_and_event_are_created_atomically(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "approval-request-atomic.sqlite3")
    with store._lock, store._conn:
        store._conn.execute(
            "CREATE TRIGGER reject_approval_request BEFORE INSERT ON events "
            "WHEN NEW.event_type='approval.requested' "
            "BEGIN SELECT RAISE(ABORT, 'forced event failure'); END"
        )
    approvals = ApprovalEngine(store, EventBus(store))

    with pytest.raises(sqlite3.IntegrityError, match="forced event failure"):
        approvals.request(
            "mission-1", "action", RiskLevel.R3, "approve", [], "trace"
        )

    assert store.count("records") == 0
    assert store.count("events") == 0


def test_evidence_verification_event_conflict_rolls_back_record_transition(
    tmp_path: Path,
) -> None:
    store, events, evidence = evidence_runtime(
        tmp_path / "evidence-verification-atomic.sqlite3"
    )
    artifact = evidence.add(
        "mission-1", "verification", "proof", "content", "trace"
    )
    events.publish(
        "attacker.conflict",
        artifact.evidence_id,
        "evidence",
        "attacker",
        "conflict",
        {"evidence_id": artifact.evidence_id},
        idempotency_key=(
            f"evidence.verify:{artifact.evidence_id}:{artifact.sha256}"
        ),
    )

    with pytest.raises(ValueError, match="event_idempotency_identity_conflict"):
        evidence.verify(artifact.evidence_id)

    payload = store.get_record_envelope(artifact.evidence_id)["payload"]
    assert payload["verification_status"] == "unverified"
    assert not evidence.is_preverified_and_integrity_bound(artifact.evidence_id)


def test_consumed_approval_event_blocks_resealed_reuse(tmp_path: Path) -> None:
    store, events, evidence = evidence_runtime(tmp_path / "approval-consumed.sqlite3")
    approvals = ApprovalEngine(store, events)
    twin = ProductTwinEngine(store)
    proof = evidence.add(
        "mission-1",
        "verification",
        "proof",
        "proof",
        "trace",
        verification_status="verified",
    )
    rollback = evidence.add(
        "mission-1",
        "verification",
        "rollback",
        "rollback",
        "trace",
        verification_status="verified",
    )
    checkpoint = twin.capture(
        mission_id="mission-1",
        expected_state={"version": 1},
        observed_state={"version": 1},
    )
    proposal = EvolutionProposal(
        proposal_id="proposal-consumption-binding",
        mission_id="mission-1",
        title="change",
        observed_problem={},
        proposed_changes=["change"],
        risk_level=RiskLevel.R3,
        evidence_refs=[proof.evidence_id],
        rollback_plan=["restore"],
        rollback_checkpoint_id=checkpoint.checkpoint_id,
        rollback_evidence_refs=[rollback.evidence_id],
    )
    approval = approvals.request(
        proposal.mission_id,
        proposal.promotion_action,
        proposal.risk_level,
        "approve",
        [],
        "trace",
        executor_id="executor-1",
        proposal_sha256=proposal.content_sha256,
    )
    approvals.decide(
        approval.approval_id,
        True,
        "human-1",
        "approved",
        "decision-trace",
    )
    gate = EvolutionPromotionGate(
        approvals, evidence, authorized_human_principals={"human-1"}
    )
    validation = EvolutionValidation(
        simulation_passed=True,
        verification_passed=True,
        accessibility_passed=True,
        governance_passed=True,
        approval_id=approval.approval_id,
        actor_id="executor-1",
    )

    first = gate.assess(proposal, validation)
    assert first.allowed
    consumption = store.get_event_by_idempotency(
        f"approval.consumed:{approval.approval_id}"
    )
    assert consumption is not None
    assert consumption["payload"]["proposal_sha256"] == proposal.content_sha256
    payload = store.get_record(approval.approval_id)
    assert payload is not None
    payload["status"] = ApprovalStatus.APPROVED.value
    store.save_record(
        approval.approval_id,
        "approval",
        payload,
        payload["created_at"],
        approval.mission_id,
    )

    replay = gate.assess(proposal, validation)
    assert not replay.allowed
    assert (
        "stored promotion approval was already consumed"
        in replay.required_actions
    )


def test_consumption_event_conflict_rolls_back_approval_status(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "approval-consumption-atomic.sqlite3")
    events = EventBus(store)
    approvals = ApprovalEngine(store, events)
    approval = approvals.request(
        "mission-1",
        "product_reality.promote:proposal-1",
        RiskLevel.R3,
        "approve",
        [],
        "trace",
        executor_id="executor-1",
        proposal_sha256="proposal-digest",
    )
    approvals.decide(
        approval.approval_id,
        True,
        "human-1",
        "approved",
        "decision-trace",
    )
    envelope = store.get_record_envelope(approval.approval_id)
    assert envelope is not None
    idempotency_key = f"approval.consumed:{approval.approval_id}"
    events.publish(
        "attacker.conflict",
        approval.mission_id,
        "mission",
        "attacker",
        "conflict",
        {"approval_id": approval.approval_id},
        idempotency_key=idempotency_key,
    )
    transition_event = {
        "event_id": approvals._transition_event_id(idempotency_key),
        "event_type": "approval.consumed",
        "aggregate_id": approval.mission_id,
        "aggregate_type": "mission",
        "actor": "executor-1",
        "trace_id": "promotion:proposal-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": idempotency_key,
        "payload": {
            "approval_id": approval.approval_id,
            "use_id": "proposal-1",
            "actor_id": "executor-1",
            "action": approval.action,
            "risk_level": approval.risk_level.value,
            "executor_id": approval.executor_id,
            "proposal_sha256": approval.proposal_sha256,
        },
    }

    persisted = store.compare_and_set_record_fields_and_events_atomically(
        [
            {
                "record_id": approval.approval_id,
                "record_type": "approval",
                "field": "status",
                "expected_value": ApprovalStatus.APPROVED.value,
                "new_value": ApprovalStatus.CONSUMED.value,
                "expected_integrity_sha256": envelope["integrity_sha256"],
            }
        ],
        [transition_event],
    )

    assert persisted is None
    assert approvals.get(approval.approval_id).status == ApprovalStatus.APPROVED
