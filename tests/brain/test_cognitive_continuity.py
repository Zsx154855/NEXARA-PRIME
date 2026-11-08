"""Isolated zero-model, zero-network cognitive bootstrap regression tests."""
from __future__ import annotations

import json

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.brain.cognitive_continuity import (
    AutonomousGoalLoop,
    CognitiveStateStore,
    ContinuityError,
    EvidenceGatedLearning,
)
from nexara_prime.brain.environment.intelligence import EnvironmentEvent, EventType


@pytest.fixture
def kit(tmp_path):
    db = SQLiteStore(tmp_path / "cognitive.db")
    evidence = EvidenceStore(db, EventBus(db))
    yield db, evidence
    db.close()


def proof(evidence, mission="m1", actor="auditor", content="{}", source_event_id=None):
    art = evidence.add(mission, "test_result", "verified test", content,
                       trace_id="test", actor=actor, source="offline_test", source_event_id=source_event_id)
    assert evidence.verify(art.evidence_id)
    assert evidence.is_preverified_and_integrity_bound(art.evidence_id)
    return art.evidence_id


def test_cognitive_state_restart_and_optimistic_revision(kit):
    db, evidence = kit
    p = proof(evidence)
    state = CognitiveStateStore(db, evidence, "project-a", owner_authorizer=lambda _: True)
    initial = state.load()
    assert initial.revision == 0
    updated = state.update(expected_revision=0, actor="owner", evidence_id=p,
                           changes={"owner_goals": ["Zero-cost autonomous audits"],
                                    "commitments": ["No production writes"]})
    assert updated.revision == 1
    restarted = CognitiveStateStore(db, evidence, "project-a", owner_authorizer=lambda _: True).load()
    assert restarted.owner_goals == ("Zero-cost autonomous audits",)
    assert restarted.last_evidence_id == p
    with pytest.raises(ContinuityError, match="stale_cognitive_revision"):
        state.update(expected_revision=0, actor="owner", evidence_id=p,
                     changes={"identity": "not committed"})
    assert CognitiveStateStore(db, evidence, "project-b").load().revision == 0


def test_cognitive_state_denies_unverified_or_agent_core_changes(kit):
    db, evidence = kit
    state = CognitiveStateStore(db, evidence, "scope", owner_authorizer=lambda _: True)
    with pytest.raises(ContinuityError, match="verified_evidence_required"):
        state.update(expected_revision=0, actor="owner", evidence_id="fake",
                     changes={"owner_goals": ["x"]})
    p = proof(evidence)
    with pytest.raises(ContinuityError, match="state_permission_denied"):
        state.update(expected_revision=0, actor="agent", evidence_id=p,
                     changes={"owner_goals": ["override owner"]})
    next_state = state.update(expected_revision=0, actor="agent", evidence_id=p,
                              changes={"hypotheses": ["Connection may be offline"]})
    assert next_state.hypotheses == ("Connection may be offline",)
    assert next_state.owner_goals == ()


def test_cognitive_state_detects_corrupted_chain(kit):
    db, evidence = kit
    state = CognitiveStateStore(db, evidence, "scope", owner_authorizer=lambda _: True)
    state.update(expected_revision=0, actor="owner", evidence_id=proof(evidence),
                 changes={"beliefs": ["verified statement"]})
    with db._lock, db._conn:
        db._conn.execute("UPDATE records SET payload=? WHERE record_type=?",
                         ('{"revision":999}', "cognitive_state_v1"))
    with pytest.raises(ValueError):
        state.load()


def test_autonomous_goal_proposals_verified_and_idempotent(kit):
    db, evidence = kit
    events = [EnvironmentEvent(f"f{i}", EventType.TEST_FAILURE, "pytest", "6 common failures")
              for i in range(2)]
    refs = {e.event_id: proof(evidence, source_event_id=e.event_id) for e in events}
    loop = AutonomousGoalLoop(db, evidence, "project")
    first = loop.tick(events, refs)
    assert len(first) == 1
    assert first[0]["new"] is True
    assert first[0]["risk_level"] == "R0"
    assert first[0]["execution_authorized"] is False
    again = AutonomousGoalLoop(db, evidence, "project").tick(events, refs)
    assert again[0]["proposal_id"] == first[0]["proposal_id"]
    assert again[0]["new"] is False
    assert len(loop.list_proposals()) == 1


