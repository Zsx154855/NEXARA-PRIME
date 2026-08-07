"""NEXARA Council V2 — Anthropic Adapter (H-ARCH)

Direct API adapter for Anthropic Claude models.
Uses httpx for API calls. Credentials from Keychain.
"""

from __future__ import annotations

import uuid

import httpx

from nexara_prime.council.adapters.base import BaseAdapter
from nexara_prime.council.adapters.schemas import (
    AdapterResponse, TransportType, UsageMode,
)


class AnthropicAdapter(BaseAdapter):
    """Direct Anthropic API adapter for Claude."""

    API_BASE = "https://api.anthropic.com/v1"

    def __init__(self):
        super().__init__(
            adapter_id="anthropic-adapter",
            seat="H-ARCH",
            provider="anthropic",
            transport=TransportType.API,
        )

    @property
    def _env_key(self) -> str:
        return "ANTHROPIC_API_KEY"

    @property
    def _keychain_service(self) -> str:
        return "anthropic_api_key"

    def _resolve_model(self) -> str:
        return "claude-sonnet-4-20250514"

    def _do_invoke(self, prompt: str, max_tokens: int = 300) -> AdapterResponse:
        api_key = self._resolve_credential()
        if not api_key:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, "no_credential",
                self.provider, self.transport,
            )

        request_id = f"req-{uuid.uuid4().hex[:12]}"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self.API_BASE}/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model_id,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = resp.json() if resp.status_code == 200 else {}

            if resp.status_code != 200:
                return AdapterResponse.error_response(
                    self.adapter_id, self.seat,
                    f"HTTP {resp.status_code}: {data.get('error', {}).get('message', str(data))}",
                    self.provider, self.transport,
                )

            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            usage = data.get("usage", {})

            response = AdapterResponse(
                adapter_id=self.adapter_id,
                seat=self.seat,
                transport=self.transport,
                provider=self.provider,
                model_id=self._model_id,
                request_id=request_id,
                schema_valid=True,
                simulated=False,
                usage_mode=UsageMode.EXACT,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                raw_response_preview=content[:200],
            )
            response.compute_response_hash(content)
            return response

        except httpx.TimeoutException:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, "timeout",
                self.provider, self.transport,
            )
        except Exception as e:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, str(e)[:200],
                self.provider, self.transport,
            )
