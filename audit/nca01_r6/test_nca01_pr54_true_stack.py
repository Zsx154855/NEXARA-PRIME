"""NCA-01 PR #54 real-store evidence/experience contracts.

Target: PR #54 HEAD 103c79f500c522492815f9b86dfa0fb80dd07e30.
Use a real checkout of that Git object; no mock MemoryController/EvidenceStore.
The final outcome-integrity test is deliberately RED until an independent
business outcome verifier exists. No model/network calls required by tests.
"""
from __future__ import annotations

import inspect

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.brain.experience_store import ExperienceStore


@pytest.fixture
def stack(tmp_path):
    assert "evidence_store" in inspect.signature(ExperienceStore.__init__).parameters, (
        "Requires PR #54 version of ExperienceStore; not main"
    )
    core_path = tmp_path / "core.sqlite"
    brain_path = tmp_path / "brain.sqlite"
    core = SQLiteStore(core_path)
    bus = EventBus(core)
    evidence = EvidenceStore(core, bus)
    brain = BrainDB(brain_path)
    memory = MemoryController(db=brain, persist=True)
    experience = ExperienceStore(memory_controller=memory, evidence_store=evidence)
    yield (core, evidence, brain, memory, experience, core_path, brain_path)
    brain.close()
    core.close()


def _verified(evidence, mission_id, content="health probe: host is online"):
    artifact = evidence.add(
        mission_id=mission_id, kind="environment", title="Environment health",
        content=content, trace_id=f"trace-{mission_id}",
        source="nca01-isolated-contract-test",
        idempotency_key=f"health:{mission_id}:{content}",
    )
    assert evidence.verify(artifact.evidence_id) is True
    assert evidence.is_preverified_and_integrity_bound(artifact.evidence_id) is True
    return artifact.evidence_id


def _record(store, mission_id, evidence_id):
    return store.record(
        mission_id=mission_id, objective="Deliver a real verified task",
        risk_level="R1", adapter="offline-test", model="none",
        status="success", score=1.0,
        lessons=["Use the approved tool receipt"], evidence_refs=[evidence_id],
    )


def test_mission_bound_evidence_rejects_foreign_success(stack):
    _, evidence, _, _, experience, *_ = stack
    eid = _verified(evidence, "foreign-mission")
    with pytest.raises(ValueError, match="experience_verified_evidence_required"):
        _record(experience, "local-mission", eid)


def test_verified_experience_is_durable_across_real_db_reopen(stack):
    core, evidence, brain, _, experience, core_path, brain_path = stack
    eid = _verified(evidence, "mission-durable")
    rec = _record(experience, "mission-durable", eid)
    # A second real SQLite connection recreates the service without mocks.
    second_core = SQLiteStore(core_path)
    second_evidence = EvidenceStore(second_core, EventBus(second_core))
    second_brain = BrainDB(brain_path)
    second_memory = MemoryController(db=second_brain, persist=True)
    try:
        restored = ExperienceStore(memory_controller=second_memory,
                                   evidence_store=second_evidence)
        found = restored.get_by_mission("mission-durable")
        assert [f.experience_id for f in found] == [rec.experience_id]
    finally:
        second_brain.close()
        second_core.close()


def test_valid_evidence_id_alone_cannot_prove_task_succeeded(stack):
    _, evidence, _, _, experience, *_ = stack
    # The artifact is real and integrity-verified, but it proves only that
    # an environment probe was online; it is NOT a successful task outcome.
    eid = _verified(evidence, "mission-false-success")
    with pytest.raises(ValueError, match="mission_outcome_not_independently_verified"):
        _record(experience, "mission-false-success", eid)
