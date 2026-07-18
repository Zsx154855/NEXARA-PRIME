"""V2 Runtime — Real Stage Crash Recovery Tests.

LEGAL BOUNDARY CRASH PATTERN:
Monkeypatch _advance to raise KeyboardInterrupt (BaseException, not caught by
run_mission's except Exception) at a specific transition boundary. This leaves
the mission naturally in the pre-transition state with all artifacts persisted.
Then re-instantiate runtime from the same DB and call run_mission() — the stage
dispatcher routes to the correct stage processor with full idempotency.

IDEMPOTENCY TESTS:
Run mission to completion, re-instantiate, re-run → verify no duplicate artifacts.
These test the "restart after clean completion" scenario — a valid recovery path.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from nexara_prime.config import Settings
from nexara_prime.models import MissionState
from nexara_prime.runtime import NexaraRuntime


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


class TestVerificationCrashRecovery:
    """KeyboardInterrupt at Verification→Evidence boundary — state stays Verification naturally."""

    def test_crash_at_verification_boundary_recovers(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Verification crash")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)

        # Monkeypatch _advance: raise KeyboardInterrupt (BaseException, NOT caught
        # by except Exception) when transitioning Verification→Evidence.
        # This leaves evidence persisted (evidence.add + _save_mission happened
        # before _advance) but state stays Verification naturally.
        original_advance = rt1._advance
        crashed = {"count": 0}

        def crash_on_evidence_transition(m, target, actor):
            if target == MissionState.EVIDENCE and m.state == "Verification":
                crashed["count"] += 1
                raise KeyboardInterrupt("simulated crash at Evidence transition")
            return original_advance(m, target, actor)

        rt1._advance = crash_on_evidence_transition
        try:
            rt1.run_mission(mid)
        except KeyboardInterrupt:
            pass  # KeyboardInterrupt escapes except Exception — state stays Verification
        assert crashed["count"] == 1

        # State must be Verification (advance skipped), evidence persisted
        m2 = rt1.get_mission(mid)
        assert m2.state == "Verification", f"Expected Verification, got {m2.state}"
        vr_count_1 = sum(1 for e in rt1.evidence.list(mid) if e.get("kind") == "verification_report")
        assert vr_count_1 == 1, "Verification evidence should be persisted"
        sid = rt1.tools.list_invocations(mid)
        assert len(sid) == 2, f"Expected 2 tool invocations, got {len(sid)}"
        del rt1

        # Re-instantiate with same DB — stage dispatcher routes to _verify_stage
        rt2 = NexaraRuntime(_mk(db_dir))
        result = rt2.run_mission(mid)
        assert result.state == "Completed"

        # Idempotency: verification_report count stays 1 (ValueError caught on re-add)
        vr_count_2 = sum(1 for e in rt2.evidence.list(mid) if e.get("kind") == "verification_report")
        assert vr_count_2 == 1, f"Expected 1 verification_report, got {vr_count_2}"

        # Tool invocations still 2 (not duplicated)
        sid2 = rt2.tools.list_invocations(mid)
        assert len(sid2) == 2, f"Expected 2 tool invocations, got {len(sid2)}"


class TestIdempotencyAfterRestart:
    """Re-instantiate after full completion: re-run must NOT duplicate artifacts."""

    def test_evidence_idempotent_on_re_instantiation(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Evidence idempotent")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)
        rt1.run_mission(mid)
        er_before = sum(1 for e in rt1.evidence.list(mid) if e.get("kind") == "execution_result")
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        rt2.run_mission(mid)  # Completed → no-op
        er_after = sum(1 for e in rt2.evidence.list(mid) if e.get("kind") == "execution_result")
        assert er_after == er_before

    def test_memory_idempotent_on_re_instantiation(self) -> None:
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
        assert c2 == c1

    def test_evaluation_idempotent_on_re_instantiation(self) -> None:
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
        assert e2 == e1


class TestTokenPersistenceAcrossRestart:

    def test_token_data_survives_re_instantiation(self) -> None:
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
        model_key = f"{mid}:model_tokens"
        tokens = final.result.get(model_key)
        assert tokens is not None, "Token data missing"
        assert int(tokens.get("input_tokens", 0)) > 0, "Tokens not persisted"


class TestResumePreservesState:

    def test_resume_does_not_change_state(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        rt1 = NexaraRuntime(_mk(db_dir))
        m = rt1.create_mission("Resume test")
        mid = m.mission_id
        rt1.plan_mission(mid)
        rt1.approve_mission(mid, approved=True)
        rt1.run_mission(mid)
        before = rt1.get_mission(mid).state
        del rt1

        rt2 = NexaraRuntime(_mk(db_dir))
        rt2.resume(mid)
        after = rt2.get_mission(mid).state
        assert before == after, f"resume() changed state: {before} → {after}"


class TestProviderUnavailableResumable:

    def test_provider_unavailable_keeps_mission_resumable(self) -> None:
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
