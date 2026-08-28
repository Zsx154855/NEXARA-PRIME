"""Vision input protocol: complete(..., images=[...]) must thread through
provider → gateway → pool and produce OpenAI image_url content blocks."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from nexara_prime.model_gateway import (
    ModelGateway,
    ModelResponse,
    OpenAICompatibleProvider,
    ProviderUnavailable,
)
from nexara_prime.provider_pool import PoolChannel, ProviderPool


def _ok_response():
    class _Resp:
        headers = {}

        def read(self):
            return json.dumps({
                "id": "chatcmpl-test",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _Resp()


def _capture_payload(mocked_urlopen):
    return json.loads(mocked_urlopen.call_args.args[0].data.decode())


# ── HTTP provider ────────────────────────────────────────────────────────────


def test_http_provider_builds_image_url_content_blocks():
    provider = OpenAICompatibleProvider("https://example.invalid/v1", model="vision-model", api_key="k")
    with patch("nexara_prime.model_gateway.urlopen", return_value=_ok_response()) as mocked:
        provider.complete("sys", "describe this", images=["https://img.example/a.png", "data:image/png;base64,AAA"])
    payload = _capture_payload(mocked)
    user_msg = payload["messages"][1]
    assert user_msg["content"] == [
        {"type": "text", "text": "describe this"},
        {"type": "image_url", "image_url": {"url": "https://img.example/a.png"}},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
    ]


def test_http_provider_without_images_keeps_plain_text():
    provider = OpenAICompatibleProvider("https://example.invalid/v1", model="m", api_key="k")
    with patch("nexara_prime.model_gateway.urlopen", return_value=_ok_response()) as mocked:
        provider.complete("sys", "task")
    payload = _capture_payload(mocked)
    assert payload["messages"][1]["content"] == "task"


# ── Gateway passthrough ──────────────────────────────────────────────────────


def test_model_gateway_passes_images_through():
    received: dict = {}

    class _Spy:
        name = "spy"
        requires_request_id = False

        def complete(self, system, task, context=None, *, trace_id="", timeout_seconds=None, images=None):
            received["images"] = images
            return ModelResponse("spy", "m", "ok", 1, 1, trace_id, request_id="rid")

    gateway = ModelGateway(_Spy(), max_attempts=1)
    gateway.complete("sys", "task", images=["https://img.example/a.png"])
    assert received["images"] == ["https://img.example/a.png"]


# ── Pool passthrough ─────────────────────────────────────────────────────────


def test_provider_pool_passes_images_to_channel():
    received: dict = {}

    class _Fake:
        provider_name = "a"

        def complete(self, system, task, context=None, *, trace_id="", timeout_seconds=None, images=None):
            received["images"] = images
            return ModelResponse("a", "m", "ok", 1, 1, trace_id)

    pool = ProviderPool([PoolChannel("a", "https://a/v1", "m", supports_images=True)], providers={"a": _Fake()})
    pool.complete("sys", "task", images=["https://img.example/b.png"])
    assert received["images"] == ["https://img.example/b.png"]


# ── Unavailable provider tolerates the new kwarg ─────────────────────────────


def test_unavailable_provider_accepts_images_kwarg():
    from nexara_prime.model_gateway import UnavailableProvider

    with pytest.raises(ProviderUnavailable):
        UnavailableProvider().complete("s", "t", images=["https://img.example/x.png"])


def test_empty_system_message_is_omitted_from_payload():
    provider = OpenAICompatibleProvider("https://example.invalid/v1", model="m", api_key="k")
    with patch("nexara_prime.model_gateway.urlopen", return_value=_ok_response()) as mocked:
        provider.complete("", "task")
    payload = _capture_payload(mocked)
    roles = [m["role"] for m in payload["messages"]]
    assert roles == ["user"]


def test_reasoning_only_response_falls_back_to_reasoning_content():
    class _Resp:
        headers = {}

        def read(self):
            return json.dumps({
                "id": "chatcmpl-r",
                "choices": [{"message": {"content": "", "reasoning_content": "thinking result"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    provider = OpenAICompatibleProvider("https://example.invalid/v1", model="m", api_key="k")
    with patch("nexara_prime.model_gateway.urlopen", return_value=_Resp()):
        response = provider.complete("sys", "task")
    assert response.text == "thinking result"


# ── Anonymous channels (no API key required) ─────────────────────────────────


def test_anonymous_provider_without_key_sends_no_auth_header():
    provider = OpenAICompatibleProvider("https://example.invalid/v1", model="m", api_key=None, anonymous=True)
    with patch("nexara_prime.model_gateway.urlopen", return_value=_ok_response()) as mocked:
        provider.complete("sys", "task")
    headers = mocked.call_args.args[0].headers
    assert "Authorization" not in headers


def test_non_anonymous_provider_without_key_raises():
    provider = OpenAICompatibleProvider("https://example.invalid/v1", model="m", api_key=None)
    with pytest.raises(ProviderUnavailable):
        provider.complete("sys", "task")
