"""Task-2: trusted experience/lesson admission with receipt consistency.

Real SQLite (BrainDB + canonical SQLiteStore/EventBus/EvidenceStore). No MockMC,
no model calls. Covers:
- lesson evidence authenticity + mission ownership (write and recall);
- experience content consistency with the bound tool receipt / experience receipt;
- caller self-attestation (`verification_status="verified"`) limited by a trusted
  verification-event or verifier-actor allowlist;
- historical forged rows excluded on recall;
- rejection observability without sensitive data;
- controlled assembly requiring a real EvidenceStore.
"""

from __future__ import annotations

import json
import logging

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import ToolInvocation, new_id


def _runtime(tmp_path):
    brain = BrainDB(tmp_path / "task2-brain.db")
    core = SQLiteStore(tmp_path / "task2-core.db")
    events = EventBus(core)
    evidence = EvidenceStore(core, events)
    mc = MemoryController(db=brain)
    return brain, core, evidence, mc


def _tool_receipt(evidence, mission_id, tool_name, status="completed", actor="tool_runtime"):
    inv = ToolInvocation(
        mission_id=mission_id, tool_name=tool_name, status=status,
        result={"ok": True}, trace_id=f"trace-{mission_id}",
    )
    artifact = evidence.add(
        mission_id, "execution_receipt", f"Tool receipt: {tool_name}",
        inv.model_dump_json(), inv.trace_id,
        tool_invocation_id=inv.invocation_id,
        actor=actor, source="tool_runtime", verification_status="verified",
    )
    return artifact, inv


def _experience_receipt(evidence, mission_id, action, result, success, actor="verification_engine"):
    content = json.dumps({
        "mission_id": mission_id, "action": action,
        "result": result, "success": success,
    })
    return evidence.add(
        mission_id, "experience_receipt", "Experience receipt", content,
        f"trace-{mission_id}", actor=actor, source="verification",
        verification_status="verified",
    )


def _record(learner, mission_id, action, evidence_id, result="ok", success=True):
    return learner.record_outcome(
        mission_id, "success" if success else "failure", action,
        result, success, evidence_id=evidence_id,
    )


class TestLessonTrust:
    def test_forged_lesson_evidence_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            learner.record_lesson("mission-A", "trusted lesson", "ev-FORGED")
        assert learner.get_lessons("trusted") == []

    def test_cross_mission_lesson_evidence_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        other, _ = _tool_receipt(evidence, "mission-B", "run_pytest")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            learner.record_lesson("mission-A", "cross mission lesson", other.evidence_id)

    def test_historical_forged_lesson_row_is_not_recalled(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        mc.commit(
            mission_id="mission-A", key="lesson:mission-A:forged",
            content=json.dumps({"lesson": "forged lesson must not surface"}),
            kind="lesson", evidence_id="ev-FORGED", confidence=0.5,
        )
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.get_lessons("forged") == []

    def test_valid_lesson_is_recalled(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact, _ = _tool_receipt(evidence, "mission-A", "run_pytest")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        learner.record_lesson("mission-A", "always run tests first", artifact.evidence_id)
        assert learner.get_lessons("tests") == ["always run tests first"]


class TestReceiptConsistency:
    def test_tool_receipt_action_mismatch_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact, _ = _tool_receipt(evidence, "mission-A", "safe_tool")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "evil_tool", artifact.evidence_id)

    def test_tool_receipt_status_mismatch_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact, _ = _tool_receipt(evidence, "mission-A", "run_pytest", status="failed")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "run_pytest", artifact.evidence_id, success=True)

    def test_experience_receipt_fields_are_enforced(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact = _experience_receipt(evidence, "mission-A", "run_pytest", "ok", True)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "different_action", artifact.evidence_id)

    def test_historical_experience_without_receipt_digest_is_excluded(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact, inv = _tool_receipt(evidence, "mission-A", "run_pytest")
        content = json.dumps({
            "mission_id": "mission-A", "outcome": "success",
            "action": "run_pytest", "result": "ok", "success": True,
            "evidence_id": artifact.evidence_id,
        })
        mc.commit(
            mission_id="mission-A", key=f"exp:mission-A:{new_id('exp')}",
            content=content, kind="experience", evidence_id=artifact.evidence_id,
            confidence=0.5,
        )
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.rank_experiences("run_pytest") == []
        assert learner.extract_patterns() == []


class TestSelfAttestation:
    def test_caller_asserted_verified_is_not_trusted(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact, _ = _tool_receipt(evidence, "mission-A", "run_pytest", actor="random_caller")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            _record(learner, "mission-A", "run_pytest", artifact.evidence_id)

    def test_verified_transition_event_is_trusted(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        inv = ToolInvocation(
            mission_id="mission-A", tool_name="run_pytest", status="completed",
            result={"ok": True}, trace_id="trace-mission-A",
        )
        artifact = evidence.add(
            "mission-A", "execution_receipt", "Tool receipt", inv.model_dump_json(),
            "trace-mission-A", tool_invocation_id=inv.invocation_id,
            actor="random_caller", source="tool_runtime",
        )
        assert evidence.verify(artifact.evidence_id) is True
        learner = ExperienceLearner(mc, evidence_store=evidence)
        cid = _record(learner, "mission-A", "run_pytest", artifact.evidence_id)
        assert cid is not None

    def test_tool_runtime_receipt_is_trusted(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        artifact, _ = _tool_receipt(evidence, "mission-A", "run_pytest")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, "mission-A", "run_pytest", artifact.evidence_id)
        assert len(learner.rank_experiences("run_pytest")) == 1


class TestObservability:
    def test_rejections_are_counted_without_sensitive_data(self, tmp_path, caplog):
        _, _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with caplog.at_level(logging.WARNING):
            with pytest.raises(ValueError):
                _record(learner, "mission-A", "run_pytest", "ev-FORGED-SECRET")
        stats = learner.rejection_stats()
        assert stats.get("evidence_untrusted", 0) == 1
        joined = " ".join(record.getMessage() for record in caplog.records)
        assert "ev-FORGED-SECRET" not in joined
        assert "mission-A" not in joined


class TestControlledAssembly:
    def test_factory_requires_evidence_store(self, tmp_path):
        from nexara_prime.brain.experience_assembly import build_trusted_experience_learner

        _, _, _, mc = _runtime(tmp_path)
        with pytest.raises(ValueError):
            build_trusted_experience_learner(mc, None)

    def test_factory_builds_strict_learner(self, tmp_path):
        from nexara_prime.brain.experience_assembly import build_trusted_experience_learner

        _, _, evidence, mc = _runtime(tmp_path)
        artifact, _ = _tool_receipt(evidence, "mission-A", "run_pytest")
        learner = build_trusted_experience_learner(mc, evidence)
        _record(learner, "mission-A", "run_pytest", artifact.evidence_id)
        assert len(learner.rank_experiences("run_pytest")) == 1
