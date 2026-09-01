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


def test_conversation_agent_loop_executes_tools_and_answers(tmp_path: Path, monkeypatch) -> None:
    """对话（chat/auto）意图走工具循环：脚本化 provider 先请求工具再给最终答复。"""
    import json as _json

    from nexara_prime.model_gateway import ModelResponse

    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8870,
    )
    (tmp_path / "workspace").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace" / "HEALTH.md").write_text("runtime: ok\n", encoding="utf-8")

    runtime = NexaraRuntime(settings)
    calls = {"n": 0}

    def fake_complete(system, task, context=None, *, trace_id="", timeout_seconds=None):
        calls["n"] += 1
        if calls["n"] == 1:
            text = _json.dumps({"action": "tool", "tool": "file_read", "arguments": {"path": "HEALTH.md"}})
        else:
            text = _json.dumps({"action": "answer", "content": "自检完成：已读取 HEALTH.md。"})
        return ModelResponse(
            provider="mock", model="mock", text=text,
            input_tokens=1, output_tokens=1, request_id=f"req-{calls['n']}",
        )

    monkeypatch.setattr(runtime.models, "complete", fake_complete)
    client = TestClient(create_app(runtime))

    conversation_id = client.post("/api/conversations", json={"title": "工具循环"}).json()["conversation_id"]
    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "请读取 HEALTH.md 并汇报", "execution_mode": "auto", "idempotency_key": "agent-loop-1"},
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["assistant_message"]["content"] == "自检完成：已读取 HEALTH.md。"
    meta = body["assistant_message"]["metadata"]
    assert meta["tool_steps"] == 1
    assert meta["tools_used"] == ["file_read"]
    assert meta["request_id"] == "req-2"

    tools = client.get("/api/tools").json()
    conv_tools = [t for t in tools if str(t.get("mission_id", "")).startswith("conversation-")]
    assert len(conv_tools) == 1
    assert conv_tools[0]["tool_name"] == "file_read"
    assert conv_tools[0]["status"] == "completed"
    assert conv_tools[0]["result"]["content"] == "runtime: ok\n"


def test_conversation_agent_loop_synthesizes_when_steps_exhausted(tmp_path: Path, monkeypatch) -> None:
    """工具循环用尽仍无答复时，追加纯总结轮，不落库原始工具 JSON。"""
    import json as _json

    from nexara_prime.model_gateway import ModelResponse

    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8870,
    )
    (tmp_path / "workspace").mkdir(parents=True, exist_ok=True)

    runtime = NexaraRuntime(settings)
    calls = {"n": 0}

    def fake_complete(system, task, context=None, *, trace_id="", timeout_seconds=None):
        calls["n"] += 1
        if calls["n"] <= runtime.CONVERSATION_MAX_TOOL_STEPS:
            text = _json.dumps({"action": "tool", "tool": "file_read", "arguments": {"path": "."}})
        else:
            text = "总结：已完成局部检查，未能确认全部状态。"
        return ModelResponse(provider="mock", model="mock", text=text, input_tokens=1, output_tokens=1)

    monkeypatch.setattr(runtime.models, "complete", fake_complete)
    client = TestClient(create_app(runtime))

    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "全量自检", "execution_mode": "auto", "idempotency_key": "agent-loop-2"},
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    content = body["assistant_message"]["content"]
    assert content == "总结：已完成局部检查，未能确认全部状态。"
    assert "{" not in content
    assert body["assistant_message"]["metadata"]["tool_steps"] == runtime.CONVERSATION_MAX_TOOL_STEPS
