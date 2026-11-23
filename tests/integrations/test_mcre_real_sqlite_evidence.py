"""M1 repository integration test: actual SQLiteStore/EventBus/EvidenceStore.

This test REQUIRES the complete NEXARA checkout. It is intentionally not part
of the isolated MCRE unit suite. No network, models or production data.

Evidence integrity is NOT host identity/authenticated independent QA proof.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from nexara_prime.brain.mcre_evidence_binding import EvidenceStoreBinding
from nexara_prime.brain.mcre_mission_shadow import MissionShadowObserver, ShadowSnapshot
from nexara_prime.brain.mcre_shadow import ContextRef
from nexara_prime.brain.verified_skill_evolution import SkillCandidate, Trial, VerifiedSkillEvolution
from nexara_prime.db import SQLiteStore
from nexara_prime.evidence import EvidenceStore
from nexara_prime.events import EventBus
from nexara_prime.models import Mission, MissionSpec, RiskLevel


@pytest.fixture
def store_and_evidence(tmp_path):
    store = SQLiteStore(tmp_path / "mcre.sqlite")
    evidence = EvidenceStore(store, EventBus(store))
    yield store, evidence
    store.close()


def commit_context(evidence, *, mission_id="m1", scope="tenant-a", project="NEXARA-PRIME"):
    fields = dict(project_id=project, repo_sha="f4a5400d73391280fa9c19e128edcea03cf608f1",
                  environment_id="py312-test", scope_id=scope)
    content = json.dumps(fields, sort_keys=True)
    artifact = evidence.add(mission_id=mission_id, kind="mcre_context", title="pinned context",
                            content=content, trace_id="mcre:test", source="isolated-test",
                            actor="test-harness", task_id="t1")
    assert evidence.verify(artifact.evidence_id) is True
    ref = ContextRef(evidence_id=artifact.evidence_id, content_digest=hashlib.sha256(content.encode()).hexdigest(),
                     **fields)
    return artifact, ref


def test_real_sqlite_verified_context_and_shadow_mission(store_and_evidence):
    _db, evidence = store_and_evidence
    artifact, ref = commit_context(evidence)
    assert evidence.is_preverified_and_integrity_bound(artifact.evidence_id)
    assert EvidenceStoreBinding(evidence).verify_context(ref)
    mission = Mission(mission_id="m1", spec=MissionSpec(mission_id="m1", title="M1", objective="Validate",
                                                      risk_level=RiskLevel.R1), trace_id="trace-m1")
    snapshot = ShadowSnapshot(project_id=ref.project_id, repo_sha=ref.repo_sha,
                              environment_id=ref.environment_id, scope_id=ref.scope_id,
                              context_refs=(ref,))
    result = MissionShadowObserver(evidence).observe(mission, snapshot)
    assert result.strategy == "REUSE"
    assert result.shadow_only and not result.execution_authorized
    assert result.evidence_ids == (artifact.evidence_id,)


def test_real_sqlite_rejects_cross_scope_and_stale_head(store_and_evidence):
    _db, evidence = store_and_evidence
    _, ref = commit_context(evidence)
    binding = EvidenceStoreBinding(evidence)
    other_scope = ContextRef(ref.evidence_id, ref.project_id, ref.repo_sha, ref.environment_id,
                             "other-tenant", ref.content_digest)
    other_sha = ContextRef(ref.evidence_id, ref.project_id, "changed-head", ref.environment_id,
                           ref.scope_id, ref.content_digest)
    assert not binding.verify_context(other_scope)
    assert not binding.verify_context(other_sha)


def test_real_sqlite_rejects_corrupted_origin_after_verify(store_and_evidence):
    store, evidence = store_and_evidence
    artifact, ref = commit_context(evidence)
    # Deliberate corruption is limited to a temp DB and MUST break integrity.
    with store._lock, store._conn:
        store._conn.execute("UPDATE records SET origin_sha256=? WHERE record_id=?",
                            ("0" * 64, artifact.evidence_id))
    assert not EvidenceStoreBinding(evidence).verify_context(ref)


def test_real_sqlite_trial_receipts_do_not_promote_without_external_authority(store_and_evidence):
    _db, evidence = store_and_evidence
    trials = []
    for i in range(3):
        for variant, turns, tokens, cost in (("treatment", 4, 80, 0.002),
                                             ("control", 6, 100, 0.003)):
            task_id = f"unseen-{i}"
            fields = dict(task_id=task_id, variant=variant, passed=True, turns=turns,
                          reviewer_id="qa-operator", input_tokens=tokens, cost_usd=cost)
            artifact = evidence.add(mission_id="m1", kind="skill_eval_trial", title="sealed evaluation",
                                    content=json.dumps(fields, sort_keys=True), trace_id="eval:test",
                                    actor="qa-operator", source="isolated-test", task_id=task_id)
            assert evidence.verify(artifact.evidence_id) is True
            trials.append(Trial(evidence_id=artifact.evidence_id, **fields))
    candidate = SkillCandidate(skill_id="skill:example", version="v2", author_id="engineer",
                               baseline_version="v1", rollback_ref="sha:fixture",
                               development_task_ids=frozenset({"development-task"}))
    result = VerifiedSkillEvolution(EvidenceStoreBinding(evidence).verify_trial).assess(candidate, tuple(trials))
    # A PASS here establishes only integrity of the synthetic receipts; it does
    # NOT authenticate the reviewer, source truth, or prove real transfer.
    assert result.status == "ELIGIBLE_FOR_REVIEW"
    assert not result.authorization_granted and not result.active_version_changed
