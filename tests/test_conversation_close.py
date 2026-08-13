"""Conversation close/reopen acceptance — durable status contract.

PHASE 6 test matrix items 7-14: close persistence, close idempotency,
closed rejects message, closed rejects mission, reopen persistence,
reopen idempotency, reopened accepts message, full chain close/reload.
"""

from __future__ import annotations

import sqlite3
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


def test_close_persists_status_and_survives_restart(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    cid = client.post("/api/conversations", json={"title": "待关闭对话"}).json()["conversation_id"]
    closed = client.post(f"/api/conversations/{cid}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    restarted = make_client(tmp_path)
    loaded = restarted.get(f"/api/conversations/{cid}")
    assert loaded.status_code == 200
    assert loaded.json()["status"] == "closed"


def test_close_is_idempotent_without_duplicate_events(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    cid = client.post("/api/conversations", json={}).json()["conversation_id"]
    first = client.post(f"/api/conversations/{cid}/close")
    second = client.post(f"/api/conversations/{cid}/close")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "closed"
    with sqlite3.connect(tmp_path / "runtime.db") as db:
        count = db.execute(
            "SELECT COUNT(*) FROM events WHERE aggregate_id=? AND event_type='conversation.closed'",
            (cid,),
        ).fetchone()[0]
    assert count == 1


def test_closed_conversation_rejects_new_messages(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    cid = client.post("/api/conversations", json={}).json()["conversation_id"]
    client.post(f"/api/conversations/{cid}/close")
    sent = client.post(f"/api/conversations/{cid}/messages", json={"content": "关闭后不应接受"})
    assert sent.status_code == 400
    assert "conversation_closed" in str(sent.json()["detail"])


def test_closed_conversation_rejects_new_mission(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    cid = client.post("/api/conversations", json={}).json()["conversation_id"]
    client.post(f"/api/conversations/{cid}/close")
    sent = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "检查状态并生成报告", "execution_mode": "mission"},
    )
    assert sent.status_code == 400
    assert "conversation_closed" in str(sent.json()["detail"])
    assert client.get("/api/missions").json() == []


def test_reopen_persists_and_is_idempotent(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    cid = client.post("/api/conversations", json={}).json()["conversation_id"]
    client.post(f"/api/conversations/{cid}/close")
    reopened = client.post(f"/api/conversations/{cid}/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    again = client.post(f"/api/conversations/{cid}/reopen")
    assert again.status_code == 200
    assert again.json()["status"] == "open"
    with sqlite3.connect(tmp_path / "runtime.db") as db:
        count = db.execute(
            "SELECT COUNT(*) FROM events WHERE aggregate_id=? AND event_type='conversation.reopened'",
            (cid,),
        ).fetchone()[0]
    assert count == 1


def test_reopened_conversation_accepts_message_and_history_is_preserved(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    cid = client.post("/api/conversations", json={}).json()["conversation_id"]
    first = client.post(f"/api/conversations/{cid}/messages", json={"content": "关闭前的问题"})
    assert first.status_code == 200
    client.post(f"/api/conversations/{cid}/close")
    client.post(f"/api/conversations/{cid}/reopen")
    after = client.post(f"/api/conversations/{cid}/messages", json={"content": "重新打开后的问题"})
    assert after.status_code == 200
    messages = client.get(f"/api/conversations/{cid}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


def test_full_conversation_mission_response_close_reload(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    cid = client.post("/api/conversations", json={"title": "全链路"}).json()["conversation_id"]
    sent = client.post(
        f"/api/conversations/{cid}/messages",
        json={"content": "检查当前运行状态并给我报告", "execution_mode": "auto"},
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["intent"] == "mission"
    assert body["mission_id"]
    assert body["approval_required"] is True
    closed = client.post(f"/api/conversations/{cid}/close")
    assert closed.status_code == 200
    restarted = make_client(tmp_path)
    loaded = restarted.get(f"/api/conversations/{cid}")
    assert loaded.status_code == 200
    assert loaded.json()["status"] == "closed"
    messages = loaded.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["metadata"]["mission_id"] == body["mission_id"]
    assert messages[1]["metadata"]["response_to"] == messages[0]["message_id"]
