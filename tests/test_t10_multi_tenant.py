"""T10: in multi-tenant mode two accounts must not see each other's work."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def _app(tmp_path: Path):
    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8899,
        multi_tenant=True,
    )
    settings.ensure_dirs()
    return create_app(NexaraRuntime(settings))


def _signup(client: TestClient, email: str, password: str = "correct-horse-1"):
    response = client.post("/auth/signup", json={"email": email, "password": password})
    assert response.status_code in (200, 201), response.text
    return response


def test_unauthenticated_write_is_rejected(tmp_path: Path):
    client = TestClient(_app(tmp_path))
    assert client.get("/health").status_code == 200
    response = client.post("/api/missions", json={"objective": "no auth"})
    assert response.status_code == 401, response.text


def test_two_accounts_are_isolated(tmp_path: Path):
    app = _app(tmp_path)
    alice = TestClient(app)
    bob = TestClient(app)

    _signup(alice, "alice@example.com")
    _signup(bob, "bob@example.com")

    alice_login = alice.post("/auth/login", json={"email": "alice@example.com", "password": "correct-horse-1"})
    bob_login = bob.post("/auth/login", json={"email": "bob@example.com", "password": "correct-horse-1"})
    assert alice_login.status_code == 200 and bob_login.status_code == 200

    created = alice.post("/api/missions", json={"objective": "alice work"})
    assert created.status_code == 200, created.text
    mission_id = created.json()["mission_id"]

    assert [m["mission_id"] for m in alice.get("/api/missions").json()] == [mission_id]
    assert bob.get("/api/missions").json() == []
    assert bob.get(f"/api/missions/{mission_id}").status_code == 404


def test_wrong_password_is_rejected(tmp_path: Path):
    client = TestClient(_app(tmp_path))
    _signup(client, "carol@example.com")
    assert client.post("/auth/login", json={"email": "carol@example.com", "password": "wrong"}).status_code == 401


def test_only_owner_can_approve(tmp_path: Path):
    """A member of the same tenant must not be able to approve work."""
    app = _app(tmp_path)
    owner = TestClient(app)
    _signup(owner, "owner@example.com")
    owner.post("/auth/login", json={"email": "owner@example.com", "password": "correct-horse-1"})

    invited = owner.post("/auth/invite", json={"email": "member@example.com", "password": "correct-horse-1"})
    assert invited.status_code in (200, 201), invited.text

    member = TestClient(app)
    member.post("/auth/login", json={"email": "member@example.com", "password": "correct-horse-1"})

    created = owner.post("/api/missions", json={"objective": "needs approval"})
    mission_id = created.json()["mission_id"]
    assert owner.post(f"/api/missions/{mission_id}/plan", json={}).status_code == 200

    assert member.post(f"/api/missions/{mission_id}/approve", json={"approved": True}).status_code == 403
    assert owner.post(f"/api/missions/{mission_id}/approve", json={"approved": True}).status_code == 200


def test_invite_requires_owner(tmp_path: Path):
    app = _app(tmp_path)
    owner = TestClient(app)
    _signup(owner, "o2@example.com")
    owner.post("/auth/login", json={"email": "o2@example.com", "password": "correct-horse-1"})
    owner.post("/auth/invite", json={"email": "m2@example.com", "password": "correct-horse-1"})

    member = TestClient(app)
    member.post("/auth/login", json={"email": "m2@example.com", "password": "correct-horse-1"})
    assert member.post("/auth/invite", json={"email": "x@example.com", "password": "correct-horse-1"}).status_code == 403
