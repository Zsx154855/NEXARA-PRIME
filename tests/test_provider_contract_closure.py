from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nexara_prime.config import Settings
from nexara_prime.model_gateway import (
    ModelGateway,
    ModelResponse,
    OpenAICompatibleProvider,
    ProviderError,
)
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.secrets.keychain import MacOSKeychainSecretStore


class _Response:
    headers = {"x-request-id": "req-test-001"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(
            {
                "id": "resp-test-001",
                "choices": [{"message": {"content": "真实测试回答"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
            }
        ).encode()


def test_real_adapter_returns_provider_contract_metadata() -> None:
    provider = OpenAICompatibleProvider("https://example.invalid/v1", model="deepseek-chat", api_key="secret-value", provider_name="deepseek", max_output_tokens=256)
    with patch("nexara_prime.model_gateway.urlopen", return_value=_Response()):
        result = provider.complete("system", "hello", trace_id="trace-1")
    assert result.provider == "deepseek"
    assert result.model == "deepseek-chat"
    assert result.assistant_content == "真实测试回答"
    assert result.request_id == "resp-test-001"
    assert result.latency_ms >= 0
    assert result.total_tokens == 7
    assert "secret-value" not in json.dumps(result.metadata, ensure_ascii=False)

    request = patch("nexara_prime.model_gateway.urlopen", return_value=_Response())
    with request as mocked_urlopen:
        provider.complete("system", "hello", trace_id="trace-2")
    payload = json.loads(mocked_urlopen.call_args.args[0].data.decode())
    assert payload["max_tokens"] == 256


def test_empty_or_missing_request_id_is_not_success() -> None:
    class EmptyResponse(_Response):
        headers = {}

        def read(self):
            return json.dumps({"choices": [{"message": {"content": ""}}]}).encode()

    provider = OpenAICompatibleProvider("https://example.invalid/v1", api_key="secret-value")
    with patch("nexara_prime.model_gateway.urlopen", return_value=EmptyResponse()), pytest.raises(ProviderError, match="empty_response"):
        provider.complete("system", "hello")


def test_non_retryable_auth_failure_does_not_retry() -> None:
    class FailingProvider:
        name = "deepseek"
        calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            raise ProviderError("authentication failed", code="authentication_failed", retryable=False)

    provider = FailingProvider()
    gateway = ModelGateway(provider, max_attempts=3, retry_delay_seconds=0)
    with pytest.raises(Exception, match="authentication failed"):
        gateway.complete("system", "hello")
    assert provider.calls == 1


def test_same_idempotency_key_retries_failed_provider_turn(tmp_path: Path) -> None:
    runtime = NexaraRuntime(Settings(tmp_path / "runtime.db", tmp_path / "workspace", tmp_path / "reports", "none", False, "127.0.0.1", 8871))
    conversation_id = runtime.conversations.create()["conversation_id"]

    class FailThenSucceed:
        name = "deepseek"
        model = "deepseek-chat"
        calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError("temporary", code="transport_error", retryable=False)
            return ModelResponse("deepseek", "deepseek-chat", "真实回答", 5, 2, request_id="req-2", latency_ms=12.5, total_tokens=7)

    provider = FailThenSucceed()
    runtime.models = ModelGateway(provider, max_attempts=1)
    with pytest.raises(ProviderError, match="temporary"):
        runtime.answer_conversation(conversation_id, "你好", idempotency_key="turn-1")
    result = runtime.answer_conversation(conversation_id, "你好", idempotency_key="turn-1")
    assert result["assistant_message"]["metadata"]["request_id"] == "req-2"
    attempts = runtime.conversations.provider_attempts(conversation_id, result["user_message"]["message_id"])
    assert [item["status"] for item in attempts] == ["failed", "succeeded"]


def test_keychain_error_does_not_include_secret_argument() -> None:
    failed = SimpleNamespace(returncode=1, stdout="", stderr="secret-value")
    with patch("nexara_prime.secrets.keychain.subprocess.run", return_value=failed), pytest.raises(RuntimeError) as error:
        MacOSKeychainSecretStore._run("/usr/bin/security", "add-generic-password", "-w", "secret-value")
    assert "secret-value" not in str(error.value)
