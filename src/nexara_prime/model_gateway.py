from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .model_router import CircuitBreaker


class ProviderError(RuntimeError):
    """A provider failure that is safe to retry or route to a fallback."""

    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


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
    value = re.sub(r"(?i)(api[_-]?key|client[_-]?secret|secret[_-]?key|token|password)\s*[:=]\s*[^\s,]+", r"\1=[REDACTED]", value)
    return value


def estimate_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def _flat_provider_metadata(context_hash: str) -> dict[str, str]:
    """Return provider metadata that is valid for strict Chat Completions APIs."""
    return {"nexara_context_hash": context_hash} if context_hash else {}


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
    request_id: str = ""
    latency_ms: float = 0.0
    total_tokens: int = 0
    error_code: str | None = None
    retry_count: int = 0
    created_at: str = ""

    @property
    def assistant_content(self) -> str:
        return self.text


ProviderResult = ModelResponse


class ModelProvider(Protocol):
    name: str

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", timeout_seconds: float | None = None) -> ModelResponse:
        ...



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
    requires_request_id = True

    def __init__(self, endpoint: str, model: str, api_key: str | None = None, timeout_seconds: float = 20.0, max_output_tokens: int = 512):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max(1, max_output_tokens)

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
        payload = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": self.max_output_tokens}
        metadata = _flat_provider_metadata(context_hash)
        if metadata:
            payload["metadata"] = metadata
        headers = {"Content-Type": "application/json", "X-NEXARA-Trace-ID": trace_id}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.name != "local":
            raise ProviderUnavailable(f"{self.name}_api_key_not_configured")
        request = Request(f"{self.endpoint}/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout_seconds or self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                response_headers = getattr(response, "headers", {})
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderError(f"{self.name}_authentication_failed", code="authentication_failed", retryable=False) from exc
            if exc.code == 429:
                raise ProviderError(f"{self.name}_rate_limited", code="rate_limited", retryable=True) from exc
            raise ProviderError(f"{self.name}_request_failed:http_{exc.code}", code=f"http_{exc.code}", retryable=exc.code >= 500) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"{self.name}_request_failed:{type(exc).__name__}", code="transport_error", retryable=True) from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{self.name}_invalid_json", code="invalid_response", retryable=False) from exc
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name}_invalid_response_shape", code="invalid_response", retryable=False) from exc
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(f"{self.name}_empty_response", code="empty_response", retryable=False)
        usage = body.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", estimate_tokens(system + task + json.dumps(context or {}, sort_keys=True))))
        output_tokens = int(usage.get("completion_tokens", estimate_tokens(str(text))))
        request_id = str(
            body.get("id")
            or response_headers.get("x-request-id", "")
            or response_headers.get("request-id", "")
            or response_headers.get("x-deepseek-request-id", "")
        )
        request_id_source = "provider"
        if not request_id:
            request_id = f"nexara-client-{trace_id or int(started * 1_000_000)}"
            request_id_source = "client_generated"
        return ModelResponse(
            self.name, self.model, str(text), input_tokens, output_tokens, trace_id,
            float(body.get("cost_usd", 0.0)), str(body.get("choices", [{}])[0].get("finish_reason", "stop")),
            redact_secrets({"usage": usage, "context_hash": context_hash, "request_id_source": request_id_source}),
            request_id=request_id,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            total_tokens=int(usage.get("total_tokens", input_tokens + output_tokens)),
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class OpenAICompatibleProvider(_HTTPProvider):
    name = "openai_compatible"

    def __init__(self, endpoint: str, model: str = "gpt-4o-mini", api_key: str | None = None, timeout_seconds: float = 20.0, provider_name: str = "openai_compatible", max_output_tokens: int = 512):
        super().__init__(endpoint, model, api_key, timeout_seconds, max_output_tokens)
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
    def __init__(self, provider: ModelProvider | None = None, fallback: ModelProvider | None = None, *, max_attempts: int = 2, retry_delay_seconds: float = 0.02, breaker: "CircuitBreaker | None" = None):
        if provider is None:
            raise ValueError("ModelGateway requires a concrete provider; use UnavailableProvider instead of None")
        self.provider = provider
        self.fallback = fallback
        self.max_attempts = max(1, max_attempts)
        self.retry_delay_seconds = retry_delay_seconds
        self.breaker = breaker if breaker is not None else CircuitBreaker()
        self.last_usage: dict[str, Any] = {}

    def complete(self, system: str, task: str, context: dict[str, Any] | None = None, *, trace_id: str = "", budget_remaining: float | None = None) -> ModelResponse:
        last_error: Exception | None = None
        provider_name = getattr(self.provider, 'name', 'unknown')
        # ── Quota enforcement (Runtime Productization v1) ──
        if budget_remaining is not None and budget_remaining <= 0:
            raise ProviderUnavailable("budget_exhausted: remaining={:.6f}".format(budget_remaining))
        for attempt in range(1, self.max_attempts + 1):
            try:
                if self.breaker.is_open(provider_name):
                    raise ProviderUnavailable("provider_circuit_open")
                response = self.provider.complete(system, task, context, trace_id=trace_id)
                if getattr(self.provider, "requires_request_id", False) and not response.request_id:
                    raise ProviderError("provider_missing_request_id", code="invalid_response", retryable=False)
                response = ModelResponse(
                    **{**response.__dict__, "retry_count": attempt - 1,
                       "total_tokens": response.total_tokens or response.input_tokens + response.output_tokens}
                )
                self.breaker.record_success(provider_name)
                self.last_usage = {"provider": response.provider, "model": response.model, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "total_tokens": response.total_tokens, "cost_usd": response.cost_usd, "trace_id": trace_id, "request_id": response.request_id, "latency_ms": response.latency_ms, "finish_reason": response.finish_reason, "retry_count": response.retry_count}
                return response
            except (ProviderError, TimeoutError) as exc:
                last_error = exc
                self.breaker.record_failure(provider_name)
                if not getattr(exc, "retryable", True):
                    break
                if attempt < self.max_attempts:
                    time.sleep(self.retry_delay_seconds * attempt)
        if self.fallback:
            response = self.fallback.complete(system, task, context, trace_id=trace_id)
            self.last_usage = {"provider": response.provider, "model": response.model, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "total_tokens": response.total_tokens, "cost_usd": response.cost_usd, "trace_id": trace_id, "request_id": response.request_id, "latency_ms": response.latency_ms, "finish_reason": response.finish_reason, "retry_count": response.retry_count, "fallback": True}
            return response
        raise ProviderUnavailable(str(last_error or "provider_failed"))

    def generate_reply(self, conversation_id: str, messages: list[dict[str, Any]], system_context: str, runtime_context: dict[str, Any] | None = None, provider_policy: dict[str, Any] | None = None) -> ProviderResult:
        """Unified provider contract used by conversation callers."""
        del conversation_id, provider_policy
        task = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in messages)
        return self.complete(system_context, task, runtime_context, trace_id=str((runtime_context or {}).get("trace_id", "")))

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
