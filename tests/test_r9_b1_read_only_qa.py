"""R9-B1 independent QA: prove contract inspection cannot update SQLite.

Real runtime Mission, approval, report bytes and receipt are created inside
the existing temporary-db fixture. This is NOT a live business outcome test.
The 8 original B1 cases remain byte-identical and unmodified.
"""
from __future__ import annotations

import sqlite3

from nexara_prime.models import ToolInvocation
from test_r9_b1_report_contract_acceptance import completed_report


def test_report_verifier_leaves_db_unchanged_on_repeated_acceptance(completed_report):
    runtime, mission, verifier = completed_report
    mid = mission.mission_id
    before = runtime.store._conn.total_changes
    first = verifier.evaluate(mid, mission.result["verification_evidence_id"])
    middle = runtime.store._conn.total_changes
    second = verifier.evaluate(mid, mission.result["verification_evidence_id"])
    after = runtime.store._conn.total_changes

    assert first.status == second.status == "CONTRACT_PASS", (first, second)
    assert first.business_outcome_verified is False
    assert second.business_outcome_verified is False
    assert (before, middle, after) == (before, before, before)


def test_read_only_receipt_chain_rejects_unverified_evidence_without_promotion(
    completed_report,
):
    runtime, mission, _verifier = completed_report
    mid = mission.mission_id
    inv = ToolInvocation(
        mission_id=mid,
        tool_name="file_write_report",
        trace_id=mission.trace_id,
        status="completed",
        idempotency_key=f"{mid}:qa-unverified-tool",
    )
    receipt = runtime.evidence.add(
        mid, "execution_receipt", "Unverified extra tool receipt",
        inv.model_dump_json(), mission.trace_id,
        actor="tool_runtime", source="tool_runtime",
        verification_status="unverified",
        tool_invocation_id=inv.invocation_id,
    )
    inv.receipt_evidence_id = receipt.evidence_id
    runtime.store.save_record(
        inv.invocation_id, "tool", inv.model_dump(mode="json"),
        inv.created_at, mid,
    )
    assert runtime.evidence.is_preverified_and_integrity_bound(receipt.evidence_id) is False

    before = runtime.store._conn.total_changes
    status = runtime.evidence.receipt_status(
        mid, tool_names=["file_write_report"], read_only=True,
    )
    after = runtime.store._conn.total_changes
    assert status["status"] != "present", status
    assert status["chain_intact"] is False
    assert after == before, (before, after)
    assert runtime.evidence.is_preverified_and_integrity_bound(receipt.evidence_id) is False

    # Backward compatibility: the legacy, explicitly repair-capable API
    # still verifies and may promote a valid yet unverified receipt.
    legacy = runtime.evidence.receipt_status(
        mid, tool_names=["file_write_report"],
    )
    assert legacy["status"] == "present", legacy
    assert runtime.evidence.is_preverified_and_integrity_bound(receipt.evidence_id) is True


def test_sqlite_readonly_authorizer_allows_contract_evaluation_without_writes(
    completed_report,
):
    runtime, mission, verifier = completed_report
    observed_writes = []
    prohibited = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}

    def authorizer(action, arg1, arg2, db_name, source):
        if action in prohibited:
            observed_writes.append((action, arg1, arg2))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection = runtime.store._conn
    before = connection.total_changes
    connection.set_authorizer(authorizer)
    try:
        result = verifier.evaluate(
            mission.mission_id, mission.result["verification_evidence_id"],
        )
    finally:
        connection.set_authorizer(None)
    assert observed_writes == [], observed_writes
    assert result.status == "CONTRACT_PASS", result
    assert result.business_outcome_verified is False
    assert connection.total_changes == before
