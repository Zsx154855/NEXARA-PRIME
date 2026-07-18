"""Regression coverage for the eight PR #18 Codex review findings."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from nexara_prime.cli import cmd_doctor
from nexara_prime.config import Settings
from nexara_prime.models import MissionState, now_iso
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.sandbox_v2 import TestSandboxBackend as _ReviewSandboxBackend


@pytest.fixture(autouse=True)
def _test_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "nexara_prime.tools.MacOSSandboxBackend", _ReviewSandboxBackend
    )


def _settings(root: Path) -> Settings:
    settings = Settings(
        db_path=root / "runtime.db",
        workspace_root=root / "workspace",
        report_root=root / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    return settings


def _approved_runtime(root: Path) -> tuple[NexaraRuntime, str]:
    runtime = NexaraRuntime(_settings(root))
    mission = runtime.create_mission("PR18 review closure")
    runtime.plan_mission(mission.mission_id)
    runtime.approve_mission(mission.mission_id, approved=True)
    return runtime, mission.mission_id


def test_consumed_approval_replays_exact_report_claim_after_crash(
    tmp_path: Path,
) -> None:
    runtime, mission_id = _approved_runtime(tmp_path)
    original_save = runtime.store.save_record

    def crash_after_report_write(
        record_id, record_type, payload, created_at, mission_id_arg=None
    ):
        if record_type == "tool" and payload.get("tool_name") == "file_write_report":
            raise KeyboardInterrupt("crash after report side effect")
        return original_save(
            record_id, record_type, payload, created_at, mission_id_arg
        )

    runtime.store.save_record = crash_after_report_write
    with pytest.raises(KeyboardInterrupt):
        runtime.run_mission(mission_id)

    report_path = tmp_path / "reports" / mission_id / "mission-report.md"
    first_bytes = report_path.read_bytes()
    assert runtime.approvals.get(runtime.get_mission(mission_id).pending_approval_id).status.value == "consumed"

    recovered = NexaraRuntime(_settings(tmp_path))
    result = recovered.run_mission(mission_id)
    assert result.state == MissionState.COMPLETED.value
    assert report_path.read_bytes() == first_bytes
    report_tools = [
        item
        for item in recovered.tools.list_invocations(mission_id)
        if item.get("tool_name") == "file_write_report"
    ]
    assert len(report_tools) == 1
    assert report_tools[0]["result"]["replayed"] is True


def test_evaluation_and_idempotency_mapping_survive_event_crash(
    tmp_path: Path,
) -> None:
    runtime, mission_id = _approved_runtime(tmp_path)
    original_publish = runtime.evaluator.events.publish

    def crash_after_atomic_records(event_type, *args, **kwargs):
        if event_type == "mission.evaluated":
            raise KeyboardInterrupt("crash after evaluation records")
        return original_publish(event_type, *args, **kwargs)

    runtime.evaluator.events.publish = crash_after_atomic_records
    with pytest.raises(KeyboardInterrupt):
        runtime.run_mission(mission_id)
    assert len(runtime.evaluator.list(mission_id)) == 1
    assert len(runtime.store.list_records("evaluation_idempotency", mission_id)) == 1

    recovered = NexaraRuntime(_settings(tmp_path))
    assert recovered.run_mission(mission_id).state == MissionState.COMPLETED.value
    assert len(recovered.evaluator.list(mission_id)) == 1
    assert len(recovered.store.list_records("evaluation_idempotency", mission_id)) == 1
    evaluated_events = [
        event
        for event in recovered.store.list_events(mission_id)
        if event.get("event_type") == "mission.evaluated"
    ]
    assert len(evaluated_events) == 1


def test_legacy_model_response_is_migrated_before_provider_call(
    tmp_path: Path,
) -> None:
    runtime, mission_id = _approved_runtime(tmp_path)
    runtime.store.save_record(
        "model_legacy",
        "model_response",
        {
            "provider": "legacy-provider",
            "model": "legacy-model",
            "text": "legacy durable output",
            "input_tokens": 11,
            "output_tokens": 7,
            "cost_usd": 0.01,
            "trace_id": "legacy-trace",
            "idempotency_key": f"{mission_id}:model-completion",
        },
        now_iso(),
        mission_id,
    )

    def provider_must_not_run(*args, **kwargs):
        raise AssertionError("provider was called despite durable legacy response")

    runtime.models.complete = provider_must_not_run
    completed = runtime.run_mission(mission_id)
    assert completed.state == MissionState.COMPLETED.value
    persisted = runtime.get_mission(mission_id)
    assert persisted.result["model_text"] == "legacy durable output"
    assert persisted.result["model_provider"] == "legacy-provider"


def test_verification_replay_rejects_changed_report(tmp_path: Path) -> None:
    runtime, mission_id = _approved_runtime(tmp_path)
    original_advance = runtime._advance

    def crash_after_verification(mission, target, actor):
        if target == MissionState.EVIDENCE and mission.state == "Verification":
            raise KeyboardInterrupt("verification boundary")
        return original_advance(mission, target, actor)

    runtime._advance = crash_after_verification
    with pytest.raises(KeyboardInterrupt):
        runtime.run_mission(mission_id)
    report_path = Path(runtime.get_mission(mission_id).result["report_path"])
    report_path.write_text("tampered after verification", encoding="utf-8")

    recovered = NexaraRuntime(_settings(tmp_path))
    with pytest.raises(ValueError, match="verification_evidence_conflict"):
        recovered.run_mission(mission_id)
    verification = [
        item
        for item in recovered.evidence.list(mission_id)
        if item.get("kind") == "verification_report"
    ]
    assert len(verification) == 1


def test_successful_provider_clears_stale_unavailable_recovery(
    tmp_path: Path,
) -> None:
    runtime, mission_id = _approved_runtime(tmp_path)
    mission = runtime.get_mission(mission_id)
    mission.result["recovery"] = {
        "provider_unavailable": True,
        "retry_after_configured": True,
    }
    runtime._provider_unavailable = True
    runtime._save_mission(mission)

    assert runtime.run_mission(mission_id).state == MissionState.COMPLETED.value
    snapshot = runtime.inspect_mission(mission_id)
    assert snapshot["provider_unavailable"] is False
    assert "recovery" not in runtime.get_mission(mission_id).result


def test_doctor_scans_staged_python_files_for_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    (tmp_path / ".nexara").mkdir()
    (tmp_path / ".nexara" / "PROJECT_STATE.json").write_text("{}")
    for directory in ("docs", "src", "tests", "scripts/security"):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    scanner = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "security"
        / "scan_hardcoded_secrets.py"
    )
    shutil.copy2(scanner, tmp_path / "scripts/security/scan_hardcoded_secrets.py")
    secret_file = tmp_path / "src" / "credential.py"
    key_name = "_".join(("service", "api", "key"))
    secret_value = "-".join(("live", "credential", "123456"))
    secret_file.write_text(f'{key_name} = "{secret_value}"\n')
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "src/credential.py"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / ".venv"))

    assert cmd_doctor() == 1
    assert "src/credential.py" in capsys.readouterr().out


def test_new_mission_has_neutral_approval_status(tmp_path: Path) -> None:
    runtime = NexaraRuntime(_settings(tmp_path))
    mission = runtime.create_mission("No approval requested yet")
    snapshot = runtime.inspect_mission(mission.mission_id)
    assert snapshot["approval_status"] == "not_required"


def test_code_receipt_cannot_satisfy_report_receipt_status(tmp_path: Path) -> None:
    runtime = NexaraRuntime(_settings(tmp_path))
    mission = runtime.create_mission("Receipt binding")
    runtime.tools.invoke(
        mission.mission_id,
        "code_exec",
        {"code": "print('only code receipt')"},
        mission.trace_id,
        actor_id="runtime",
        idempotency_key=f"{mission.mission_id}:code-only",
    )
    assert runtime.inspect_mission(mission.mission_id)["receipt_status"] == "missing"

    runtime.plan_mission(mission.mission_id)
    runtime.approve_mission(mission.mission_id, approved=True)
    runtime.run_mission(mission.mission_id)
    assert runtime.inspect_mission(mission.mission_id)["receipt_status"] == "present"