def test_autonomous_goal_does_not_ingest_unverified_claims(kit):
    db, evidence = kit
    events = [EnvironmentEvent(f"f{i}", EventType.TEST_FAILURE, "pytest", "claim")
              for i in range(2)]
    loop = AutonomousGoalLoop(db, evidence, "project")
    assert loop.tick(events, {"f0": "fabricated", "f1": "fabricated2"}) == []
    assert loop.list_proposals() == []


def test_learning_candidate_requires_independent_verified_metrics(kit):
    db, evidence = kit
    before = proof(evidence, content=json.dumps({"tests_passed": 10, "tests_failed": 0, "tokens": 900}))
    after = proof(evidence, content=json.dumps({"tests_passed": 11, "tests_failed": 0, "tokens": 500}))
    learner = EvidenceGatedLearning(db, evidence, "project", auditor_authorizer=lambda _: True)
    record = learner.evaluate(mission_id="m1", strategy="Symbol-level file retrieval",
                              baseline_id=before, candidate_id=after,
                              executor_id="dev", auditor_id="auditor")
    assert record["status"] == "REVIEWABLE"
    assert record["activated"] is False
    assert record["permission_granted"] is False
    assert learner.evaluate(mission_id="m1", strategy="Symbol-level file retrieval",
                            baseline_id=before, candidate_id=after,
                            executor_id="dev", auditor_id="auditor")["new"] is False
    assert len(learner.list_candidates()) == 1
    with pytest.raises(ContinuityError, match="independent_evidence_required"):
        learner.evaluate(mission_id="m1", strategy="bad", baseline_id=before, candidate_id=after,
                         executor_id="auditor", auditor_id="auditor")


def test_learning_regression_and_mission_mismatch_fail_closed(kit):
    db, evidence = kit
    before = proof(evidence, content=json.dumps({"tests_passed": 10, "tests_failed": 0, "tokens": 300}))
    after = proof(evidence, content=json.dumps({"tests_passed": 10, "tests_failed": 1, "tokens": 100}))
    learner = EvidenceGatedLearning(db, evidence, "project", auditor_authorizer=lambda _: True)
    rejected = learner.evaluate(mission_id="m1", strategy="poor regression", baseline_id=before,
                                candidate_id=after, executor_id="dev", auditor_id="auditor")
    assert rejected["status"] == "REJECTED"
    assert not rejected["activated"]
    with pytest.raises(ContinuityError, match="evaluator_identity_or_mission_mismatch"):
        learner.evaluate(mission_id="m2", strategy="mismatch", baseline_id=before,
                         candidate_id=after, executor_id="dev", auditor_id="auditor")


def test_learning_refuses_unverified_result_and_forged_metrics(kit):
    db, evidence = kit
    before = proof(evidence, content=json.dumps({"tests_passed": 10, "tests_failed": 0, "tokens": 300}))
    unknown = "evidence_not_found"
    learner = EvidenceGatedLearning(db, evidence, "project", auditor_authorizer=lambda _: True)
    with pytest.raises(ContinuityError, match="verified_evidence_required"):
        learner.evaluate(mission_id="m1", strategy="fake", baseline_id=before,
                         candidate_id=unknown, executor_id="dev", auditor_id="auditor")
    malformed = proof(evidence, content="not json metrics")
    with pytest.raises(ContinuityError, match="verified_metrics_invalid"):
        learner.evaluate(mission_id="m1", strategy="fake", baseline_id=before,
                         candidate_id=malformed, executor_id="dev", auditor_id="auditor")
