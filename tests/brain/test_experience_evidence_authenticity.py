"""Task-1: action experiences must be bound to authentic EvidenceStore receipts.

All stores are real SQLite temp databases (BrainDB + canonical SQLiteStore with
EventBus/EvidenceStore). No MockMC, no model provider, no network.

The suite covers the three trusted paths:
- commit: ``record_outcome`` refuses forged/unverified/cross-mission/corrupt evidence;
- recall: ``rank_experiences`` never returns rows whose evidence is not authentic;
- pattern extraction: ``extract_patterns`` / ``count_low_confidence`` exclude them.

It also proves read-only recall performs no SQL writes on either database.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import new_id, now_iso


def _runtime(tmp_path):
    brain = BrainDB(tmp_path / "task1-brain.db")
    core = SQLiteStore(tmp_path / "task1-core.db")
    events = EventBus(core)
    evidence = EvidenceStore(core, events)
    mc = MemoryController(db=brain)
    return brain, core, evidence, mc


def _verified(evidence, mission_id, action="run_pytest", result="ok", success=True):
    content = json.dumps({
        "mission_id": mission_id, "action": action,
        "result": result, "success": success,
    })
    return evidence.add(
        mission_id, "experience_receipt", "experience receipt", content,
        f"trace-{mission_id}", actor="verification_engine", source="verification",
        verification_status="verified",
    )


def _record(learner, mission_id, action, evidence_id, success=True):
    return learner.record_outcome(
        mission_id, "success" if success else "failure", action,
        "ok", success, evidence_id=evidence_id,
    )


def _poisoned_row(mc, mission_id, action, evidence_id, success=True):
    """Seed a row directly to simulate forged/legacy records already in BrainDB."""
    content = json.dumps({
        "mission_id": mission_id,
        "outcome": "success" if success else "failure",
        "action": action,
        "result": "ok",
        "success": success,
        "evidence_id": evidence_id,
        "patterns": [],
        "lessons": [],
        "confidence": 0.5,
        "trace_id": "",
        "created_at": now_iso(),
    })
    return mc.commit(
        mission_id=mission_id, key=f"exp:{mission_id}:{new_id('exp')}",
        content=content, kind="experience", evidence_id=evidence_id,
        confidence=0.5,
    )


class TestCommitPath:
    def test_forged_evidence_cannot_be_committed_or_learned(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            for i in range(3):
                _record(learner, "mission-A", "forged_tool", f"ev-FORGED-{i}")
        assert learner.extract_patterns() == []
        assert learner.rank_experiences("forged_tool") == []

    def test_cross_mission_evidence_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        other = _verified(evidence, "mission-B")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "run_pytest", other.evidence_id)
        _poisoned_row(mc, "mission-A", "run_pytest", other.evidence_id)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.rank_experiences("run_pytest") == []
        assert learner.extract_patterns() == []

    def test_unverified_evidence_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact = evidence.add(
            "mission-A", "verification", "proof", "not verified",
            "trace-mission-A",
        )
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "run_pytest", artifact.evidence_id)
        _poisoned_row(mc, "mission-A", "run_pytest", artifact.evidence_id)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.extract_patterns() == []

    def test_corrupted_evidence_is_rejected(self, tmp_path):
        _, core, evidence, mc = _runtime(tmp_path)
        artifact = _verified(evidence, "mission-A")
        with core._lock, core._conn:
            raw = core.get_record(artifact.evidence_id)
            raw["content"] = "tampered content"
            core._conn.execute(
                "UPDATE records SET payload=? WHERE record_id=?",
                (json.dumps(raw), artifact.evidence_id),
            )
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "run_pytest", artifact.evidence_id)
        _poisoned_row(mc, "mission-A", "run_pytest", artifact.evidence_id)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.rank_experiences("run_pytest") == []
        assert learner.extract_patterns() == []

    def test_validator_exception_fails_closed(self, tmp_path):
        _, _, _, mc = _runtime(tmp_path)

        def boom(_mission_id, _evidence_id):
            raise RuntimeError("validator unavailable")

        learner = ExperienceLearner(mc, evidence_validator=boom)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "run_pytest", "ev-any")
        assert learner.rank_experiences("run_pytest") == []
        assert learner.extract_patterns() == []

    def test_valid_same_mission_evidence_is_learned(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        for _ in range(3):
            artifact = _verified(evidence, "mission-A")
            _record(learner, "mission-A", "run_pytest", artifact.evidence_id)
        ranked = learner.rank_experiences("run_pytest")
        assert [r.action for r in ranked] == ["run_pytest"] * 3
        patterns = learner.extract_patterns()
        matches = [p for p in patterns if "run_pytest" in p.description]
        assert len(matches) == 1
        assert matches[0].frequency == 3
        assert matches[0].success_rate == 1.0


class TestDefaultLearner:
    def test_default_learner_fails_closed_without_verifier(self, tmp_path):
        """Regression baseline: a learner with no verifier must not trust any id."""
        _, _, _, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc)
        with pytest.raises(ValueError, match="evidence"):
            _record(learner, "mission-A", "forged_tool", "ev-FORGED")
        _poisoned_row(mc, "mission-A", "forged_tool", "ev-FORGED")
        learner = ExperienceLearner(mc)
        assert learner.rank_experiences("forged_tool") == []
        assert learner.extract_patterns() == []


class TestRecallAndExtractionPaths:
    def test_poisoned_rows_are_not_recalled_counted_or_patterned(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        for i in range(3):
            _poisoned_row(mc, "mission-A", "forged_tool", f"ev-FORGED-{i}")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.rank_experiences("forged_tool") == []
        assert learner.extract_patterns() == []
        assert learner.count_low_confidence(threshold=1.0) == 0

    def test_mixed_rows_only_authentic_ones_are_learned(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        for _ in range(3):
            good = _verified(evidence, "mission-A", "good_tool")
            _record(learner, "mission-A", "good_tool", good.evidence_id)
        _poisoned_row(mc, "mission-A", "bad_tool", "ev-FORGED")
        ranked = learner.rank_experiences("tool")
        assert [r.action for r in ranked] == ["good_tool"] * 3
        patterns = learner.extract_patterns()
        assert {p.description.split("'")[1] for p in patterns} == {"good_tool"}


class TestReadOnlyRecall:
    def _deny_writes(self, calls):
        denied = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}

        def audit(action, arg1, arg2, database, source):
            if action in denied:
                calls.append((action, arg1, arg2))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        return audit

    def test_recall_and_extraction_issue_no_sql_writes(self, tmp_path):
        brain, core, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        for _ in range(3):
            artifact = _verified(evidence, "mission-A")
            _record(learner, "mission-A", "run_pytest", artifact.evidence_id)

        core_before = core._conn.total_changes
        brain_before = brain._conn.total_changes
        attempted_core, attempted_brain = [], []
        core._conn.set_authorizer(self._deny_writes(attempted_core))
        brain._conn.set_authorizer(self._deny_writes(attempted_brain))
        try:
            assert len(learner.rank_experiences("run_pytest")) == 3
            assert learner.extract_patterns()
            assert learner.count_low_confidence(threshold=0.0) == 0
            learner.summarize()
        finally:
            core._conn.set_authorizer(None)
            brain._conn.set_authorizer(None)
        assert attempted_core == [], attempted_core
        assert attempted_brain == [], attempted_brain
        assert core._conn.total_changes == core_before
        assert brain._conn.total_changes == brain_before

    def test_default_rank_retrieve_still_logs_access(self, tmp_path):
        brain, _, _, mc = _runtime(tmp_path)
        mc.commit(
            mission_id="mission-A", key="note:1", content="note",
            kind="short_term", confidence=0.9,
        )
        with brain._lock:
            before = brain._conn.execute(
                "SELECT COUNT(*) FROM memory_access_log"
            ).fetchone()[0]
        mc.rank_retrieve("note")
        with brain._lock:
            after = brain._conn.execute(
                "SELECT COUNT(*) FROM memory_access_log"
            ).fetchone()[0]
        assert after == before + 1
