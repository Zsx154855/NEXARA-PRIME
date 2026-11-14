"""R9-B2 source-qualified, two-DB read-only QA over real local Mission artifacts.

Positive test inserts an INJECTED outcome callback solely to exercise existing
ExperienceStore's admission seam. It is NOT independent QA business proof and
cannot establish agent identity or end-to-end autonomous transfer.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_store import ExperienceStore
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.brain.reasoning.context_assembler import MemoryRetrievalAdapter
from nexara_prime.models import ToolInvocation
from test_r9_b1_report_contract_acceptance import completed_report


def _store(runtime, tmp_path, allow=lambda _mid, _eid: True):
    brain = BrainDB(tmp_path / "r9-b2-brain.sqlite")
    mc = MemoryController(db=brain, persist=True)
    experience = ExperienceStore(
        mc, evidence_store=runtime.evidence, outcome_validator=allow,
    )
    return brain, mc, experience


def _record(experience, mission):
    return experience.record(
        mission_id=mission.mission_id,
        objective=mission.spec.objective,
        risk_level=mission.spec.risk_level.value,
        adapter="bounded-report",
        model="mock-test-only",
        status="success",
        score=1.0,
        lessons=["report evidence linked to one exact Mission"],
        evidence_refs=[mission.result["verification_evidence_id"]],
    )


def _read_only_authorizer(calls):
    denied = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
    def audit(action, arg1, arg2, database, source):
        if action in denied:
            calls.append((action, arg1, arg2))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return audit


def test_real_sqlite_success_reading_changes_neither_evidence_nor_brain_db(
    completed_report, tmp_path,
):
    runtime, mission, report_checker = completed_report
    contract = report_checker.evaluate(
        mission.mission_id, mission.result["verification_evidence_id"],
    )
    assert contract.status == "CONTRACT_PASS"
    assert contract.business_outcome_verified is False
    brain, mc, experience = _store(runtime, tmp_path)
    try:
        exp = _record(experience, mission)
        adapter = MemoryRetrievalAdapter(mc, verified_experiences=experience)

        core = runtime.store._conn
        brain_conn = brain._conn
        core_before = core.total_changes
        brain_before = brain_conn.total_changes
        attempted_core, attempted_brain = [], []
        core.set_authorizer(_read_only_authorizer(attempted_core))
        brain_conn.set_authorizer(_read_only_authorizer(attempted_brain))
        try:
            assert [x.experience_id for x in experience.list_trusted_successes()] == [
                exp.experience_id,
            ]
            memories = adapter.retrieve(
                mission.spec.objective, read_only=True,
            )
            assert len(memories) == 1
            assert memories[0]["key"] == f"mission_experience:{exp.experience_id}"
            assert json.loads(memories[0]["content"])["status"] == "success"
            assert [x.experience_id for x in experience.get_by_mission(
                mission.mission_id,
            )] == [exp.experience_id]
        finally:
            core.set_authorizer(None)
            brain_conn.set_authorizer(None)
        assert attempted_core == [], attempted_core
        assert attempted_brain == [], attempted_brain
        assert core.total_changes == core_before
        assert brain_conn.total_changes == brain_before
    finally:
        brain.close()


def test_unverified_extra_receipt_cannot_promote_or_mutate_during_recall(
    completed_report, tmp_path,
):
    runtime, mission, _report_checker = completed_report
    brain, mc, experience = _store(runtime, tmp_path)
    try:
        exp = _record(experience, mission)
        inv = ToolInvocation(
            mission_id=mission.mission_id,
            tool_name="file_write_report",
            status="completed",
            idempotency_key=f"{mission.mission_id}:unverified-qa",
            trace_id=mission.trace_id,
        )
        receipt = runtime.evidence.add(
            mission.mission_id,
            "execution_receipt", "Additional unverified tool receipt",
            inv.model_dump_json(), mission.trace_id,
            actor="tool_runtime", source="tool_runtime",
            verification_status="unverified",
            tool_invocation_id=inv.invocation_id,
        )
        inv.receipt_evidence_id = receipt.evidence_id
        runtime.store.save_record(
            inv.invocation_id, "tool", inv.model_dump(mode="json"),
            inv.created_at, mission.mission_id,
        )
        assert runtime.evidence.is_preverified_and_integrity_bound(
            receipt.evidence_id,
        ) is False
        core_before = runtime.store._conn.total_changes
        brain_before = brain._conn.total_changes
        assert experience.list_trusted_successes() == []
        assert experience.get(exp.experience_id) is None
        adapter = MemoryRetrievalAdapter(
            mc, verified_experiences=experience,
        )
        assert adapter.retrieve(mission.spec.objective, read_only=True) == []
        assert runtime.store._conn.total_changes == core_before
        assert brain._conn.total_changes == brain_before
        assert runtime.evidence.is_preverified_and_integrity_bound(
            receipt.evidence_id,
        ) is False
    finally:
        brain.close()


def test_regular_ranked_recall_still_records_access_when_explicit_read_is_off(
    completed_report, tmp_path,
):
    runtime, mission, _report_checker = completed_report
    brain, mc, experience = _store(runtime, tmp_path)
    try:
        record = _record(experience, mission)
        before = brain._conn.total_changes
        matches = mc.rank_retrieve(
            "mission_experience:", layers=["semantic"], min_confidence=0.0,
            record_access=False,
        )
        assert any(x["key"] == f"mission_experience:{record.experience_id}" for x in matches)
        assert brain._conn.total_changes == before

        default = mc.rank_retrieve(
            "mission_experience:", layers=["semantic"], min_confidence=0.0,
        )
        assert len(default) >= 1
        assert brain._conn.total_changes > before
    finally:
        brain.close()
