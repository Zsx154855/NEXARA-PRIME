"""Experience Must Influence Decisions (M4 partial): verified recall -> action choice.

Real SQLite; no model calls. These tests prove the decision layer uses only
admitted (evidence-bound, receipt-consistent, active) experiences and returns
provenance. They do NOT prove business-level learning transfer.
"""

from __future__ import annotations

import json

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import ToolInvocation, new_id


def _runtime(tmp_path):
    brain = BrainDB(tmp_path / "decision-brain.db")
    core = SQLiteStore(tmp_path / "decision-core.db")
    evidence = EvidenceStore(core, EventBus(core))
    return brain, evidence, MemoryController(db=brain)


def _receipt(evidence, mission_id, tool_name, status="completed"):
    inv = ToolInvocation(
        mission_id=mission_id, tool_name=tool_name, status=status,
        result={"ok": status == "completed"}, trace_id=f"trace-{mission_id}",
    )
    return evidence.add(
        mission_id, "execution_receipt", f"Tool receipt: {tool_name}",
        inv.model_dump_json(), inv.trace_id,
        tool_invocation_id=inv.invocation_id,
        actor="tool_runtime", source="tool_runtime",
        verification_status="verified",
    )


def _record(learner, evidence, mission_id, tool_name, success, n=1):
    ids = []
    for _ in range(n):
        artifact = _receipt(
            evidence, mission_id, tool_name,
            status="completed" if success else "failed",
        )
        learner.record_outcome(
            mission_id, "success" if success else "failure", tool_name,
            "ok" if success else "failed", success,
            evidence_id=artifact.evidence_id,
        )
        ids.append(artifact.evidence_id)
    return ids


def _spread(learner, evidence, tool_name, success):
    for mission in ("mission-A", "mission-B"):
        _record(learner, evidence, mission, tool_name, success, n=1)


def _poisoned_row(mc, action, evidence_id):
    content = json.dumps({
        "mission_id": "mission-A", "outcome": "success", "action": action,
        "result": "ok", "success": True, "evidence_id": evidence_id,
    })
    mc.commit(
        mission_id="mission-A", key=f"exp:mission-A:{new_id('exp')}",
        content=content, kind="experience", evidence_id=evidence_id,
        confidence=0.5,
    )


class TestDecisionInfluence:
    def test_cold_start_returns_no_action(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        decision = learner.recommend_action("adapter")
        assert decision["action"] is None
        assert decision["based_on"] == 0
        assert decision["confidence"] == 0.0

    def test_verified_experiences_drive_recommendation(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        good_ids = []
        for mission in ("mission-A", "mission-B"):
            good_ids += _record(learner, evidence, mission, "python_adapter", True, n=1)
        _record(learner, evidence, "mission-A", "claude_adapter", False, n=2)

        decision = learner.recommend_action("adapter")
        assert decision["action"] == "python_adapter"
        assert decision["confidence"] == 1.0
        assert decision["based_on"] == 2
        assert decision["based_on_missions"] == 2
        assert set(decision["evidence_ids"]).issubset(set(good_ids))

    def test_decision_reuses_experience_for_unseen_task_keywords(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _spread(learner, evidence, "python_adapter", True)

        # No mission-scoped filter: an unseen caller query reuses verified lessons.
        decision = learner.recommend_action("adapter for a new mission")
        assert decision["action"] == "python_adapter"
        assert decision["based_on"] == 2

    def test_known_failing_action_is_not_recommended(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, evidence, "mission-A", "broken_adapter", False, n=2)
        _record(learner, evidence, "mission-B", "broken_adapter", False, n=1)

        decision = learner.recommend_action("adapter")
        assert decision["action"] is None
        assert decision.get("reason") == "low_success_rate"

    def test_single_sample_is_not_enough(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, evidence, "mission-A", "lucky_adapter", True, n=1)

        decision = learner.recommend_action("adapter")
        assert decision["action"] is None
        assert decision.get("reason") == "insufficient_evidence"

    def test_poisoned_rows_do_not_influence_decision(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _spread(learner, evidence, "python_adapter", True)
        for _ in range(5):
            _poisoned_row(mc, "evil_adapter", "ev-FORGED")

        decision = learner.recommend_action("adapter")
        assert decision["action"] == "python_adapter"

    def test_unrelated_query_does_not_recommend(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _spread(learner, evidence, "python_adapter", True)
        decision = learner.recommend_action("zzz quantum banana")
        assert decision["action"] is None
        assert decision["based_on"] == 0

    def test_falls_back_to_next_best_reliable_action(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, evidence, "mission-A", "broken_adapter", False, n=3)
        _spread(learner, evidence, "python_adapter", True)

        decision = learner.recommend_action("adapter")
        assert decision["action"] == "python_adapter"
        assert decision["confidence"] == 1.0

    def test_negative_decision_reports_zero_confidence(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, evidence, "mission-A", "broken_adapter", False, n=3)
        decision = learner.recommend_action("adapter")
        assert decision["action"] is None
        assert decision["confidence"] == 0.0


class TestRelevancePerRecord:
    def test_relevance_is_not_shared_across_rows(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, evidence, "mission-A", "report_tool", True, n=2)
        _record(learner, evidence, "mission-A", "other_tool", True, n=2)

        rows = mc.rank_retrieve(
            query="report", top_k=10, layers=["semantic"],
            min_confidence=0.1, record_access=False,
        )
        by_action = {json.loads(row["content"])["action"]: row for row in rows}
        assert by_action["report_tool"]["relevance"] > 0
        assert by_action["other_tool"]["relevance"] == 0

    def test_samples_from_one_mission_are_not_enough(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, evidence, "mission-A", "python_adapter", True, n=5)
        decision = learner.recommend_action("adapter")
        assert decision["action"] is None
        assert decision["reason"] == "insufficient_independent_missions"


class TestRetirement:
    def test_retired_mission_stops_influencing_decisions(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        _record(learner, evidence, "mission-A", "python_adapter", True, n=2)
        _record(learner, evidence, "mission-B", "python_adapter", True, n=2)
        assert learner.recommend_action("adapter")["based_on_missions"] == 2

        retired = learner.retire_experiences(mission_id="mission-A")
        assert retired == 2
        decision = learner.recommend_action("adapter")
        assert decision["action"] is None
        assert decision["reason"] == "insufficient_independent_missions"

    def test_retire_requires_a_selector(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        with pytest.raises(ValueError, match="retire_criteria_required"):
            learner.retire_experiences()

    def test_retired_lessons_are_not_returned(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        receipt = _receipt(evidence, "mission-A", "run_pytest")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        learner.record_lesson("mission-A", "retire me", receipt.evidence_id)
        assert learner.get_lessons("retire") == ["retire me"]
        learner.retire_experiences(mission_id="mission-A")
        assert learner.get_lessons("retire") == []
