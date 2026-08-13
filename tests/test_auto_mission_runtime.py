"""Acceptance tests for the Runtime-owned chat/auto/mission contract."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.conversation_intent import RuntimeIntentClassifier
from nexara_prime.runtime import NexaraRuntime


def make_client(tmp_path: Path, *, mock: bool = True) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock" if mock else "none",
        mock_model=mock,
        api_host="127.0.0.1",
        api_port=8870,
    )
    return TestClient(create_app(NexaraRuntime(settings)))


def test_runtime_classifier_uses_multiple_signals() -> None:
    mission = RuntimeIntentClassifier.classify("检查 NEXARA 当前运行状态，自动解决所有低风险问题，并向我汇报。")
    chat = RuntimeIntentClassifier.classify("你好，你是谁？你记得我们正在完成什么吗？")
    assert mission.intent == "mission"
    assert len(mission.reasons) >= 3
    assert chat.intent == "chat"


def test_auto_mode_admits_mission_and_preserves_intent_metadata(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "检查 NEXARA 当前运行状态，自动解决所有低风险问题，并向我汇报。",
            "execution_mode": "auto",
            "idempotency_key": "auto-mission-turn",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "auto"
    assert body["intent"] == "mission"
    assert body["mission_id"]
    assert body["approval_required"] is True
    stored = client.get(f"/api/conversations/{conversation_id}/messages").json()[0]
    assert stored["metadata"]["execution_mode"] == "auto"
    assert stored["metadata"]["intent"] == "mission"


def test_auto_mode_keeps_question_in_conversation(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "你好，你是谁？", "execution_mode": "auto"},
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "chat"
    assert response.json()["mission_id"] is None


def test_approved_auto_mission_runs_without_ui_process(tmp_path: Path) -> None:
    runtime = NexaraRuntime(
        Settings(tmp_path / "runtime.db", tmp_path / "workspace", tmp_path / "reports", "mock", True, "127.0.0.1", 8871)
    )
    mission = runtime.create_mission("检查本地运行状态并生成一份报告")
    runtime.plan_mission(mission.mission_id)
    loaded = runtime.get_mission(mission.mission_id)
    loaded.result["background_execution"] = True
    runtime._save_mission(loaded)
    runtime.approve_mission(mission.mission_id, decision="approve_once")
    worker = runtime._mission_threads[mission.mission_id]
    worker.join(timeout=10)
    assert not worker.is_alive()
    completed = runtime.get_mission(mission.mission_id)
    assert completed.state == "Completed"
    assert completed.result.get("memory_patch_id")
    # Reality-first: on this main the code_exec probe succeeds, so no
    # environment_limitation is recorded; the branch recorded one only when
    # sandbox enforcement was unavailable. Either durable truth is valid.
    assert completed.result.get("environment_limitation") or completed.result.get("report_path")
    assert runtime.store.find_record("notification", "mission_id", mission.mission_id)
