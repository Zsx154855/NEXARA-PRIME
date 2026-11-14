"""Task-3: close task-2 re-entry gaps (lesson digest, receipt kind, seam closure)."""

from __future__ import annotations

import json

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import ToolInvocation


def _runtime(tmp_path):
    brain = BrainDB(tmp_path / "t3-brain.db")
    core = SQLiteStore(tmp_path / "t3-core.db")
    events = EventBus(core)
    evidence = EvidenceStore(core, events)
    return brain, core, evidence, MemoryController(db=brain)


def _tool_receipt(evidence, mission_id, tool_name, status="completed", extra=None):
    inv = ToolInvocation(
        mission_id=mission_id, tool_name=tool_name, status=status,
        result={"ok": True}, trace_id=f"trace-{mission_id}",
    )
    content = inv.model_dump()
    if extra:
        content.update(extra)
    return evidence.add(
        mission_id, "execution_receipt", f"Tool receipt: {tool_name}",
        json.dumps(content), inv.trace_id,
        tool_invocation_id=inv.invocation_id,
        actor="tool_runtime", source="tool_runtime",
        verification_status="verified",
    )


def _seed_lesson(mc, mission_id, lesson, evidence_id, digest=None):
    content = {"lesson": lesson}
    if digest is not None:
        content["evidence_sha256"] = digest
    mc.commit(
        mission_id=mission_id, key=f"lesson:{mission_id}:seed",
        content=json.dumps(content), kind="lesson",
        evidence_id=evidence_id, confidence=0.5,
    )


class TestLessonDigestBinding:
    def test_lesson_without_digest_reference_is_not_recalled(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        receipt = _tool_receipt(evidence, "mission-A", "run_pytest")
        _seed_lesson(mc, "mission-A", "no digest lesson", receipt.evidence_id)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.get_lessons("digest") == []

    def test_lesson_with_wrong_digest_is_not_recalled(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        receipt = _tool_receipt(evidence, "mission-A", "run_pytest")
        _seed_lesson(mc, "mission-A", "wrong digest lesson", receipt.evidence_id, "deadbeef")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.get_lessons("digest") == []

    def test_valid_lesson_with_digest_is_recalled(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        receipt = _tool_receipt(evidence, "mission-A", "run_pytest")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        learner.record_lesson("mission-A", "always run tests", receipt.evidence_id)
        assert learner.get_lessons("tests") == ["always run tests"]

    def test_cross_mission_historical_lesson_row_is_excluded(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        other = _tool_receipt(evidence, "mission-B", "run_pytest")
        _seed_lesson(mc, "mission-A", "cross mission lesson", other.evidence_id, other.sha256)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.get_lessons("cross") == []


class TestReceiptKindAndResult:
    def test_unsupported_receipt_kind_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        content = json.dumps({
            "mission_id": "mission-A", "action": "run_pytest",
            "result": "ok", "success": True,
        })
        artifact = evidence.add(
            "mission-A", "verification", "verification receipt", content,
            "trace-mission-A", actor="verification_engine", source="verification",
            verification_status="verified",
        )
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            learner.record_outcome(
                "mission-A", "success", "run_pytest", "ok", True,
                evidence_id=artifact.evidence_id,
            )

    def test_execution_receipt_result_summary_mismatch_is_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        receipt = _tool_receipt(
            evidence, "mission-A", "run_pytest",
            extra={"result_summary": "tool said something else"},
        )
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError):
            learner.record_outcome(
                "mission-A", "success", "run_pytest", "different summary", True,
                evidence_id=receipt.evidence_id,
            )

    def test_business_failure_receipt_is_accepted(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        receipt = _tool_receipt(evidence, "mission-A", "run_pytest", status="failed")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        learner.record_outcome(
            "mission-A", "failure", "run_pytest", "failed", False,
            evidence_id=receipt.evidence_id,
        )
        assert len(learner.rank_experiences("run_pytest")) == 1


class TestSeamClosure:
    def test_validator_seam_requires_explicit_test_flag(self, tmp_path):
        _, _, _, mc = _runtime(tmp_path)
        with pytest.raises(ValueError):
            ExperienceLearner(mc, evidence_validator=lambda _m, _e: True)

    def test_validator_seam_allows_tests_with_flag(self, tmp_path):
        _, _, _, mc = _runtime(tmp_path)
        learner = ExperienceLearner(
            mc, evidence_validator=lambda _m, _e: True, allow_test_seam=True
        )
        assert learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id="ev-test",
        ) is not None
