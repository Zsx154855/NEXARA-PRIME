"""Conversation/Message API acceptance over the canonical runtime store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
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
    runtime = NexaraRuntime(settings)
    return TestClient(create_app(runtime))


def test_conversation_round_trip_order_and_restart_persistence(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    created = client.post("/api/conversations", json={"title": "第一次对话"})
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]

    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "你好，你是谁？", "idempotency_key": "first-turn"},
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["metadata"]["provider"] == "mock"
    assert [m["role"] for m in client.get(f"/api/conversations/{conversation_id}/messages").json()] == ["user", "assistant"]

    replay = client.post(
        f"/api/conversations/{conversation_id}/messages",
        headers={"Idempotency-Key": "first-turn"},
        json={"content": "你好，你是谁？"},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert len(client.get(f"/api/conversations/{conversation_id}/messages").json()) == 2

    restarted = make_client(tmp_path)
    loaded = restarted.get(f"/api/conversations/{conversation_id}")
    assert loaded.status_code == 200
    assert [item["role"] for item in loaded.json()["messages"]] == ["user", "assistant"]
    with sqlite3.connect(tmp_path / "runtime.db") as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            ("conversation_message_index",),
        ).fetchone() is not None


def test_idempotency_conflict_and_missing_conversation_errors(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    first = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "第一条", "idempotency_key": "same"},
    )
    assert first.status_code == 200
    conflict = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "不同内容", "idempotency_key": "same"},
    )
    assert conflict.status_code == 409
    assert client.get("/api/conversations/not-found").status_code == 404
    assert client.get("/api/conversations/not-found/messages").status_code == 404


def test_message_can_admit_mission_without_bypassing_approval(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "检查当前运行状态并给我报告", "execute_mission": True},
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["mission_id"]
    assert body["approval_required"] is True
    mission = client.get(f"/api/missions/{body['mission_id']}").json()
    assert mission["state"] == "Approval"


def test_unconfigured_provider_does_not_write_assistant_success(tmp_path: Path) -> None:
    client = make_client(tmp_path, mock=False)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "不得伪造回答", "idempotency_key": "no-provider"},
    )
    assert sent.status_code == 503
    messages = client.get(f"/api/conversations/{conversation_id}/messages").json()
    assert [item["role"] for item in messages] == ["user"]
