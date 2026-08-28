"""OpenAI-compatible microservice exposing a ProviderPool.

LiteLLM (or any OpenAI-SDK tool) points at this service; the pool fans out
to anonymous free-tier channels that must be called WITHOUT an
Authorization header (OVHcloud, Kilo, LLM7), which LiteLLM cannot do
directly.

Run::

    uvicorn nexara_prime.pool_gateway:app --host 127.0.0.1 --port 4001

Requires ``NEXARA_MODEL_POOL`` (see provider_pool.from_env) and
``NEXARA_POOL_GATEWAY_KEY`` (default ``sk-nexara-pool``) as the Bearer
token accepted by this service.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .model_gateway import ProviderUnavailable
from .provider_pool import ProviderPool

DEFAULT_GATEWAY_KEY = "sk-nexara-pool"


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: int | None = 512
    temperature: float | None = None
    stream: bool | None = False


def _require_key(authorization: str | None = Header(default=None)) -> str:
    gateway_key = os.getenv("NEXARA_POOL_GATEWAY_KEY", DEFAULT_GATEWAY_KEY)
    if authorization != f"Bearer {gateway_key}":
        raise HTTPException(status_code=401, detail="invalid_api_key")
    return gateway_key


def _flatten_messages(messages: list[ChatMessage]) -> tuple[str, str, list[str] | None]:
    """Extract (system, task, images) from OpenAI chat messages."""
    system = ""
    task = ""
    images: list[str] = []
    for message in messages:
        if message.role == "system":
            system += (str(message.content) + "\n") if isinstance(message.content, str) else ""
            continue
        if isinstance(message.content, str):
            task += message.content + "\n"
            continue
        if isinstance(message.content, list):
            for part in message.content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    task += str(part.get("text", "")) + "\n"
                elif part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url")
                    if url:
                        images.append(str(url))
    return system.strip(), task.strip(), images or None


def create_app(pool: ProviderPool, *, gateway_key: str) -> FastAPI:
    """Build the FastAPI app around an existing pool (test seam)."""
    app = FastAPI(title="nexara-pool-gateway")
    expected_auth = f"Bearer {gateway_key}"

    def _guard(authorization: str | None = Header(default=None)) -> None:
        if authorization != expected_auth:
            raise HTTPException(status_code=401, detail="invalid_api_key")

    @app.get("/v1/models")
    def list_models(_: None = Depends(_guard)) -> dict[str, Any]:
        return {
            "object": "list",
            "data": [{"id": channel.model, "object": "model", "owned_by": channel.name} for channel in pool.channels],
        }

    @app.post("/v1/chat/completions")
    def chat_completions(request: ChatRequest, _: None = Depends(_guard)) -> dict[str, Any]:
        system, task, images = _flatten_messages(request.messages)
        if not task:
            raise HTTPException(status_code=400, detail="empty_user_message")
        try:
            response = pool.complete(system, task, images=images)
        except ProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "id": response.request_id or f"pool-{response.trace_id}",
            "object": "chat.completion",
            "created": 0,
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response.text},
                    "finish_reason": response.finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": response.total_tokens or response.input_tokens + response.output_tokens,
            },
        }

    return app


def build_app_from_env() -> FastAPI:
    pool = ProviderPool.from_env()
    if pool is None:
        raise RuntimeError("NEXARA_MODEL_POOL is not set; cannot start pool gateway")
    return create_app(pool, gateway_key=os.getenv("NEXARA_POOL_GATEWAY_KEY", DEFAULT_GATEWAY_KEY))


# Import-safe module-level app: tests build apps via create_app(); uvicorn
# entrypoint requires NEXARA_MODEL_POOL in the environment (see
# scripts/start_pool_gateway.sh).
try:
    app = build_app_from_env()
except RuntimeError:
    app = None  # type: ignore[assignment]
