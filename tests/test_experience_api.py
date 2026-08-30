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
