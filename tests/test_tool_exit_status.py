from __future__ import annotations

import pytest

from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def _runtime(tmp_path):
    settings = Settings(
        db_path=tmp_path / "runtime.db", workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports", model_provider="mock", mock_model=True,
        api_host="127.0.0.1", api_port=0,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


def test_nonzero_exit_marks_invocation_failed(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        with pytest.raises(RuntimeError):
            runtime.tools.invoke(
                "exit-status", "code_exec",
                {"code": "raise SystemExit(3)"}, "trace-nonzero",
                idempotency_key="nonzero-1",
            )
        invocations = runtime.tools.list_invocations("exit-status")
        assert len(invocations) == 1
        assert invocations[0]["status"] == "failed"
        assert invocations[0]["failure_code"] == "TOOL_EXECUTION_FAILED"
        assert invocations[0]["reason_code"] == "EXECUTION_FAILED"
        assert invocations[0]["result"]["returncode"] == 3
        assert invocations[0]["receipt_evidence_id"]
    finally:
        runtime.telemetry.stop()
        runtime.store.close()


def test_zero_exit_stays_completed(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        invocation = runtime.tools.invoke(
            "exit-status", "code_exec", {"code": "print(42)"}, "trace-zero",
            idempotency_key="zero-1",
        )
        assert invocation.status == "completed"
        assert invocation.result["returncode"] == 0
    finally:
        runtime.telemetry.stop()
        runtime.store.close()


def test_failed_invocation_replay_raises_without_duplicate(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        with pytest.raises(RuntimeError):
            runtime.tools.invoke(
                "exit-status", "code_exec",
                {"code": "raise SystemExit(3)"}, "trace-replay",
                idempotency_key="replay-failed-1",
            )
        with pytest.raises(RuntimeError, match="tool_replay_failed: TOOL_EXECUTION_FAILED"):
            runtime.tools.invoke(
                "exit-status", "code_exec",
                {"code": "raise SystemExit(3)"}, "trace-replay",
                idempotency_key="replay-failed-1",
            )
        assert len(runtime.tools.list_invocations("exit-status")) == 1
    finally:
        runtime.telemetry.stop()
        runtime.store.close()
