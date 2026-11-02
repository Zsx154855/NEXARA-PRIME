"""T3 acceptance: the control plane is local by default.

Three claims, each one an experiment:
  1. binding a non-loopback host without a token refuses to start
  2. with a token, API routes require it and /health stays anonymous
  3. on loopback without a token, the API keeps working (local single-owner)
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def make_runtime(tmp_path: Path, *, host: str = "127.0.0.1", token: str | None = None) -> NexaraRuntime:
    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host=host,
        api_port=8873,
        api_token=token,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


def test_non_loopback_without_token_refuses_to_start(tmp_path: Path):
    runtime = make_runtime(tmp_path, host="0.0.0.0", token=None)
    with pytest.raises(RuntimeError, match="NEXARA_API_TOKEN"):
        create_app(runtime)


def test_token_required_on_api_but_not_health(tmp_path: Path):
    runtime = make_runtime(tmp_path, token="s3cret")
    client = TestClient(create_app(runtime))

    assert client.get("/health").status_code == 200
    assert client.get("/api/runtime/overview").status_code == 401
    assert client.get("/api/runtime/overview",
                     headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/runtime/overview",
                      headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_loopback_without_token_still_works(tmp_path: Path):
    runtime = make_runtime(tmp_path)
    client = TestClient(create_app(runtime))
    assert client.get("/api/runtime/overview").status_code == 200
