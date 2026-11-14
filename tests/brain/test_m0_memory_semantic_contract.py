"""M0 memory contract regression: real BrainDB, no MockMC, no provider calls.

This suite intentionally checks the isolated memory path only. Passing it does
NOT establish Runtime wiring, EvidenceStore integrity, or autonomous learning.
All stores are isolated via pytest's tmp_path fixture.
"""

import json

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.memory import MemoryKernel, MemoryLayerManager
from nexara_prime.memory_os import MemoryOS, MemoryType


def _controller(tmp_path):
    return MemoryController(db=BrainDB(tmp_path / "m0_contract.db"))


def _record_action(learner, n=1):
    for i in range(n):
        learner.record_outcome(
            "mission-A", "completed", "run_pytest",
            f"pass {i}", True, evidence_id=f"ev-action-{i}",
        )


def test_action_experience_is_semantic_and_recalled_after_restart(tmp_path):
    # Taxonomy test: authenticity is covered by test_experience_evidence_authenticity.py.
    learner = ExperienceLearner(_controller(tmp_path), evidence_validator=lambda _m, _e: True)
    _record_action(learner)
    assert _controller(tmp_path)._db.recall(mission_id="mission-A")[0]["layer"] == "semantic"
    restarted = ExperienceLearner(_controller(tmp_path), evidence_validator=lambda _m, _e: True)
    hits = restarted.rank_experiences("run_pytest")
    assert len(hits) == 1
    assert hits[0].action == "run_pytest" and hits[0].success is True


def test_action_experience_extracts_real_pattern(tmp_path):
    learner = ExperienceLearner(_controller(tmp_path), evidence_validator=lambda _m, _e: True)
    _record_action(learner, n=3)
    patterns = learner.extract_patterns()
    matches = [p for p in patterns if "run_pytest" in p.description]
    assert len(matches) == 1
    assert matches[0].frequency == 3
    assert matches[0].success_rate == 1.0


def test_n01_mission_summaries_cannot_become_failed_action_samples(tmp_path):
    mc = _controller(tmp_path)
    # PR #54 persists mission-level records using this key/schema in semantic.
    for i in range(3):
        mc.commit(
            mission_id=f"mission-{i}", key=f"mission_experience:exp_{i}",
            kind="experience", evidence_id=f"ev-summary-{i}",
            content=json.dumps({
                "experience_id": f"exp_{i}", "mission_id": f"mission-{i}",
                "objective": "run_pytest", "risk_level": "R1",
                "adapter": "local", "model": "local",
                "status": "success", "score": 0.9,
                "lessons": [], "evidence_refs": [f"ev-summary-{i}"],
            }),
        )
    learner = ExperienceLearner(mc)
    assert learner.extract_patterns() == []
    assert learner.rank_experiences("run_pytest") == []
    assert learner.count_low_confidence(threshold=1.0) == 0


def test_action_payload_with_conflicting_evidence_is_not_learned(tmp_path):
    mc = _controller(tmp_path)
    mc.commit(
        mission_id="mission-A", kind="experience",
        key="exp:mission-A:forged", evidence_id="ev-actual",
        content=json.dumps({
            "mission_id": "mission-A", "outcome": "completed",
            "action": "run_pytest", "result": "ok",
            "success": True, "evidence_id": "ev-other",
        }),
    )
    learner = ExperienceLearner(mc)
    assert learner.rank_experiences("run_pytest") == []
    assert learner.extract_patterns() == []


def test_lesson_is_procedural_and_requires_evidence(tmp_path):
    # Taxonomy test: authenticity is covered by test_trusted_experience_task2.py.
    learner = ExperienceLearner(_controller(tmp_path), evidence_validator=lambda _m, _e: True)
    with pytest.raises(ValueError, match="memory_evidence_required"):
        learner.record_lesson("mission-A", "reject forged receipts")
    learner.record_lesson("mission-A", "reject forged receipts", "ev-lesson-1")
    data = _controller(tmp_path)._db.recall(mission_id="mission-A")
    assert len(data) == 1
    assert data[0]["kind"] == "lesson" and data[0]["layer"] == "procedural"
    assert ExperienceLearner(
        _controller(tmp_path), evidence_validator=lambda _m, _e: True
    ).get_lessons("forged") == ["reject forged receipts"]


def test_legacy_procedural_kind_is_not_silently_promoted(tmp_path):
    mc = _controller(tmp_path)
    mc.commit(
        mission_id="mission-A", kind="procedural",
        key="lesson:mission-A:legacy", content='{"lesson": "unverified legacy note"}',
    )
    assert ExperienceLearner(mc).get_lessons("legacy") == []


def _canonical(tmp_path):
    store = SQLiteStore(tmp_path / "m0_canonical.db")
    events = EventBus(store)
    evidence = EvidenceStore(store, events)
    kernel = MemoryKernel(store, events, evidence)
    return store, kernel


def test_pending_review_does_not_leak_through_keyword_fallback(tmp_path):
    _, kernel = _canonical(tmp_path)
    manager = MemoryLayerManager(kernel, rag=None, enable_patch_review=True)
    candidate = manager.propose_patch(
        "ops:runbook", "unreviewed runbook steps", "trace-1",
        mission_id="mission-A", evidence_id="ev-pending",
    )
    assert candidate["status"] == "pending_review"
    assert manager.search("unreviewed runbook") == []


def test_active_memoryos_entry_not_hidden_by_fallback_filter(tmp_path):
    store, kernel = _canonical(tmp_path)
    MemoryOS(store).create_entry(
        MemoryType.SEMANTIC, "runbook document", source="operator",
    )
    manager = MemoryLayerManager(kernel, rag=None)
    assert manager.search("runbook")



def test_validated_but_not_activated_record_is_not_visible(tmp_path):
    # VALIDATED is not yet ACTIVE in the MemoryOS/archive lifecycle.
    store, kernel = _canonical(tmp_path)
    store.save_record(
        "mem-validated-only", "memory",
        {
            "memory_id": "mem-validated-only",
            "mission_id": "mission-A",
            "key": "draft:validation",
            "kind": "fact",
            "content": "validated only, not activated",
            "status": "validated",
        },
        "2026-11-12T00:00:00+00:00", "mission-A",
    )
    manager = MemoryLayerManager(kernel, rag=None)
    assert manager.search("validated only", mission_id="mission-A") == []



def test_no_evidence_action_experience_is_rejected(tmp_path):
    learner = ExperienceLearner(_controller(tmp_path))
    with pytest.raises(ValueError, match="memory_evidence_required"):
        learner.record_outcome("mission-A", "completed", "run_pytest", "ok", True)
