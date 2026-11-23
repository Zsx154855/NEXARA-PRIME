"""Real-SQLite lifecycle negatives for the MCRE evidence path (M1 supplement).

Adds the lifecycle cases the M1 repository test does not cover: reopen after
close, duplicate submission idempotency, and concurrent-handle conflict.
Real SQLiteStore/EventBus/EvidenceStore only; temp DB; no network.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from nexara_prime.brain.mcre_evidence_binding import EvidenceStoreBinding
from nexara_prime.brain.mcre_shadow import ContextRef
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore

FIELDS = dict(
    project_id="NEXARA-PRIME",
    repo_sha="7ecbdf3c1093d0f0a8ba954fc198f78b4cc569d0",
    environment_id="py312-test",
    scope_id="tenant-a",
)


def _open(path):
    store = SQLiteStore(path)
    return store, EvidenceStore(store, EventBus(store))


def _add(evidence, *, key=None, content=None, mission_id="m1"):
    body = content if content is not None else json.dumps(FIELDS, sort_keys=True)
    artifact = evidence.add(
        mission_id=mission_id,
        kind="mcre_context",
        title="pinned context",
        content=body,
        trace_id="mcre:lifecycle",
        source="isolated-test",
        actor="test-harness",
        task_id="t1",
        idempotency_key=key,
    )
    return artifact, body


def _count(path, table):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_reopen_after_close_preserves_evidence_and_binding(tmp_path):
    db = tmp_path / "mcre.sqlite"
    store, evidence = _open(db)
    artifact, body = _add(evidence)
    assert evidence.verify(artifact.evidence_id) is True
    ref = ContextRef(
        evidence_id=artifact.evidence_id,
        content_digest=hashlib.sha256(body.encode()).hexdigest(),
        **FIELDS,
    )
    store.close()

    store2, evidence2 = _open(db)
    try:
        assert evidence2.verify(artifact.evidence_id) is True
        assert evidence2.is_preverified_and_integrity_bound(artifact.evidence_id)
        assert EvidenceStoreBinding(evidence2).verify_context(ref) is True
    finally:
        store2.close()


def test_duplicate_submission_is_idempotent_and_single_row(tmp_path):
    db = tmp_path / "mcre.sqlite"
    store, evidence = _open(db)
    try:
        first, _ = _add(evidence, key="idem-1")
        second, _ = _add(evidence, key="idem-1")
        assert first.evidence_id == second.evidence_id
        assert _count(db, "records") == 1
    finally:
        store.close()


def test_duplicate_key_with_changed_payload_is_rejected(tmp_path):
    db = tmp_path / "mcre.sqlite"
    store, evidence = _open(db)
    try:
        _add(evidence, key="idem-2")
        with pytest.raises(Exception):
            _add(evidence, key="idem-2", content=json.dumps({"tampered": True}))
        assert _count(db, "records") == 1
    finally:
        store.close()


def test_concurrent_handle_conflict_on_same_evidence_id(tmp_path):
    db = tmp_path / "mcre.sqlite"
    store_a, evidence_a = _open(db)
    store_b, evidence_b = _open(db)
    try:
        artifact, _ = _add(evidence_a, key="idem-3")
        # Same idempotency key from a second real connection must not fork state.
        replay, _ = _add(evidence_b, key="idem-3")
        assert replay.evidence_id == artifact.evidence_id
        assert _count(db, "records") == 1
        assert evidence_b.verify(replay.evidence_id) is True
    finally:
        store_a.close()
        store_b.close()
