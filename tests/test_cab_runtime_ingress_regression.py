"""Regression tests for Runtime execution ingress while CAB provenance remains open.

The fake Runtime never launches a model, tool, or process. It intentionally
presents a persisted-like mission at EXECUTION state without a verified
authorization or trusted host principal. A state label alone is not authority.
Keep the strict xfail until the real ingress contract is integrated and tested.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from nexara_prime.kernel_boundary import KernelBoundaryViolation
from nexara_prime.models import MissionState
from nexara_prime.runtime import NexaraRuntime


def _fake_runtime(state: str, *, safe_mode: bool = False):
    """Minimal duck-typed Runtime, so no DB/model/tool side effects can occur."""
    invocations: list[str] = []
    mission = SimpleNamespace(
        mission_id="untrusted-mission",
        state=state,
        paused=False,
        safe_mode=safe_mode,
        result={},
        created_at=datetime.now(timezone.utc).isoformat(),
        # Explicitly no approved contract, admission or verified principal.
        contract=None,
        pending_approval_id=None,
    )

    def _execute(_mission):
        invocations.append("execute")
        return _mission

    def _unreachable(_mission):
        invocations.append("unexpected")
        return _mission

    # Preserve Runtime's normal exception bookkeeping if a future guard
    # rejects inside a stage. Otherwise the fake would raise AttributeError
    # instead of the expected authorization exception.
    def _advance(_mission, target, _actor):
        _mission.state = target.value

    runtime = SimpleNamespace(
        _load_mission=lambda _mission_id: mission,
        _save_mission=lambda _mission: None,
        _advance=_advance,
        _execute_stage=_execute,
        _verify_stage=_unreachable,
        _commit_evidence_stage=_unreachable,
        _update_memory_stage=_unreachable,
        _evaluate_stage=_unreachable,
        settings=SimpleNamespace(max_execution_seconds=0),
    )
    return runtime, mission, invocations


def test_approval_stage_without_approval_does_not_dispatch():
    runtime, mission, calls = _fake_runtime(MissionState.APPROVAL.value)
    result = NexaraRuntime.run_mission(runtime, mission.mission_id)
    assert result is mission
    assert calls == []


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Open ingress gap: run_mission dispatches EXECUTION state without "
        "a trusted subject-bound kernel admission or persisted approval"
    ),
)
def test_execution_stage_without_trusted_admission_must_be_rejected():
    runtime, mission, calls = _fake_runtime(MissionState.EXECUTION.value)
    with pytest.raises((PermissionError, KernelBoundaryViolation)):
        NexaraRuntime.run_mission(runtime, mission.mission_id)
    assert calls == []


def test_safe_mode_approval_is_denied_without_dispatch():
    runtime, mission, calls = _fake_runtime(MissionState.APPROVAL.value, safe_mode=True)
    with pytest.raises(PermissionError, match="safe_mode_blocks_unapproved_mission"):
        NexaraRuntime.run_mission(runtime, mission.mission_id)
    assert calls == []
