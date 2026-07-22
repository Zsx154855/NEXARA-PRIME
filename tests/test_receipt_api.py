"""PR #20 Web Dashboard — Receipt endpoint tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8766,
    )
    settings.ensure_dirs()
    runtime = NexaraRuntime(settings)
    app = create_app(runtime)
    return TestClient(app)


@pytest.fixture
def runtime_with_mission(client: TestClient) -> TestClient:
    """Create a mission and return the client with active mission."""
    r = client.post("/api/missions", json={"objective": "receipt test mission"})
    assert r.status_code == 200
    mid = r.json()["mission_id"]
    client.post(f"/api/missions/{mid}/plan")
    client.post(f"/api/missions/{mid}/approve", json={"approved": True, "actor": "tester"})
    client.post(f"/api/missions/{mid}/run")
    return client


class TestReceiptEndpoint:
    def test_no_receipts_for_unknown_mission(self, client: TestClient) -> None:
        r = client.get("/api/receipts?mission_id=nonexistent")
        assert r.status_code == 200
        data = r.json()
        assert data.get("total_invocations", 0) == 0

    def test_receipts_for_mission(self, runtime_with_mission: TestClient) -> None:
        r = runtime_with_mission.get("/api/missions")
        assert r.status_code == 200
        missions = r.json()
        if not missions:
            pytest.skip("No missions created")
        mid = missions[0]["mission_id"]
        r = runtime_with_mission.get(f"/api/receipts?mission_id={mid}")
        assert r.status_code == 200
        data = r.json()
        assert "chain" in data
        assert "chain_intact" in data

    def test_receipts_all(self, runtime_with_mission: TestClient) -> None:
        r = runtime_with_mission.get("/api/receipts")
        assert r.status_code == 200
        data = r.json()
        assert "missions" in data
        assert isinstance(data["total"], int)

    def test_tools_for_mission(self, runtime_with_mission: TestClient) -> None:
        r = runtime_with_mission.get("/api/missions")
        assert r.status_code == 200
        mid = r.json()[0]["mission_id"]
        tools = runtime_with_mission.get(f"/api/missions/{mid}/tools")
        assert tools.status_code == 200
        data = tools.json()
        assert isinstance(data, list)
        assert any(item.get("tool_name") == "file_write_report" for item in data)

    def test_receipt_chain_fields(self, runtime_with_mission: TestClient) -> None:
        r = runtime_with_mission.get("/api/missions")
        missions = r.json()
        if not missions:
            pytest.skip("No missions")
        mid = missions[0]["mission_id"]
        r = runtime_with_mission.get(f"/api/receipts?mission_id={mid}")
        data = r.json()
        for item in data.get("chain", []):
            assert "invocation_id" in item
            assert "has_receipt" in item
            assert "receipt_verifiable" in item
