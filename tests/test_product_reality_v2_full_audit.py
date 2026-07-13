from __future__ import annotations

import json
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
from nexara_prime.models import ApprovalStatus, RiskLevel
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
