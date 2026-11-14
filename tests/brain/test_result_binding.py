"""P1: tool result digest must be bound to the trusted experience (no vacuous check)."""

from __future__ import annotations

import hashlib
import json

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import ToolInvocation, new_id, now_iso


def _runtime(tmp_path):
    brain = BrainDB(tmp_path / "bind-brain.db")
    core = SQLiteStore(tmp_path / "bind-core.db")
    evidence = EvidenceStore(core, EventBus(core))
    return brain, evidence, MemoryController(db=brain)


def _receipt(evidence, result=None):
    inv = ToolInvocation(
        mission_id="mission-A", tool_name="run_pytest", status="completed",
        result=result or {"ok": True, "rows": 3}, trace_id="trace",
    )
    return evidence.add(
        "mission-A", "execution_receipt", "Tool receipt",
        inv.model_dump_json(), inv.trace_id,
        tool_invocation_id=inv.invocation_id,
        actor="tool_runtime", source="tool_runtime",
        verification_status="verified",
    )


def _seed(mc, artifact, *, result_sha256=None):
    content = {
        "mission_id": "mission-A", "outcome": "success", "action": "run_pytest",
        "result": "ok", "success": True, "evidence_id": artifact.evidence_id,
        "evidence_sha256": artifact.sha256, "evidence_kind": "execution_receipt",
        "created_at": now_iso(),
    }
    if result_sha256 is not None:
        content["result_sha256"] = result_sha256
    mc.commit(
        mission_id="mission-A", key=f"exp:mission-A:{new_id('seed')}",
        content=json.dumps(content), kind="experience",
        evidence_id=artifact.evidence_id, confidence=0.5,
    )


class TestResultDigest:
    def test_result_digest_is_stored_and_recalled(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        artifact = _receipt(evidence)
        learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=artifact.evidence_id,
        )
        rows = mc._db.recall(mission_id="mission-A", kind="experience")
        assert json.loads(rows[0]["content"])["result_sha256"]
        assert len(learner.rank_experiences("run_pytest")) == 1

    def test_row_without_result_digest_is_excluded(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        artifact = _receipt(evidence)
        _seed(mc, artifact, result_sha256=None)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.rank_experiences("run_pytest") == []

    def test_row_with_wrong_result_digest_is_excluded(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        artifact = _receipt(evidence)
        _seed(mc, artifact, result_sha256="deadbeef")
        learner = ExperienceLearner(mc, evidence_store=evidence)
        assert learner.rank_experiences("run_pytest") == []

    def test_different_tool_results_produce_different_digests(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        learner = ExperienceLearner(mc, evidence_store=evidence)
        first = _receipt(evidence, result={"ok": True, "rows": 1})
        second = _receipt(evidence, result={"ok": True, "rows": 2})
        learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=first.evidence_id,
        )
        learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=second.evidence_id,
        )
        rows = mc._db.recall(mission_id="mission-A", kind="experience")
        digests = {json.loads(row["content"])["result_sha256"] for row in rows}
        assert len(digests) == 2
        for row in rows:
            receipt = json.loads(evidence.get_by_id(row["evidence_id"]).content)
            expected = hashlib.sha256(
                json.dumps(receipt["result"], sort_keys=True, default=str).encode()
            ).hexdigest()
            assert json.loads(row["content"])["result_sha256"] == expected

    def test_experience_receipt_path_still_works(self, tmp_path):
        _, evidence, mc = _runtime(tmp_path)
        content = json.dumps({
            "mission_id": "mission-A", "action": "run_pytest",
            "result": "ok", "success": True,
        })
        artifact = evidence.add(
            "mission-A", "experience_receipt", "receipt", content, "trace",
            actor="verification_engine", source="verification",
            verification_status="verified",
        )
        learner = ExperienceLearner(mc, evidence_store=evidence)
        learner.record_outcome(
            "mission-A", "success", "run_pytest", "ok", True,
            evidence_id=artifact.evidence_id,
        )
        assert len(learner.rank_experiences("run_pytest")) == 1
