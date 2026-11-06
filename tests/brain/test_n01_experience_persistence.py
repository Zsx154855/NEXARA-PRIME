"""N01: durable verified experience / next-task adapter decision experiment.

These tests exercise the actual BrainDB + MemoryController on temporary SQLite.
They do not measure LLM hypothesis quality or real paid provider outcomes.
"""

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_recall import ExperienceRecall
from nexara_prime.brain.experience_store import ExperienceStore
from nexara_prime.brain.memory_controller import MemoryController


def store(tmp_path, *, checker=None):
    mc = MemoryController(db=BrainDB(tmp_path / "n01-experiences.db"))
    return ExperienceStore(mc, evidence_validator=checker), mc


def record_good(s):
    return s.record(
        mission_id="task-A", objective="reconcile vendor invoices",
        risk_level="R1", adapter="python", model="local", status="success",
        score=0.9, lessons=["verified parser handled matching invoices"],
        evidence_refs=["evidence-task-A"],
    )


def test_task_a_recalled_after_new_sqlite_controller(tmp_path):
    first, _ = store(tmp_path, checker=lambda mid, eid: (
        mid == "task-A" and eid == "evidence-task-A"
    ))
    exp = record_good(first)
    second, _ = store(tmp_path, checker=lambda mid, eid: False)
    assert second.get(exp.experience_id) is not None
    assert len(second) == 1
    assert second.get_by_mission("task-A")[0].evidence_refs == ["evidence-task-A"]


def test_task_b_decision_changes_with_real_recalled_experience(tmp_path):
    baseline = ExperienceRecall(ExperienceStore()).recommend_adapter(
        "reconcile supplier invoices"
    )
    assert baseline["recommended_adapter"] == "claude"
    first, _ = store(tmp_path, checker=lambda mid, eid: True)
    record_good(first)
    after_restart, _ = store(tmp_path)
    learned = ExperienceRecall(after_restart).recommend_adapter(
        "reconcile supplier invoices"
    )
    assert learned["recommended_adapter"] == "python"
    assert learned["based_on"] == 1
    assert learned["confidence"] == 1.0


def test_missing_evidence_is_rejected_before_memory_write(tmp_path):
    s, mc = store(tmp_path, checker=lambda mid, eid: True)
    with pytest.raises(ValueError, match="experience_verified_evidence_required"):
        s.record(
            mission_id="task-A", objective="reconcile vendor invoices",
            risk_level="R1", adapter="python", model="local", status="success",
            score=0.9,
        )
    assert not s.list_all()


def test_rejected_evidence_cannot_be_learned(tmp_path):
    s, _ = store(tmp_path, checker=lambda mid, eid: False)
    with pytest.raises(ValueError, match="experience_verified_evidence_required"):
        record_good(s)
    reopened, _ = store(tmp_path)
    assert len(reopened) == 0


def test_superseded_memory_disappears_even_in_same_process(tmp_path):
    s, mc = store(tmp_path, checker=lambda mid, eid: True)
    record_good(s)
    assert len(s) == 1
    records = mc.rank_retrieve(
        "mission_experience:", top_k=10, layers=["semantic"], min_confidence=0.0
    )
    assert len(records) == 1
    mc._db.update_status(records[0]["memory_id"], "superseded")
    assert len(s) == 0
    assert ExperienceRecall(s).search("reconcile supplier invoices").total_matches == 0


def test_bad_history_does_not_promote_failing_adapter(tmp_path):
    s, _ = store(tmp_path, checker=lambda mid, eid: True)
    s.record(
        mission_id="task-A", objective="reconcile vendor invoices",
        risk_level="R1", adapter="bad-adapter", model="local", status="failed",
        score=0.2, evidence_refs=["evidence-failure"],
    )
    later, _ = store(tmp_path)
    answer = ExperienceRecall(later).recommend_adapter("reconcile supplier invoices")
    assert answer["recommended_adapter"] == "claude"
    assert answer["confidence"] == 0.0


def test_backward_compatible_in_memory_store():
    original = ExperienceStore()
    exp = original.record(
        mission_id="legacy", objective="file report", risk_level="R1",
        adapter="legacy", model="local", status="success",
    )
    assert original.get(exp.experience_id) is not None
    assert len(original) == 1
