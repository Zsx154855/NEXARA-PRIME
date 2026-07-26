"""KMA Phase 2 — EvidenceStore Extended API Tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.config import Settings
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.runtime import NexaraRuntime


@pytest.fixture
def evidence_store():
    db = Path(tempfile.mkdtemp()) / "test.db"
    store = SQLiteStore(db)
    events = EventBus(store)
    return EvidenceStore(store, events)


@pytest.fixture
def runtime():
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


class TestGetById:
    def test_get_existing_evidence(self, evidence_store):
        artifact = evidence_store.add("m1", "test", "Test", "hello", "t1")
        result = evidence_store.get_by_id(artifact.evidence_id)
        assert result.evidence_id == artifact.evidence_id
        assert result.content == "hello"

    def test_get_missing_raises_keyerror(self, evidence_store):
        with pytest.raises(KeyError):
            evidence_store.get_by_id("nonexistent")


class TestGetByIdempotencyKey:
    def test_get_by_idempotency_key(self, evidence_store):
        artifact = evidence_store.add(
            "m1", "test", "Test", "content", "t1",
            idempotency_key="ikey-1",
        )
        result = evidence_store.get_by_idempotency_key("ikey-1")
        assert result is not None
        assert result.evidence_id == artifact.evidence_id


class TestGetEnvelope:
    def test_get_envelope_for_existing(self, evidence_store):
        artifact = evidence_store.add("m1", "test", "T", "c", "t1")
        envelope = evidence_store.get_envelope(artifact.evidence_id)
        assert envelope is not None
        assert envelope["record_type"] == "evidence"


class TestReceiptStatus:
    def test_receipt_status_no_tools(self, evidence_store):
        result = evidence_store.receipt_status("no-tools-mission")
        assert result["status"] in ("missing", "present", "unverifiable")
        assert "chain_intact" in result


class TestFindByIdempotency:
    def test_find_by_idempotency(self, evidence_store):
        evidence_store.add("m1", "test", "T", "c", "t1", idempotency_key="key-x")
        result = evidence_store.find_by_idempotency("key-x")
        assert result is not None

    def test_find_missing_returns_none(self, evidence_store):
        assert evidence_store.find_by_idempotency("no-such-key") is None


class TestNoRawStoreBypass:
    def test_runtime_uses_evidence_api_not_store(self, runtime):
        import inspect
        source = inspect.getsource(runtime._get_evidence_by_idempotency)
        assert "store.find_record" not in source
        assert "evidence.find_by_idempotency" in source
