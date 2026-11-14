"""R7: real SQLite + real EvidenceStore fail-closed outcome admission.

This suite uses product SQLiteStore, BrainDB, MemoryController, EvidenceStore
and ExperienceStore. Positive success tests STUB the external independent
business-acceptance and receipt verifiers at a dependency boundary; they are
component-contract tests, NOT proof of a real independent QA actor or Mac E2E.
"""
from __future__ import annotations

import json

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_recall import ExperienceRecall
from nexara_prime.brain.experience_store import ExperienceStore
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import Mission, MissionSpec, MissionState, WorkContract


@pytest.fixture
def stack(tmp_path):
    core = SQLiteStore(tmp_path / "core.sqlite")
    brain = BrainDB(tmp_path / "brain.sqlite")
    evidence = EvidenceStore(core, EventBus(core))
    memory = MemoryController(db=brain, persist=True)
    yield core, brain, evidence, memory
    brain.close()
    core.close()


def artifact(evidence, mission, *, kind="environment", actor="system", content="host online"):
    item = evidence.add(
        mission_id=mission,
        kind=kind,
        title=kind,
        content=content,
        trace_id="test-trace",
        actor=actor,
        source="isolated-n01-test",
    )
    assert evidence.verify(item.evidence_id)
    assert evidence.is_preverified_and_integrity_bound(item.evidence_id)
    return item.evidence_id


def record(store, mission, evidence_id, *, status="success", score=1.0):
    return store.record(
        mission_id=mission,
        objective="reconcile vendor invoices",
        risk_level="R1",
        adapter="local-parser",
        model="none",
        status=status,
        score=score,
        lessons=["verified parser handled matching invoices"],
        evidence_refs=[evidence_id],
    )


def complete_mission(core, evidence, mission, *, state=MissionState.COMPLETED,
                     reviewer_passed=True, auditor_passed=True, evaluation_passed=True):
    evidence_id = artifact(
        evidence, mission, kind="verification_report", actor="reviewer",
        content=json.dumps({"exists": True, "non_empty": True, "sha256": "test-report"}),
    )
    reviewer_id = artifact(
        evidence, mission, kind="reviewer_verdict", actor="reviewer",
        content=json.dumps({"actor": "reviewer", "mission_id": mission,
                            "passed": reviewer_passed}),
    )
    auditor_id = artifact(
        evidence, mission, kind="auditor_verdict", actor="auditor",
        content=json.dumps({"actor": "auditor", "mission_id": mission,
                            "passed": auditor_passed}),
    )
    spec = MissionSpec(
        mission_id=mission, title="Invoice reconciliation",
        objective="reconcile vendor invoices",
        acceptance_criteria=["Invoice totals independently agree"],
    )
    contract = WorkContract(
        mission_id=mission,
        objective=spec.objective,
        status="approved",
        acceptance_criteria=list(spec.acceptance_criteria),
    )
    obj = Mission(
        mission_id=mission,
        spec=spec,
        contract=contract,
        trace_id="test-trace",
        state=state,
        result={
            "evaluation_id": "evaluation-from-runtime",
            "evaluation_passed": evaluation_passed,
            "verification_evidence_id": evidence_id,
            "reviewer_evidence_id": reviewer_id,
            "auditor_evidence_id": auditor_id,
        },
    )
    core.save_record(
        mission, "mission", obj.model_dump(mode="json"), obj.created_at, mission
    )
    return evidence_id


def test_no_mission_health_probe_cannot_prove_success(stack):
    _, _, ev, mc = stack
    eid = artifact(ev, "m-health")
    s = ExperienceStore(mc, evidence_store=ev)
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        record(s, "m-health", eid)
    assert len(s) == 0


def test_cross_mission_evidence_is_rejected_before_success_gate(stack):
    _, _, ev, mc = stack
    foreign_id = artifact(ev, "m-other")
    s = ExperienceStore(mc, evidence_store=ev)
    with pytest.raises(ValueError, match="experience_verified_evidence_required"):
        record(s, "m-target", foreign_id)


def test_historical_success_is_quarantined_in_canonical_recall(stack):
    _, brain, ev, mc = stack
    eid = artifact(ev, "m-legacy")
    legacy = ExperienceStore(mc, evidence_validator=lambda mid, e: True)
    old = record(legacy, "m-legacy", eid)
    assert legacy.get(old.experience_id) is not None  # backwards-compatible ledger
    canonical = ExperienceStore(mc, evidence_store=ev)
    assert canonical.list_all() == []
    assert canonical.stats().success_rate == 0.0
    rec = ExperienceRecall(canonical).recommend_adapter("reconcile vendor invoices")
    assert rec["recommended_adapter"] == "claude"
    assert rec["confidence"] == 0.0
    assert any(x.get("key", "").startswith("mission_experience:")
               for x in mc._db.recall())  # historical row retained, not deleted


def test_failed_experience_with_verified_failure_evidence_survives(stack):
    _, _, ev, mc = stack
    eid = artifact(ev, "m-fail", kind="failure", content="parser returned exception")
    canonical = ExperienceStore(mc, evidence_store=ev)
    obj = record(canonical, "m-fail", eid, status="failed", score=0.2)
    assert canonical.get_by_mission("m-fail")[0].experience_id == obj.experience_id
    assert canonical.stats().success_rate == 0.0
    assert ExperienceRecall(canonical).recommend_adapter(
        "reconcile vendor invoices")["recommended_adapter"] == "claude"


