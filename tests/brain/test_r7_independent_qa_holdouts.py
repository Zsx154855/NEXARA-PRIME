"""Independent R7 holdouts. REAL product modules and temporary SQLite.

QA-01: historical, integrity-verified environment-heartbeat success cannot
be passed directly from MemoryController into reasoning context.
QA-02: in-memory canonical experience should revalidate an outcome when a
trusted callback revokes it. The positive seam intentionally stubs receipt
status and business evaluation: it is NOT production independent QA.

Run these tests on this QA-only branch; expected initial status RED. Do not
turn off assertions or change product source in this branch.
"""
from __future__ import annotations

import json

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.brain.experience_store import ExperienceStore
from nexara_prime.brain.reasoning.context_assembler import MemoryRetrievalAdapter
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import Mission, MissionSpec, MissionState, WorkContract


def _evidence(evidence, mission_id, kind, actor, content):
    item = evidence.add(
        mission_id=mission_id, kind=kind, title=kind, content=content,
        trace_id=f"trace-{mission_id}", actor=actor,
        source="r7-independent-qa",
    )
    assert evidence.verify(item.evidence_id) is True
    assert evidence.is_preverified_and_integrity_bound(item.evidence_id) is True
    return item.evidence_id


def _success(experiences, mission_id, evidence_id):
    return experiences.record(
        mission_id=mission_id, objective="reconcile vendor invoices",
        risk_level="R1", adapter="local-parser", model="none",
        status="success", score=1.0,
        lessons=["parser output was accepted"],
        evidence_refs=[evidence_id],
    )


def test_unverified_historical_success_cannot_enter_reasoning_context(tmp_path):
    core = SQLiteStore(tmp_path / "core.sqlite")
    brain = BrainDB(tmp_path / "brain.sqlite")
    try:
        evidence = EvidenceStore(core, EventBus(core))
        mc = MemoryController(db=brain, persist=True)
        mission_id = "qa-historical-success"
        heartbeat = _evidence(
            evidence, mission_id, "environment", "system", "host online"
        )

        # Reconstruct a pre-R7 PR54 historical success with real, valid
        # EvidenceStore evidence but no independently verified business outcome.
        legacy = ExperienceStore(
            mc,
            evidence_validator=lambda mid, eid: (
                evidence.is_preverified_and_integrity_bound(eid) is True
                and evidence.get_by_id(eid).mission_id == mid
            ),
        )
        _success(legacy, mission_id, heartbeat)

        canonical = ExperienceStore(mc, evidence_store=evidence)
        assert canonical.list_all() == []  # R7 scoped quarantine works

        # Actual production ContextAssembler's adapter goes directly to
        # MemoryController.rank_retrieve rather than canonical ExperienceStore.
        raw_for_reasoning = MemoryRetrievalAdapter(mc).retrieve(
            "reconcile vendor invoices", strategy="broad_semantic"
        )
        leaked = [
            item for item in raw_for_reasoning
            if item.get("kind") == "experience"
            and json.loads(item.get("content", "{}")).get("status") == "success"
        ]
        assert leaked == [], (
            "Historical unverified successful experience bypasses the "
            "canonical ExperienceStore filter and enters reasoning context"
        )
    finally:
        brain.close()
        core.close()


def test_in_memory_outcome_revocation_removes_success_from_recall(tmp_path, monkeypatch):
    core = SQLiteStore(tmp_path / "core.sqlite")
    try:
        evidence = EvidenceStore(core, EventBus(core))
        mid = "qa-revocation-inmemory"
        report = _evidence(
            evidence, mid, "verification_report", "reviewer",
            json.dumps({"exists": True, "non_empty": True}),
        )
        reviewer = _evidence(
            evidence, mid, "reviewer_verdict", "reviewer",
            json.dumps({"mission_id": mid, "actor": "reviewer", "passed": True}),
        )
        auditor = _evidence(
            evidence, mid, "auditor_verdict", "auditor",
            json.dumps({"mission_id": mid, "actor": "auditor", "passed": True}),
        )
        spec = MissionSpec(
            mission_id=mid, title="Invoice reconciliation",
            objective="reconcile vendor invoices",
            acceptance_criteria=["Invoice totals independently agree"],
        )
        contract = WorkContract(
            mission_id=mid, objective=spec.objective,
            status="approved", acceptance_criteria=list(spec.acceptance_criteria),
        )
        mission = Mission(
            mission_id=mid, spec=spec, contract=contract,
            state=MissionState.COMPLETED, trace_id=f"trace-{mid}",
            result={
                "evaluation_id": "test-eval", "evaluation_passed": True,
                "verification_evidence_id": report,
                "reviewer_evidence_id": reviewer,
                "auditor_evidence_id": auditor,
            },
        )
        core.save_record(
            mid, "mission", mission.model_dump(mode="json"),
            mission.created_at, mid,
        )
        # Injection only exercises a component contract. Not a valid business
        # verdict or real receipt producer.
        monkeypatch.setattr(
            evidence, "receipt_status", lambda _mid, **_kwargs: {"status": "present"}
        )
        allowed = {"value": True}
        store = ExperienceStore(
            evidence_store=evidence,
            outcome_validator=lambda _mid, _eid: allowed["value"],
        )
        _success(store, mid, report)
        assert len(store.list_all()) == 1

        allowed["value"] = False
        assert store.list_all() == [], (
            "In-memory ExperienceStore returns cached successful experiences "
            "without re-checking the revoked trusted outcome"
        )
    finally:
        core.close()
