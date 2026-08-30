"""Experience API V1.0 契约验收：信封、状态映射、分页。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8870,
    )
    return TestClient(create_app(NexaraRuntime(settings)))


def create_mission(client: TestClient, objective: str) -> dict:
    response = client.post("/api/missions", json={"objective": objective, "source_dir": None})
    assert response.status_code == 200, response.text
    return response.json()


def assert_envelope(body: dict) -> None:
    assert set(body) == {"success", "data", "error", "meta"}
    assert body["success"] is True
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_missions_envelope_and_contract_fields(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    snapshot = create_mission(client, "对接体验层演示任务")
    body = client.get("/v1/missions").json()
    assert_envelope(body)
    assert body["meta"]["total"] == 1 and body["meta"]["page"] == 1 and body["meta"]["limit"] == 20
    mission = body["data"][0]
    assert set(mission) == {"id", "title", "goal", "status", "progress", "nextStep", "subtasks", "updatedText"}
    assert mission["id"] == snapshot["mission_id"]
    assert mission["status"] in {"planning", "executing", "paused", "completed"}
    assert mission["goal"] == "对接体验层演示任务"
    for subtask in mission["subtasks"]:
        assert set(subtask) == {"id", "title", "done"}


def test_missions_empty_runtime_returns_empty_list(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = client.get("/v1/missions").json()
    assert_envelope(body)
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_missions_pagination(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for index in range(3):
        create_mission(client, f"分页演示任务 {index}")
    body = client.get("/v1/missions?page=2&limit=2").json()
    assert_envelope(body)
    assert body["meta"] == {"timestamp": body["meta"]["timestamp"], "total": 3, "page": 2, "limit": 2}
    assert len(body["data"]) == 1


def test_mission_state_mapping_table() -> None:
    from nexara_prime.experience_api import map_mission_state

    assert map_mission_state("Intent") == "planning"
    assert map_mission_state("AwaitingApproval") == "planning"
    assert map_mission_state("Execution") == "executing"
    assert map_mission_state("Running") == "executing"
    assert map_mission_state("Paused") == "paused"
    assert map_mission_state("Blocked") == "paused"
    assert map_mission_state("Completed") == "completed"
    assert map_mission_state("Failed") == "completed"
    assert map_mission_state("某个未知状态") == "planning"


def test_user_envelope_and_fields(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    create_mission(client, "用户面板演示任务")
    body = client.get("/v1/user").json()
    assert_envelope(body)
    user = body["data"]
    assert set(user) == {"name", "level", "daysCount", "goalsCompleted", "missionsActive", "quote"}
    assert user["missionsActive"] == 1
    assert user["goalsCompleted"] == 0
    assert user["daysCount"] >= 1


def test_session_envelope_and_fields(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = client.get("/v1/session").json()
    assert_envelope(body)
    session = body["data"]
    assert set(session) == {"id", "dateText", "greeting", "energyLevel", "suggestion", "highlights"}
    assert 0.0 <= session["energyLevel"] <= 1.0
    assert isinstance(session["highlights"], list) and session["highlights"]
    assert "月" in session["dateText"] and "星期" in session["dateText"]
    assert session["greeting"]
    assert session["suggestion"]


def test_days_since_first_record_handles_naive_and_bad_input() -> None:
    from datetime import datetime, timezone

    from nexara_prime.experience_api import days_since_first_record

    now = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    assert days_since_first_record([], now=now) == 1
    assert days_since_first_record([{"spec": {"created_at": "not-a-date"}}], now=now) == 1
    naive = [{"spec": {"created_at": "2026-08-30T12:00:00"}}]
    assert days_since_first_record(naive, now=now) == 2  # naive 被当作 UTC，不抛 TypeError
    aware = [{"spec": {"created_at": "2026-08-29T12:00:00+08:00"}}]
    assert days_since_first_record(aware, now=now) == 3


def test_memory_kind_mapping_table() -> None:
    from nexara_prime.experience_api import map_memory_kind

    assert map_memory_kind("experience") == "experience"
    assert map_memory_kind("failure_experience") == "experience"
    assert map_memory_kind("fact") == "knowledge"
    assert map_memory_kind("user_fact") == "knowledge"
    assert map_memory_kind("project_fact") == "knowledge"
    assert map_memory_kind("decision") == "knowledge"
    assert map_memory_kind("patch") == "knowledge"
    assert map_memory_kind("system_rule") == "knowledge"
    assert map_memory_kind("preference") == "relation"
    assert map_memory_kind("short_term") == "relation"
    assert map_memory_kind("temporary_context") == "relation"
    assert map_memory_kind("未知类别") == "knowledge"


def test_memories_envelope_and_fields(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = client.get("/v1/memories").json()
    assert_envelope(body)
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_conversations_role_mapping(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    created = client.post("/api/conversations", json={"title": "对接联调"}).json()
    client.post(
        f"/api/conversations/{created['conversation_id']}/messages",
        json={"content": "你好", "idempotency_key": "exp-1"},
    )
    body = client.get("/v1/conversations").json()
    assert_envelope(body)
    conversation = body["data"][0]
    assert set(conversation) == {"id", "title", "messages"}
    assert conversation["title"] == "对接联调"
    roles = [m["role"] for m in conversation["messages"]]
    assert roles == ["user", "nexara"]
    for message in conversation["messages"]:
        assert set(message) == {"id", "role", "text", "timeText"}


def test_token_usage_shape(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = client.get("/v1/token/usage").json()
    assert_envelope(body)
    token = body["data"]
    assert set(token) == {"todayUsed", "todayLimit"}
    assert token["todayLimit"] == 50000 and token["todayUsed"] >= 0


def test_system_status_shape(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = client.get("/v1/system/status").json()
    assert_envelope(body)
    status = body["data"]
    assert set(status) == {"runtimeVersion", "mode", "uptimeText", "components", "token"}
    assert status["runtimeVersion"].startswith("V")
    assert [c["id"] for c in status["components"]] == ["comp-1", "comp-2", "comp-3", "comp-4", "comp-5", "comp-6"]
    for component in status["components"]:
        assert set(component) == {"id", "name", "state", "detail"}
        assert component["state"] in {"normal", "busy", "paused", "warning"}
    assert set(status["token"]) == {"todayUsed", "todayLimit"}


def test_reserved_endpoints_return_null_data(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for path in ("/v1/agents", "/v1/evaluations"):
        body = client.get(path).json()
        assert_envelope(body)
        assert body["data"] is None
