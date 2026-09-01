"""Conversation attachment acceptance: upload, reference, send, serve."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.attachments import MAX_ATTACHMENT_BYTES, classify_kind, sanitize_name
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
    runtime = NexaraRuntime(settings)
    return TestClient(create_app(runtime))


def test_classify_kind_and_sanitize_name() -> None:
    assert classify_kind("image/png") == "image"
    assert classify_kind("video/mp4") == "video"
    assert classify_kind("application/pdf") == "file"
    assert sanitize_name("../../etc/passwd") == "passwd"
    assert sanitize_name("报价 单 (v2).xlsx") == "报价_单_v2_.xlsx"
    assert sanitize_name("") == "attachment.bin"


def test_upload_list_and_content_round_trip(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]

    uploaded = client.post(
        f"/api/conversations/{conversation_id}/attachments",
        files={"file": ("notes.png", b"\x89PNG fake-bytes", "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    record = uploaded.json()
    assert record["kind"] == "image"
    assert record["media_type"] == "image/png"
    assert record["size"] == len(b"\x89PNG fake-bytes")
    assert record["content_hash"]

    listed = client.get(f"/api/conversations/{conversation_id}/attachments").json()
    assert [item["attachment_id"] for item in listed] == [record["attachment_id"]]

    content = client.get(
        f"/api/conversations/{conversation_id}/attachments/{record['attachment_id']}/content"
    )
    assert content.status_code == 200
    assert content.content == b"\x89PNG fake-bytes"
    assert content.headers["content-type"] == "image/png"


def test_send_message_with_attachment_persists_metadata(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    record = client.post(
        f"/api/conversations/{conversation_id}/attachments",
        files={"file": ("spec.pdf", b"%PDF-1.4 spec", "application/pdf")},
    ).json()

    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "看看这份规格",
            "execution_mode": "chat",
            "idempotency_key": "turn-with-attachment",
            "attachment_ids": [record["attachment_id"]],
        },
    )
    assert sent.status_code == 200, sent.text
    user_message = sent.json()["user_message"]
    attachments = user_message["metadata"]["attachments"]
    assert attachments[0]["attachment_id"] == record["attachment_id"]
    assert attachments[0]["kind"] == "file"

    replay = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "看看这份规格", "idempotency_key": "turn-with-attachment"},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True


def test_attachment_isolation_and_errors(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    first = client.post("/api/conversations", json={}).json()["conversation_id"]
    second = client.post("/api/conversations", json={}).json()["conversation_id"]
    record = client.post(
        f"/api/conversations/{first}/attachments",
        files={"file": ("a.txt", b"hello", "text/plain")},
    ).json()

    assert client.get(f"/api/conversations/{second}/attachments/{record['attachment_id']}/content").status_code == 404
    assert client.get(f"/api/conversations/{first}/attachments/attachment_missing/content").status_code == 404
    assert client.post("/api/conversations/not-found/attachments", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 404

    cross = client.post(
        f"/api/conversations/{second}/messages",
        json={"content": "借用别人的附件", "attachment_ids": [record["attachment_id"]]},
    )
    assert cross.status_code == 400

    missing = client.post(
        f"/api/conversations/{first}/messages",
        json={"content": "不存在的附件", "attachment_ids": ["attachment_missing"]},
    )
    assert missing.status_code == 400

    empty = client.post(
        f"/api/conversations/{first}/attachments",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert empty.status_code == 400


def test_upload_size_limit(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]
    oversized = client.post(
        f"/api/conversations/{conversation_id}/attachments",
        files={"file": ("big.bin", b"\x00" * (MAX_ATTACHMENT_BYTES + 1), "application/octet-stream")},
    )
    assert oversized.status_code == 400


def test_attachables_and_plugin_connection_refs(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    conversation_id = client.post("/api/conversations", json={}).json()["conversation_id"]

    attachables = client.get("/api/attachables").json()
    assert attachables["plugins"], "capability registry must expose plugins"
    plugin = attachables["plugins"][0]
    assert plugin["ref_id"] and plugin["name"]

    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "带上插件和连接",
            "execution_mode": "chat",
            "attachment_refs": [{"kind": "plugin", "ref_id": plugin["ref_id"], "name": plugin["name"]}],
        },
    )
    assert sent.status_code == 200, sent.text
    refs = sent.json()["user_message"]["metadata"]["attachments"]
    assert refs[0]["kind"] == "plugin"
    assert refs[0]["ref_id"] == plugin["ref_id"]

    if attachables["connections"]:
        connector = attachables["connections"][0]
        with_conn = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={
                "content": "带连接",
                "execution_mode": "chat",
                "attachment_refs": [{"kind": "connection", "ref_id": connector["connector_id"]}],
            },
        )
        assert with_conn.status_code == 200, with_conn.text
        conn_refs = with_conn.json()["user_message"]["metadata"]["attachments"]
        assert conn_refs[0]["kind"] == "connection"

    unknown = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "未知插件", "attachment_refs": [{"kind": "plugin", "ref_id": "skill.nope"}]},
    )
    assert unknown.status_code == 400

    bad_kind = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "非法类型", "attachment_refs": [{"kind": "wat", "ref_id": "x"}]},
    )
    assert bad_kind.status_code == 422
