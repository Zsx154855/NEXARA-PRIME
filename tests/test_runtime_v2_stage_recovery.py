"""V2 Runtime — Real Stage Crash Recovery (KeyboardInterrupt at 5 boundaries).

Each test monkeypatches _advance to raise KeyboardInterrupt (BaseException —
NOT caught by run_mission's except Exception) at a specific transition boundary.
The mission stays naturally in the pre-transition state with all artifacts
persisted. Then re-instantiate runtime from the same DB and call run_mission() —
the stage dispatcher routes to the correct stage with full idempotency.

Crash B: Tool write succeeded, evidence NOT committed. Simulates crash between
_execute_stage completion and VERIFICATION→EVIDENCE transition.

All tests: re-instantiation + run_mission → no duplicate side effects,
exactly 1 of each artifact.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.config import Settings
from nexara_prime.models import MissionState
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.sandbox_v2 import TestSandboxBackend as _StageSandboxBackend


@pytest.fixture(autouse=True)
def _use_stage_test_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise Runtime recovery independently of the host OS sandbox.

    OS sandbox enforcement has its own security suite. These tests need a
    deterministic executor on Linux and macOS so they can focus on persisted
    stage boundaries and idempotency.
    """
    monkeypatch.setattr("nexara_prime.tools.MacOSSandboxBackend", _StageSandboxBackend)


def _mk(db_dir: Path) -> Settings:
    s = Settings(
        db_path=db_dir / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock", mock_model=True,
        api_host="127.0.0.1", api_port=8765,
    )
    s.ensure_dirs()
    return s


