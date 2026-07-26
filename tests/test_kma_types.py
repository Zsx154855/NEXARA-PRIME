"""KMA Phase 2 — KMA Runtime Types Tests.

Validates all 4 Pydantic models against their JSON schemas.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexara_prime.models import (
    CapabilityHistory,
    KnowledgeCommit,
    KnowledgeObject,
    KnowledgeRecall,
    KnowledgeRelation,
    MemoryKind,
    MemoryRecord,
)


class TestKnowledgeObject:
    def test_create_minimal(self):
        ko = KnowledgeObject(object_type="evidence")
        assert ko.object_id.startswith("kobj_")
        assert ko.object_type == "evidence"
        assert ko.confidence == 1.0

    def test_create_all_types(self):
        for t in ("evidence", "memory", "receipt"):
            ko = KnowledgeObject(object_type=t)
            assert ko.object_type == t

    def test_rejects_invalid_type(self):
        with pytest.raises(Exception):
            KnowledgeObject(object_type="invalid")

    def test_stable_id_unique(self):
        ko1 = KnowledgeObject(object_type="evidence")
        ko2 = KnowledgeObject(object_type="evidence")
        assert ko1.object_id != ko2.object_id

    def test_serialization(self):
        ko = KnowledgeObject(object_type="memory", mission_id="m1")
        data = ko.model_dump(mode="json")
        assert data["object_type"] == "memory"
        assert data["mission_id"] == "m1"
        assert "object_id" in data
        assert "created_at" in data

    def test_roundtrip(self):
        ko = KnowledgeObject(
            object_type="receipt",
            mission_id="m1",
            sha256="a" * 64,
            envelope_sha256="b" * 64,
            confidence=0.5,
        )
        data = ko.model_dump(mode="json")
        ko2 = KnowledgeObject.model_validate(data)
        assert ko2.object_id == ko.object_id
        assert ko2.confidence == 0.5

    def test_json_schema_matches(self):
        schema_path = (
            Path(__file__).parent.parent
            / "contracts/kma/KNOWLEDGE_OBJECT_SCHEMA_V1.json"
        )
        schema = json.loads(schema_path.read_text())
        required = set(schema.get("required", []))
        model_fields = set(KnowledgeObject.model_fields.keys())
        assert "object_id" in required
        assert "object_type" in required
        for req in required:
            assert req in model_fields, f"Schema required field '{req}' missing from model"


class TestKnowledgeRelation:
    def test_create_minimal(self):
        kr = KnowledgeRelation(
            source_id="a", target_id="b", relation_type="evidence_backing"
        )
        assert kr.relation_id.startswith("rel_")
        assert kr.confidence == 1.0
        assert kr.bidirectional is False

    def test_all_relation_types(self):
        valid = [
            "evidence_backing", "receipt_attests", "memory_derived_from",
            "supersedes", "conflicts_with", "references",
            "parent_of", "child_of", "depends_on", "produced_by", "verified_by",
        ]
        for rt in valid:
            kr = KnowledgeRelation(source_id="s", target_id="t", relation_type=rt)
            assert kr.relation_type == rt

    def test_rejects_invalid_relation(self):
        with pytest.raises(Exception):
            KnowledgeRelation(source_id="s", target_id="t", relation_type="bad_type")

    def test_idempotent_id_different(self):
        kr1 = KnowledgeRelation(source_id="a", target_id="b", relation_type="references")
        kr2 = KnowledgeRelation(source_id="a", target_id="b", relation_type="references")
        assert kr1.relation_id != kr2.relation_id

    def test_serialization_roundtrip(self):
        kr = KnowledgeRelation(
            source_id="obj_a", target_id="obj_b",
            relation_type="supersedes", confidence=0.8, weight=0.5,
        )
        data = kr.model_dump(mode="json")
        kr2 = KnowledgeRelation.model_validate(data)
        assert kr2.source_id == "obj_a"
        assert kr2.weight == 0.5


class TestKnowledgeRecall:
    def test_create_minimal(self):
        kq = KnowledgeRecall(query="test query", trace_id="t1")
        assert kq.query == "test query"
        assert kq.top_k == 10
        assert kq.min_confidence == 0.3

    def test_rejects_empty_query(self):
        with pytest.raises(Exception):
            KnowledgeRecall(query="", trace_id="t1")

    def test_rejects_top_k_out_of_range(self):
        # top_k=0 is valid (means no results)
        KnowledgeRecall(query="ok", top_k=0, trace_id="t1")
        with pytest.raises(Exception):
            KnowledgeRecall(query="ok", top_k=101, trace_id="t1")

    def test_rejects_confidence_out_of_range(self):
        with pytest.raises(Exception):
            KnowledgeRecall(query="ok", min_confidence=-0.1, trace_id="t1")
        with pytest.raises(Exception):
            KnowledgeRecall(query="ok", min_confidence=1.1, trace_id="t1")

    def test_layers_validation(self):
        kq = KnowledgeRecall(
            query="q", layers=["working", "semantic"], trace_id="t1"
        )
        assert kq.layers == ["working", "semantic"]

    def test_json_schema_matches(self):
        schema_path = (
            Path(__file__).parent.parent
            / "contracts/kma/KNOWLEDGE_RECALL_SCHEMA_V1.json"
        )
        schema = json.loads(schema_path.read_text())
        required = set(schema.get("required", []))
        model_fields = set(KnowledgeRecall.model_fields.keys())
        assert "query" in required
        for req in required:
            assert req in model_fields, f"Schema required field '{req}' missing from model"


class TestKnowledgeCommit:
    def test_create_minimal(self):
        kc = KnowledgeCommit(
            kind=MemoryKind.FACT, key="k1", content="test content",
            trace_id="t1", idempotency_key="ik-min",
        )
        assert kc.kind == MemoryKind.FACT
        assert kc.key == "k1"
        assert kc.auto_commit is False
        assert kc.idempotency_key == "ik-min"

    def test_rejects_empty_key(self):
        with pytest.raises(Exception):
            KnowledgeCommit(kind=MemoryKind.FACT, key="", content="c",
                            trace_id="t1", idempotency_key="ik1")

    def test_rejects_empty_content(self):
        with pytest.raises(Exception):
            KnowledgeCommit(kind=MemoryKind.FACT, key="k", content="",
                            trace_id="t1", idempotency_key="ik1")

    def test_rejects_missing_idempotency_key(self):
        with pytest.raises(Exception):
            KnowledgeCommit(kind=MemoryKind.FACT, key="k", content="c", trace_id="t1")

    def test_all_memory_kinds(self):
        for kind in MemoryKind:
            kc = KnowledgeCommit(kind=kind, key="k", content="c",
                                 trace_id="t1", idempotency_key="ik-ak")
            assert kc.kind == kind

    def test_confidence_range(self):
        with pytest.raises(Exception):
            KnowledgeCommit(
                kind=MemoryKind.FACT, key="k", content="c",
                trace_id="t1", confidence=-0.1, idempotency_key="ik1",
            )
        with pytest.raises(Exception):
            KnowledgeCommit(
                kind=MemoryKind.FACT, key="k", content="c",
                trace_id="t1", confidence=1.1, idempotency_key="ik1",
            )

    def test_receipt_id_optional(self):
        kc = KnowledgeCommit(
            kind=MemoryKind.PATCH, key="k", content="c",
            trace_id="t1", receipt_id="r1", idempotency_key="ik-r",
        )
        assert kc.receipt_id == "r1"

    def test_json_schema_matches(self):
        schema_path = (
            Path(__file__).parent.parent
            / "contracts/kma/KNOWLEDGE_COMMIT_SCHEMA_V1.json"
        )
        schema = json.loads(schema_path.read_text())
        required = set(schema.get("required", []))
        model_fields = set(KnowledgeCommit.model_fields.keys())
        for req in required:
            assert req in model_fields, f"Schema required field '{req}' missing from model"


class TestCapabilityHistory:
    def test_create_minimal(self):
        ch = CapabilityHistory(capability_id="skill.test")
        assert ch.record_id.startswith("caphist_")
        assert ch.success is True
        assert ch.schema_version == 1

    def test_full_record(self):
        ch = CapabilityHistory(
            capability_id="skill.evidence",
            mission_id="m1",
            provider="deepseek-v4-pro",
            model="deepseek-v4-pro",
            success=False,
            failure_kind="PROVIDER_TIMEOUT",
            latency_ms=1500.0,
            input_tokens=2000,
            output_tokens=500,
            cost=0.005,
            retry_count=2,
            recovery=True,
            evaluation_score=0.85,
            evidence_id="e1",
            idempotency_key="key-abc",
        )
        assert ch.failure_kind == "PROVIDER_TIMEOUT"
        assert ch.recovery is True
        assert ch.evaluation_score == 0.85

    def test_serialization(self):
        ch = CapabilityHistory(capability_id="c1", mission_id="m1", success=True)
        data = ch.model_dump(mode="json")
        assert data["capability_id"] == "c1"
        assert data["mission_id"] == "m1"

    def test_record_id_unique(self):
        ch1 = CapabilityHistory(capability_id="c1")
        ch2 = CapabilityHistory(capability_id="c1")
        assert ch1.record_id != ch2.record_id


class TestKnowledgeObjectStatusEnum:
    def test_valid_statuses(self):
        valid = [
            "committed", "candidate", "conflict", "superseded",
            "pending_review", "cleared", "unverified", "verified", "corrupt",
        ]
        for status in valid:
            ko = KnowledgeObject(object_type="evidence", status=status)
            assert ko.status == status

    def test_rejects_invalid_status(self):
        with pytest.raises(Exception):
            KnowledgeObject(object_type="evidence", status="invalid_status")

    def test_default_status(self):
        ko = KnowledgeObject(object_type="evidence")
        assert ko.status == "committed"

    def test_schema_enum_matches(self):
        schema_path = (
            Path(__file__).parent.parent
            / "contracts/kma/KNOWLEDGE_OBJECT_SCHEMA_V1.json"
        )
        schema = json.loads(schema_path.read_text())
        schema_statuses = set(schema["properties"]["status"]["enum"])
        from typing import get_args
        model_statuses = set(get_args(KnowledgeObject.model_fields["status"].annotation))
        assert schema_statuses == model_statuses


class TestMemoryRecordReceiptId:
    def test_receipt_id_field_added(self):
        mr = MemoryRecord(kind=MemoryKind.FACT, key="k", content="c", receipt_id="r1")
        assert mr.receipt_id == "r1"

    def test_receipt_id_default_none(self):
        mr = MemoryRecord(kind=MemoryKind.FACT, key="k", content="c")
        assert mr.receipt_id is None

    def test_write_propagates_receipt_id(self):
        """receipt_id passed to write() is stored on the MemoryRecord."""
        import tempfile
        from nexara_prime.db import SQLiteStore
        from nexara_prime.events import EventBus
        from nexara_prime.memory import MemoryKernel

        db_path = Path(tempfile.mkdtemp()) / "test.db"
        store = SQLiteStore(db_path)
        try:
            events = EventBus(store)
            kernel = MemoryKernel(store, events)
            record = kernel.write(
                MemoryKind.FACT, "test_key", "test_content",
                trace_id="t1", receipt_id="r123",
            )
            assert record.receipt_id == "r123"
        finally:
            store.close()

    def test_propose_propagates_receipt_id(self):
        """receipt_id passed to propose() is stored on the MemoryRecord."""
        import tempfile
        from nexara_prime.db import SQLiteStore
        from nexara_prime.events import EventBus
        from nexara_prime.memory import MemoryKernel

        db_path = Path(tempfile.mkdtemp()) / "test.db"
        store = SQLiteStore(db_path)
        try:
            events = EventBus(store)
            kernel = MemoryKernel(store, events)
            record = kernel.propose(
                MemoryKind.FACT, "pk", "propose_content",
                trace_id="t2", source_evidence_id="ev1",
                receipt_id="r456",
            )
            assert record.receipt_id == "r456"
        finally:
            store.close()
