"""T12: a scrapeable metrics endpoint, with counts that reflect reality."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8901,
    )
    settings.ensure_dirs()
    return TestClient(create_app(NexaraRuntime(settings)))


def test_metrics_exposes_prometheus_text(tmp_path: Path):
    client = _client(tmp_path)
    client.post("/api/missions", json={"objective": "count me"})
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "nexara_http_requests_total" in body
    assert "nexara_missions" in body
    assert 'state="Intent"' in body or 'state="intent"' in body.lower()


def test_metrics_rejects_non_loopback_without_token(tmp_path: Path):
    client = TestClient(_client(tmp_path).app, client=("203.0.113.7", 50000))
    assert client.get("/metrics").status_code == 401
