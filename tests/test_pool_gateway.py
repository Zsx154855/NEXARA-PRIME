"""NEXARA pool gateway (OpenAI-compatible microservice) tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nexara_prime.model_gateway import ModelResponse, ProviderUnavailable
from nexara_prime.pool_gateway import create_app
from nexara_prime.provider_pool import PoolChannel, ProviderPool

GATEWAY_KEY = "sk-test-gateway"
AUTH = {"Authorization": f"Bearer {GATEWAY_KEY}"}


def _fake_pool():
    class _Fake:
        provider_name = "a"
        received: dict = {}

        def complete(self, system, task, context=None, *, trace_id="", timeout_seconds=None, images=None):
            self.received.update(system=system, task=task, images=images)
            return ModelResponse("a", "fake-model", "ok", 2, 1, trace_id)

    fake = _Fake()
    pool = ProviderPool([PoolChannel("a", "https://a/v1", "m", supports_images=True)], providers={"a": fake})
    return pool, fake


def _client(pool):
    app = create_app(pool, gateway_key=GATEWAY_KEY)
    return TestClient(app)


def test_chat_completions_requires_key():
    pool, _ = _fake_pool()
    client = _client(pool)
    resp = client.post("/v1/chat/completions", json={"model": "m", "messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 401


def test_chat_completions_routes_to_pool():
    pool, fake = _fake_pool()
    client = _client(pool)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]},
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "ok"
    assert fake.received["system"] == "sys"
    assert fake.received["task"] == "task"


def test_chat_completions_passes_images():
    pool, fake = _fake_pool()
    client = _client(pool)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "m",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image_url", "image_url": {"url": "https://img.example/a.png"}},
                    ],
                }
            ],
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert fake.received["images"] == ["https://img.example/a.png"]
    assert fake.received["task"] == "describe"


def test_models_lists_pool_channels():
    pool, _ = _fake_pool()
    client = _client(pool)
    resp = client.get("/v1/models", headers=AUTH)
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()["data"]]
    assert "m" in ids


def test_pool_exhaustion_returns_503():
    def _fail():
        raise ProviderUnavailable("all_pool_channels_unavailable:x:rate_limited")

    class _Dead:
        provider_name = "a"

        def complete(self, system, task, context=None, *, trace_id="", timeout_seconds=None, images=None):
            _fail()

    pool = ProviderPool([PoolChannel("a", "https://a/v1", "m")], providers={"a": _Dead()})
    client = _client(pool)
    resp = client.post(
        "/v1/chat/completions", json={"model": "m", "messages": [{"role": "user", "content": "hi"}]}, headers=AUTH
    )
    assert resp.status_code == 503
