"""T14: request logs must be one JSON object per line, with no secrets."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def _app(tmp_path: Path):
    settings = Settings(
        db_path=tmp_path / "runtime.db", workspace_root=tmp_path / "w", report_root=tmp_path / "r",
        model_provider="mock", mock_model=True, api_host="127.0.0.1", api_port=8903,
    )
    settings.ensure_dirs()
    return create_app(NexaraRuntime(settings))


def test_request_log_is_json_lines(tmp_path: Path, capsys):
    client = TestClient(_app(tmp_path))
    client.post("/api/missions", json={"objective": "log me"})

    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("{")]
    assert lines, "no structured log line emitted"
    record = json.loads(lines[-1])
    assert record["event"] == "http_request"
    assert record["path"] == "/api/missions"
    assert record["status"] == 200
    assert isinstance(record["duration_ms"], (int, float))
    assert "request_id" in record


def test_log_does_not_leak_authorization_header(tmp_path: Path, capsys):
    client = TestClient(_app(tmp_path))
    client.get("/api/runtime/overview", headers={"Authorization": "Bearer super-secret"})
    out = capsys.readouterr().out
    assert "super-secret" not in out
