from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    """A provider failure that is safe to retry or route to a fallback."""


class ProviderUnavailable(ProviderError):
    pass


def redact_secrets(value: Any) -> Any:
    """Redact common secret forms before persistence or telemetry."""
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if any(token in key.lower() for token in ("key", "token", "secret", "password", "authorization")) else redact_secrets(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(sk-[A-Za-z0-9_-]{8,})", "[REDACTED]", value)
    value = re.sub(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*[^\s,]+", r"\1=[REDACTED]", value)
    return value


def estimate_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


@dataclass(frozen=True)
class ModelResponse:
    provider: str
    model: str
    text: str
    input_tokens: int
    output_tokens: int
    trace_id: str = ""
    cost_usd: float = 0.0
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    name: str

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", timeout_seconds: float | None = None) -> ModelResponse:
        ...


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def before_call(self) -> None:
        if self.open:
            raise ProviderUnavailable("provider_circuit_open")

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


class MockProvider:
    name = "mock"

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", timeout_seconds: float | None = None) -> ModelResponse:
        del timeout_seconds
        context = context or {}
        summary = redact_secrets(task.strip().replace("\n", " ")[:240])
        text = (
            "DETERMINISTIC_MOCK_RESULT\n"
            f"Objective: {summary}\n"
            f"Context keys: {', '.join(sorted(context)) or 'none'}\n"
            "Decision: produce a bounded local report, preserve evidence, and require human approval for the write."
        )
        input_tokens = estimate_tokens(system + task)
        output_tokens = estimate_tokens(text)
        return ModelResponse(self.name, "mock-v1", text, input_tokens, output_tokens, trace_id, 0.0, metadata={"deterministic": True})


class UnavailableProvider:
    """Provider that raises on every call — used when no real provider is configured.
    This ensures missions cannot silently complete with fake results."""

    name = "unavailable"

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", timeout_seconds: float | None = None) -> ModelResponse:
        raise ProviderUnavailable("no_provider_configured: set NEXARA_MODEL_PROVIDER or enable mock_model for testing")


class _HTTPProvider:
    name = "http"

    def __init__(self, endpoint: str, model: str, api_key: str | None = None, timeout_seconds: float = 20.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _complete_http(self, system: str, task: str, context: dict[str, Any] | None, trace_id: str, timeout_seconds: float | None) -> ModelResponse:
        if not self.endpoint:
            raise ProviderUnavailable(f"{self.name}_endpoint_not_configured")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
        context_hash = str((context or {}).get("context_hash", ""))
        if context:
            model_visible_context = {
                "context_hash": context_hash,
                "repository": context.get("repository"),
                "branch": context.get("branch"),
                "head_sha": context.get("head_sha"),
                "dirty": context.get("dirty"),
                "files": context.get("files", []),
                "excerpts": context.get("excerpts", []),
            }
            messages.append({
                "role": "user",
                "content": "NEXARA bounded repository context:\n"
                + json.dumps(redact_secrets(model_visible_context), ensure_ascii=False, sort_keys=True),
            })
        payload = {"model": self.model, "messages": messages, "temperature": 0}
        if context:
            payload["metadata"] = redact_secrets(context)
            if context_hash:
                payload["metadata"]["nexara_context_hash"] = context_hash
        headers = {"Content-Type": "application/json", "X-NEXARA-Trace-ID": trace_id}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.name != "local":
            raise ProviderUnavailable(f"{self.name}_api_key_not_configured")
        request = Request(f"{self.endpoint}/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds or self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{self.name}_request_failed:{type(exc).__name__}") from exc
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name}_invalid_response_shape") from exc
        usage = body.get("usage", {})
        return ModelResponse(
            self.name, self.model, str(text), int(usage.get("prompt_tokens", estimate_tokens(system + task + json.dumps(context or {}, sort_keys=True)))),
            int(usage.get("completion_tokens", estimate_tokens(str(text)))), trace_id,
            float(body.get("cost_usd", 0.0)), metadata=redact_secrets({"usage": usage, "context_hash": context_hash}),
        )


class OpenAICompatibleProvider(_HTTPProvider):
    name = "openai_compatible"

    def __init__(self, endpoint: str, model: str = "gpt-4o-mini", api_key: str | None = None, timeout_seconds: float = 20.0, provider_name: str = "openai_compatible"):
        super().__init__(endpoint, model, api_key, timeout_seconds)
        self.name = provider_name

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", timeout_seconds: float | None = None) -> ModelResponse:
        return self._complete_http(system, task, context, trace_id, timeout_seconds)


class LocalModelProvider(_HTTPProvider):
    name = "local"

    def __init__(self, endpoint: str | None = None, model: str = "local-model", timeout_seconds: float = 30.0):
        super().__init__(endpoint or "", model, None, timeout_seconds)

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", timeout_seconds: float | None = None) -> ModelResponse:
        return self._complete_http(system, task, context, trace_id, timeout_seconds)


class FallbackProvider:
    name = "fallback"

    def __init__(self, providers: list[ModelProvider]):
        if not providers:
            raise ValueError("fallback_requires_provider")
        self.providers = providers
        self.last_attempts: list[str] = []

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", timeout_seconds: float | None = None) -> ModelResponse:
        self.last_attempts = []
        errors: list[str] = []
        for provider in self.providers:
            self.last_attempts.append(provider.name)
            try:
                return provider.complete(system, task, context, trace_id=trace_id, timeout_seconds=timeout_seconds)
            except (ProviderError, TimeoutError) as exc:
                errors.append(f"{provider.name}:{exc}")
        raise ProviderUnavailable("all_providers_failed:" + "|".join(errors))


class ModelGateway:
    def __init__(self, provider: ModelProvider | None = None, fallback: ModelProvider | None = None, *, max_attempts: int = 2, retry_delay_seconds: float = 0.02):
        if provider is None:
            raise ValueError("ModelGateway requires a concrete provider; use UnavailableProvider instead of None")
        self.provider = provider
        self.fallback = fallback
        self.max_attempts = max(1, max_attempts)
        self.retry_delay_seconds = retry_delay_seconds
        self.breaker = CircuitBreaker()
        self.last_usage: dict[str, Any] = {}

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "") -> ModelResponse:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self.breaker.before_call()
                response = self.provider.complete(system, task, context, trace_id=trace_id)
                self.breaker.success()
                self.last_usage = {"provider": response.provider, "model": response.model, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "cost_usd": response.cost_usd, "trace_id": trace_id}
                return response
            except (ProviderError, TimeoutError) as exc:
                last_error = exc
                self.breaker.failure()
                if attempt < self.max_attempts:
                    time.sleep(self.retry_delay_seconds * attempt)
        if self.fallback:
            response = self.fallback.complete(system, task, context, trace_id=trace_id)
            self.last_usage = {"provider": response.provider, "model": response.model, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "cost_usd": response.cost_usd, "trace_id": trace_id, "fallback": True}
            return response
        raise ProviderUnavailable(str(last_error or "provider_failed"))

    def complete_structured(self, system: str, task: str, required_fields: list[str], context: dict[str, Any] | None = None, *, trace_id: str = "") -> tuple[ModelResponse, dict[str, Any]]:
        response = self.complete(system, task, context, trace_id=trace_id)
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ProviderError("structured_output_not_json") from exc
        missing = [field for field in required_fields if field not in parsed]
        if missing:
            raise ProviderError("structured_output_missing:" + ",".join(missing))
        return response, parsed