class TestCrashAtExecutionToVerificationBoundary:
    """KeyboardInterrupt at Execution→Verification — tool write succeeded, state=Execution."""

    def test_crash_at_execution_boundary_recovers(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Crash Execution→Verification")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)
        orig = rt1._advance

        def crash_on_verify(mission, target, actor):
            if target == MissionState.VERIFICATION and mission.state == "Execution":
                raise KeyboardInterrupt("crash at Execution→Verification")
            return orig(mission, target, actor)

        rt1._advance = crash_on_verify
        try:
            rt1.run_mission(mid)
        except KeyboardInterrupt:
            pass
        rt1._advance = orig

        m2 = rt1.get_mission(mid)
        assert m2.state == "Execution", f"Expected Execution, got {m2.state}"
        t1 = len(rt1.tools.list_invocations(mid))
        assert t1 == 2, f"Expected 2 tool invocations, got {t1}"
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        result = rt2.run_mission(mid)
        assert result.state == "Completed"
        t2 = len(rt2.tools.list_invocations(mid))
        assert t2 == 2, f"Re-run duplicated tool invocations: {t1}→{t2}"


class TestCrashAtVerificationToEvidenceBoundary:
    """KeyboardInterrupt at Verification→Evidence — evidence persisted, state=Verification."""

    def test_crash_at_verification_boundary_recovers(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Crash Verification→Evidence")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)

        crashed = [False]
        orig = rt1._advance

        def crash_on_evidence(mission, target, actor):
            if target == MissionState.EVIDENCE and mission.state == "Verification":
                crashed[0] = True
                raise KeyboardInterrupt("crash at Verification→Evidence")
            return orig(mission, target, actor)

        rt1._advance = crash_on_evidence
        try:
            rt1.run_mission(mid)
        except KeyboardInterrupt:
            pass
        rt1._advance = orig
        assert crashed[0]

        m2 = rt1.get_mission(mid)
        assert m2.state == "Verification", f"Expected Verification, got {m2.state}"
        vr1 = sum(1 for e in rt1.evidence.list(mid) if e.get("kind") == "verification_report")
        assert vr1 == 1, "Verification evidence must be persisted"
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        result = rt2.run_mission(mid)
        assert result.state == "Completed"
        vr2 = sum(1 for e in rt2.evidence.list(mid) if e.get("kind") == "verification_report")
        assert vr2 == 1, f"Verification report duplicated: {vr1}→{vr2}"


class TestCrashAtEvidenceToMemoryPatchBoundary:
    """KeyboardInterrupt at Evidence→MemoryPatch — execution_result persisted, state=Evidence."""

    def test_crash_at_evidence_boundary_recovers(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Crash Evidence→MemoryPatch")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)

        crashed = [False]
        orig = rt1._advance

        def crash_on_memory(mission, target, actor):
            if target == MissionState.MEMORY_PATCH and mission.state == "Evidence":
                crashed[0] = True
                raise KeyboardInterrupt("crash at Evidence→MemoryPatch")
            return orig(mission, target, actor)

        rt1._advance = crash_on_memory
        try:
            rt1.run_mission(mid)
        except KeyboardInterrupt:
            pass
        rt1._advance = orig
        assert crashed[0]

        m2 = rt1.get_mission(mid)
        assert m2.state == "Evidence", f"Expected Evidence, got {m2.state}"
        er1 = sum(1 for e in rt1.evidence.list(mid) if e.get("kind") == "execution_result")
        assert er1 == 1, "Execution result evidence must be persisted"
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        result = rt2.run_mission(mid)
        assert result.state == "Completed"
        er2 = sum(1 for e in rt2.evidence.list(mid) if e.get("kind") == "execution_result")
        assert er2 == 1, f"Execution result duplicated: {er1}→{er2}"


class TestCrashAtMemoryPatchToEvaluationBoundary:
    """KeyboardInterrupt at MemoryPatch→Evaluation — memory patch persisted, state=MemoryPatch."""

    def test_crash_at_memory_boundary_recovers(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Crash MemoryPatch→Evaluation")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)

        crashed = [False]
        orig = rt1._advance

        def crash_on_eval(mission, target, actor):
            if target == MissionState.EVALUATION and mission.state == "MemoryPatch":
                crashed[0] = True
                raise KeyboardInterrupt("crash at MemoryPatch→Evaluation")
            return orig(mission, target, actor)

        rt1._advance = crash_on_eval
        try:
            rt1.run_mission(mid)
        except KeyboardInterrupt:
            pass
        rt1._advance = orig
        assert crashed[0]

        m2 = rt1.get_mission(mid)
        assert m2.state == "MemoryPatch", f"Expected MemoryPatch, got {m2.state}"
        c1 = len([x for x in rt1.memory.inspect(mid) if x.get("status") == "committed"])
        assert c1 == 1, "Memory patch must be committed"
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        result = rt2.run_mission(mid)
        assert result.state == "Completed"
        c2 = len([x for x in rt2.memory.inspect(mid) if x.get("status") == "committed"])
        assert c2 == 1, f"Memory patch duplicated: {c1}→{c2}"


class TestCrashAtEvaluationToCompletedBoundary:
    """KeyboardInterrupt at Evaluation→Completed — evaluation persisted, state=Evaluation."""

    def test_crash_at_evaluation_boundary_recovers(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Crash Evaluation→Completed")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)

        crashed = [False]
        orig = rt1._advance

        def crash_on_complete(mission, target, actor):
            if target == MissionState.COMPLETED and mission.state == "Evaluation":
                crashed[0] = True
                raise KeyboardInterrupt("crash at Evaluation→Completed")
            return orig(mission, target, actor)

        rt1._advance = crash_on_complete
        try:
            rt1.run_mission(mid)
        except KeyboardInterrupt:
            pass
        rt1._advance = orig
        assert crashed[0]

        m2 = rt1.get_mission(mid)
        assert m2.state == "Evaluation", f"Expected Evaluation, got {m2.state}"
        ev1 = len(rt1.evaluator.list(mid))
        assert ev1 == 1, "Evaluation must be persisted"
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        result = rt2.run_mission(mid)
        assert result.state == "Completed"
        ev2 = len(rt2.evaluator.list(mid))
        assert ev2 == 1, f"Evaluation duplicated: {ev1}→{ev2}"


class TestCrashBEvidenceNotCommitted:
    """Crash B: tool write succeeded (report file on disk), but evidence NOT committed.
    After re-instantiation, execution resumes without repeating tool side effects."""

    def test_tool_success_evidence_uncommitted(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Crash B — evidence not committed")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)

        original_advance = rt1._advance

        def crash_after_tool_success(mission, target, actor):
            if target == MissionState.VERIFICATION and mission.state == "Execution":
                raise KeyboardInterrupt("crash after tool success, before verification evidence")
            return original_advance(mission, target, actor)

        rt1._advance = crash_after_tool_success
        try:
            rt1.run_mission(mid)
        except KeyboardInterrupt:
            pass

        crashed = rt1.get_mission(mid)
        assert crashed.state == "Execution"
        report_path = crashed.result.get("report_path", "")
        assert report_path, "Report must be written"
        assert Path(report_path).exists(), f"Report file missing: {report_path}"

        evidence_before = rt1.evidence.list(mid)
        assert sum(1 for e in evidence_before if e.get("kind") == "verification_report") == 0
        assert sum(1 for e in evidence_before if e.get("kind") == "execution_result") == 0
        tool_count_before = len(rt1.tools.list_invocations(mid))
        assert tool_count_before == 2
        del rt1

        # Re-instantiate from the persisted Execution state. Stable tool keys
        # replay the completed calls, then the missing evidence stages run once.
        rt2 = NexaraRuntime(_mk(db_dir))
        result = rt2.run_mission(mid)
        assert result.state == "Completed"
        assert len(rt2.tools.list_invocations(mid)) == tool_count_before

        evidence_after = rt2.evidence.list(mid)
        assert sum(1 for e in evidence_after if e.get("kind") == "verification_report") == 1
        assert sum(1 for e in evidence_after if e.get("kind") == "execution_result") == 1


class TestIdempotencyAfterReInstantiation:
    """Re-instantiate after full completion: re-run must NOT duplicate artifacts."""

    def test_memory_idempotent(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Memory idempotent")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)
        rt1.run_mission(mid)
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        c1 = len([x for x in rt2.memory.inspect(mid) if x.get("status") == "committed"])
        rt2.run_mission(mid)
        c2 = len([x for x in rt2.memory.inspect(mid) if x.get("status") == "committed"])
        assert c2 == c1, f"Memory duplicated: {c1}→{c2}"

    def test_evaluation_idempotent(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Eval idempotent")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)
        rt1.run_mission(mid)
        e1 = len(rt1.evaluator.list(mid))
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        rt2.run_mission(mid)
        e2 = len(rt2.evaluator.list(mid))
        assert e2 == e1, f"Eval duplicated: {e1}→{e2}"


class TestTokenPersistenceAndResume:

    def test_token_data_survives(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Token survival")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)
        rt1.run_mission(mid)
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        final = rt2.get_mission(mid)
        tokens = final.result.get(f"{mid}:model_tokens")
        assert tokens is not None
        assert int(tokens.get("input_tokens", 0)) > 0

    def test_resume_does_not_change_state(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Resume test")
        rt1.plan_mission(m.mission_id)
        rt1.approve_mission(m.mission_id, approved=True)
        rt1.run_mission(m.mission_id)
        before = rt1.get_mission(m.mission_id).state
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        rt2.resume(m.mission_id)
        after = rt2.get_mission(m.mission_id).state
        assert before == after, f"resume() changed state: {before}→{after}"


class TestProviderUnavailable:

    def test_provider_unavailable_resumable(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        s = Settings(
            db_path=db_dir / "test.db",
            workspace_root=Path(tempfile.mkdtemp()),
            report_root=Path(tempfile.mkdtemp()),
            model_provider="none", mock_model=False,
            api_host="127.0.0.1", api_port=8765,
        )
        s.ensure_dirs()
        rt = NexaraRuntime(s)
        m = rt.create_mission("Provider unavailable")
        rt.plan_mission(m.mission_id)
        rt.approve_mission(m.mission_id, approved=True)
        from nexara_prime.model_gateway import ProviderUnavailable
        try:
            rt.run_mission(m.mission_id)
        except ProviderUnavailable:
            pass
        final = rt.get_mission(m.mission_id)
        assert final.state != "Failed", f"ProviderUnavailable should stay resumable, got {final.state}"
