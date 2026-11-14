"""R8 trusted recall: REAL SQLite and product classes.

Successful learning in this test uses injected *stub* receipt and outcome
verifiers to exercise the integration seam. It does NOT prove independent
business acceptance or authorize production use.
"""
from __future__ import annotations

import json

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_store import ExperienceStore
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.brain.reasoning.context_assembler import MemoryRetrievalAdapter
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import Mission, MissionSpec, MissionState, WorkContract


def _verified(evidence, mission_id, kind, actor, content):
    item = evidence.add(
        mission_id=mission_id, kind=kind, title=kind, content=content,
        trace_id=f"trace-{mission_id}", actor=actor, source="r8-local-test",
    )
    assert evidence.verify(item.evidence_id) is True
    assert evidence.is_preverified_and_integrity_bound(item.evidence_id) is True
    return item.evidence_id


def test_real_sqlite_verified_success_can_enter_trusted_reasoning_then_be_revoked(
    tmp_path, monkeypatch,
):
    core = SQLiteStore(tmp_path / "core.sqlite")
    brain = BrainDB(tmp_path / "brain.sqlite")
    try:
        evidence = EvidenceStore(core, EventBus(core))
        mc = MemoryController(db=brain, persist=True)
        mission_id = "r8-approved"
        report = _verified(
            evidence, mission_id, "verification_report", "reviewer",
            json.dumps({"exists": True, "non_empty": True}),
        )
        reviewer = _verified(
            evidence, mission_id, "reviewer_verdict", "reviewer",
            json.dumps({"mission_id": mission_id, "actor": "reviewer", "passed": True}),
        )
        auditor = _verified(
            evidence, mission_id, "auditor_verdict", "auditor",
            json.dumps({"mission_id": mission_id, "actor": "auditor", "passed": True}),
        )

        spec = MissionSpec(
            mission_id=mission_id, title="Reconcile invoices",
            objective="reconcile vendor invoices",
            acceptance_criteria=["Vendor totals independently match"],
        )
        contract = WorkContract(
            mission_id=mission_id, objective=spec.objective,
            status="approved", acceptance_criteria=list(spec.acceptance_criteria),
        )
        mission = Mission(
            mission_id=mission_id, spec=spec, contract=contract,
            state=MissionState.COMPLETED, trace_id=f"trace-{mission_id}",
            result={
                "evaluation_id": "evaluation-from-runtime",
                "evaluation_passed": True,
                "verification_evidence_id": report,
                "reviewer_evidence_id": reviewer,
                "auditor_evidence_id": auditor,
            },
        )
        core.save_record(
            mission_id, "mission", mission.model_dump(mode="json"),
            mission.created_at, mission_id,
        )
        monkeypatch.setattr(
            evidence, "receipt_status",
            lambda _mid: {"status": "present"},
        )
        allowed = {"value": True}
        experiences = ExperienceStore(
            mc, evidence_store=evidence,
            outcome_validator=lambda _mid, _eid: allowed["value"],
        )
        record = experiences.record(
            mission_id=mission_id, objective=spec.objective,
            risk_level="R1", adapter="local-parser", model="none",
            status="success", score=1.0,
            evidence_refs=[report],
        )

        # The default cognitive adapter refuses raw successful rows,
        # including a valid one, unless explicitly bound to a canonical
        # trusted-success view.
        default = MemoryRetrievalAdapter(mc)
        baseline = default.retrieve(spec.objective)
        assert not any(r.get("kind") == "experience" for r in baseline)

        trusted = MemoryRetrievalAdapter(
            mc, verified_experiences=experiences
        )
        promoted = trusted.retrieve(spec.objective)
        assert len(promoted) == 1
        assert promoted[0]["key"] == f"mission_experience:{record.experience_id}"

        allowed["value"] = False
        after_revocation = trusted.retrieve(spec.objective)
        assert not any(r.get("kind") == "experience" for r in after_revocation)

        allowed["value"] = True
        # Callback-only (legacy) store is never a trusted source even when
        # externally supplied and configured with always-True evidence checks.
        legacy = ExperienceStore(mc, evidence_validator=lambda _m, _e: True)
        unsafe_adapter = MemoryRetrievalAdapter(
            mc, verified_experiences=legacy
        )
        assert not any(
            r.get("kind") == "experience"
            for r in unsafe_adapter.retrieve(spec.objective)
        )
    finally:
        brain.close()
        core.close()


def test_real_failure_experience_remains_in_reasoning_context(tmp_path):
    core = SQLiteStore(tmp_path / "core.sqlite")
    brain = BrainDB(tmp_path / "brain.sqlite")
    try:
        ev = EvidenceStore(core, EventBus(core))
        mc = MemoryController(db=brain, persist=True)
        proof = _verified(
            ev, "r8-failure", "execution_failure", "reviewer",
            "Parser failed independently observed",
        )
        ExperienceStore(mc, evidence_store=ev).record(
            mission_id="r8-failure", objective="reconcile vendor invoices",
            risk_level="R1", adapter="broken-parser", model="none",
            status="failed", score=0.1, evidence_refs=[proof],
        )
        matches = MemoryRetrievalAdapter(mc).retrieve("reconcile vendor invoices")
        assert len(matches) == 1
        assert json.loads(matches[0]["content"])["status"] == "failed"
    finally:
        brain.close()
        core.close()
