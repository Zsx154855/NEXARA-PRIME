"""P0: repeated dispatch of the same Mission + receipt must not duplicate experience/evidence."""

from __future__ import annotations

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import ToolInvocation


def _runtime(tmp_path):
    brain = BrainDB(tmp_path / "idem-brain.db")
    core = SQLiteStore(tmp_path / "idem-core.db")
    evidence = EvidenceStore(core, EventBus(core))
    return brain, core, evidence, MemoryController(db=brain)


def _receipt(evidence, mission_id="mission-A", tool_name="run_pytest"):
    inv = ToolInvocation(
        mission_id=mission_id, tool_name=tool_name, status="completed",
        result={"ok": True}, trace_id=f"trace-{mission_id}",
    )
    return evidence.add(
        mission_id, "execution_receipt", "Tool receipt",
        inv.model_dump_json(), inv.trace_id,
        tool_invocation_id=inv.invocation_id,
        actor="tool_runtime", source="tool_runtime",
        verification_status="verified",
    )


def _experience_count(brain) -> int:
    with brain._lock:
        return brain._conn.execute(
            "SELECT COUNT(*) FROM brain_memories WHERE kind='experience'"
        ).fetchone()[0]


def _lesson_count(brain) -> int:
    with brain._lock:
        return brain._conn.execute(
            "SELECT COUNT(*) FROM brain_memories WHERE kind='lesson'"
        ).fetchone()[0]


class TestExperienceIdempotency:
    def test_duplicate_outcome_same_receipt_is_idempotent(self, tmp_path):
        brain, _, evidence, mc = _runtime(tmp_path)
        receipt = _receipt(evidence)
        learner = ExperienceLearner(mc, evidence_store=evidence)

        first = learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=receipt.evidence_id,
        )
        second = learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=receipt.evidence_id,
        )
        assert first == second
        assert _experience_count(brain) == 1

    def test_different_receipts_are_not_deduplicated(self, tmp_path):
        brain, _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        first = _receipt(evidence)
        second = _receipt(evidence)
        id_a = learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=first.evidence_id,
        )
        id_b = learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=second.evidence_id,
        )
        assert id_a != id_b
        assert _experience_count(brain) == 2

    def test_same_receipt_different_action_still_rejected(self, tmp_path):
        _, _, evidence, mc = _runtime(tmp_path)
        receipt = _receipt(evidence)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=receipt.evidence_id,
        )
        with pytest.raises(ValueError):
            learner.record_outcome(
                "mission-A", "success", "different_action", "ok", True,
                evidence_id=receipt.evidence_id,
            )


class TestLessonIdempotency:
    def test_duplicate_lesson_same_receipt_is_idempotent(self, tmp_path):
        brain, _, evidence, mc = _runtime(tmp_path)
        receipt = _receipt(evidence)
        learner = ExperienceLearner(mc, evidence_store=evidence)

        first = learner.record_lesson("mission-A", "always run tests", receipt.evidence_id)
        second = learner.record_lesson("mission-A", "always run tests", receipt.evidence_id)
        assert first == second
        assert _lesson_count(brain) == 1

    def test_different_lessons_same_receipt_are_distinct(self, tmp_path):
        brain, _, evidence, mc = _runtime(tmp_path)
        receipt = _receipt(evidence)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        first = learner.record_lesson("mission-A", "lesson one", receipt.evidence_id)
        second = learner.record_lesson("mission-A", "lesson two", receipt.evidence_id)
        assert first != second
        assert _lesson_count(brain) == 2


class TestEvidenceIdempotency:
    def test_same_idempotency_key_yields_one_evidence(self, tmp_path):
        _, core, evidence, _ = _runtime(tmp_path)
        content = ToolInvocation(
            mission_id="mission-A", tool_name="run_pytest", status="completed",
            result={"ok": True}, trace_id="trace",
        ).model_dump_json()
        first = evidence.add(
            "mission-A", "execution_receipt", "Tool receipt", content, "trace",
            actor="tool_runtime", source="tool_runtime",
            verification_status="verified", idempotency_key="dispatch-1",
        )
        second = evidence.add(
            "mission-A", "execution_receipt", "Tool receipt", content, "trace",
            actor="tool_runtime", source="tool_runtime",
            verification_status="verified", idempotency_key="dispatch-1",
        )
        assert first.evidence_id == second.evidence_id
        assert len(core.list_records("evidence", "mission-A")) == 1
