"""NEXARA Council V2 — OpenAI Adapter (H-CHAIRMAN)

Direct API adapter for OpenAI ChatGPT models.
Uses httpx for API calls. Credentials from Keychain.
"""

from __future__ import annotations

import uuid

import httpx

from nexara_prime.council.adapters.base import BaseAdapter
from nexara_prime.council.adapters.schemas import (
    AdapterResponse, TransportType, UsageMode,
)


class OpenAIAdapter(BaseAdapter):
    """Direct OpenAI API adapter for ChatGPT."""

    API_BASE = "https://api.openai.com/v1"

    def __init__(self):
        super().__init__(
            adapter_id="openai-adapter",
            seat="H-CHAIRMAN",
            provider="openai",
            transport=TransportType.API,
        )

    @property
    def _env_key(self) -> str:
        return "OPENAI_API_KEY"

    @property
    def _keychain_service(self) -> str:
        return "openai_api_key"

    def _resolve_model(self) -> str:
        return "gpt-4o"

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
                    f"{self.API_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.3,
                    },
                )
                data = resp.json() if resp.status_code == 200 else {}

            if resp.status_code != 200:
                return AdapterResponse.error_response(
                    self.adapter_id, self.seat,
                    f"HTTP {resp.status_code}: {data.get('error', {}).get('message', str(data))}",
                    self.provider, self.transport,
                )

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
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