def test_failed_experience_survives_actual_sqlite_reopen(stack):
    core, brain, ev, mc = stack
    mid = "m-failed-durable"
    eid = artifact(ev, mid, kind="failure", content="independent failure evidence")
    first = ExperienceStore(mc, evidence_store=ev)
    written = record(first, mid, eid, status="failed", score=0.3)
    second_core = SQLiteStore(core.path)
    second_brain = BrainDB(brain.path)
    try:
        second_evidence = EvidenceStore(second_core, EventBus(second_core))
        second_memory = MemoryController(db=second_brain, persist=True)
        restored = ExperienceStore(second_memory, evidence_store=second_evidence)
        items = restored.get_by_mission(mid)
        assert [item.experience_id for item in items] == [written.experience_id]
        assert restored.stats().success_rate == 0.0
    finally:
        second_brain.close()
        second_core.close()


def test_qualified_success_persists_across_reopen_with_trusted_test_seam(stack, monkeypatch):
    core, brain, ev, mc = stack
    mid = "m-success-durable-seam"
    eid = complete_mission(core, ev, mid)
    monkeypatch.setattr(ev, "receipt_status", lambda _mid: {"status": "present"})
    first = ExperienceStore(
        mc, evidence_store=ev,
        outcome_validator=lambda _mid, _eid: True,
    )
    written = record(first, mid, eid)
    second_core = SQLiteStore(core.path)
    second_brain = BrainDB(brain.path)
    try:
        second_evidence = EvidenceStore(second_core, EventBus(second_core))
        monkeypatch.setattr(
            second_evidence, "receipt_status",
            lambda _mid: {"status": "present"},
        )
        second_memory = MemoryController(db=second_brain, persist=True)
        restored = ExperienceStore(
            second_memory, evidence_store=second_evidence,
            outcome_validator=lambda _mid, _eid: True,
        )
        assert [e.experience_id for e in restored.get_by_mission(mid)] == [
            written.experience_id
        ]
    finally:
        second_brain.close()
        second_core.close()


def test_complete_mission_without_independent_outcome_callback_is_rejected(stack, monkeypatch):
    core, _, ev, mc = stack
    eid = complete_mission(core, ev, "m-no-outcome")
    monkeypatch.setattr(ev, "receipt_status", lambda mid: {"status": "present"})
    s = ExperienceStore(mc, evidence_store=ev)
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        record(s, "m-no-outcome", eid)


def test_completed_mission_without_real_receipt_is_rejected(stack):
    core, _, ev, mc = stack
    eid = complete_mission(core, ev, "m-no-receipt")
    s = ExperienceStore(
        mc, evidence_store=ev, outcome_validator=lambda mid, e: True
    )
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        record(s, "m-no-receipt", eid)


@pytest.mark.parametrize("state", [MissionState.RUNNING, MissionState.FAILED, MissionState.BLOCKED])
def test_nonterminal_or_failed_mission_never_promotes_success(stack, monkeypatch, state):
    core, _, ev, mc = stack
    eid = complete_mission(core, ev, f"m-state-{state.value}", state=state)
    monkeypatch.setattr(ev, "receipt_status", lambda mid: {"status": "present"})
    s = ExperienceStore(mc, evidence_store=ev, outcome_validator=lambda mid, e: True)
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        record(s, f"m-state-{state.value}", eid)


@pytest.mark.parametrize("reviewer,auditor", [(False, True), (True, False)])
def test_independent_verdict_must_pass(stack, monkeypatch, reviewer, auditor):
    core, _, ev, mc = stack
    mission = f"m-bad-verdict-{reviewer}-{auditor}"
    eid = complete_mission(
        core, ev, mission, reviewer_passed=reviewer, auditor_passed=auditor
    )
    monkeypatch.setattr(ev, "receipt_status", lambda mid: {"status": "present"})
    s = ExperienceStore(mc, evidence_store=ev, outcome_validator=lambda mid, e: True)
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        record(s, mission, eid)


def test_validated_verification_report_is_required_not_health_probe(stack, monkeypatch):
    core, _, ev, mc = stack
    mid = "m-verification-id"
    complete_mission(core, ev, mid)
    eid = artifact(ev, mid, kind="environment", content="health probe only")
    monkeypatch.setattr(ev, "receipt_status", lambda _mid: {"status": "present"})
    s = ExperienceStore(mc, evidence_store=ev, outcome_validator=lambda mid, e: True)
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        record(s, mid, eid)


def test_outcome_callback_error_fails_closed(stack, monkeypatch):
    core, _, ev, mc = stack
    mid = "m-outcome-exception"
    eid = complete_mission(core, ev, mid)
    monkeypatch.setattr(ev, "receipt_status", lambda _mid: {"status": "present"})
    def unavailable(mid, eid):
        raise RuntimeError("independent QA offline")
    s = ExperienceStore(mc, evidence_store=ev, outcome_validator=unavailable)
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        record(s, mid, eid)


def test_canonical_positive_dependency_seam_and_revocation(stack, monkeypatch):
    # This only proves integration with a trusted injected acceptance callback
    # and mocked receipt-status interface. It does NOT prove business QA works.
    core, _, ev, mc = stack
    mid = "m-verified-seam"
    eid = complete_mission(core, ev, mid)
    monkeypatch.setattr(ev, "receipt_status", lambda _mid: {"status": "present"})
    accepted = {"value": True}
    s = ExperienceStore(
        mc, evidence_store=ev,
        outcome_validator=lambda _mid, _eid: accepted["value"],
    )
    saved = record(s, mid, eid)
    assert s.get_by_mission(mid)[0].experience_id == saved.experience_id
    accepted["value"] = False
    assert s.get_by_mission(mid) == []
    assert ExperienceRecall(s).recommend_adapter(
        "reconcile vendor invoices")["recommended_adapter"] == "claude"
    assert any(x.get("key", "").startswith("mission_experience:")
               for x in mc._db.recall())  # history retained despite quarantine
