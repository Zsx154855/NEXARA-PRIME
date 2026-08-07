"""NEXARA Council V2 — xAI/Grok Adapter (H-RED)

Adapter for xAI Grok models. Uses grok CLI for invocation.
Credentials from Keychain.
"""

from __future__ import annotations

import subprocess
import uuid

from nexara_prime.council.adapters.base import BaseAdapter
from nexara_prime.council.adapters.schemas import (
    AdapterResponse, AdapterDiscovery,
    TransportType, UsageMode,
)


class XAIAdapter(BaseAdapter):
    """xAI Grok adapter via CLI + API."""

    def __init__(self):
        super().__init__(
            adapter_id="xai-adapter",
            seat="H-RED",
            provider="xai",
            transport=TransportType.CLI,
        )

    @property
    def _env_key(self) -> str:
        return "XAI_API_KEY"

    @property
    def _keychain_service(self) -> str:
        return "xai_api_key"

    def _resolve_model(self) -> str:
        return "grok-4.1-fast"

    def _check_client(self) -> bool:
        return self._which("grok") is not None

    def discover(self) -> AdapterDiscovery:
        d = super().discover()
        grok_path = self._which("grok")
        if grok_path:
            d.cli_path = grok_path
            d.cli_version = self._cli_version(grok_path)
        return d

    def _do_invoke(self, prompt: str, max_tokens: int = 300) -> AdapterResponse:
        grok_path = self._which("grok")
        if not grok_path:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, "grok_cli_not_found",
                self.provider, self.transport,
            )

        request_id = f"req-{uuid.uuid4().hex[:12]}"
        try:
            # Use grok CLI: grok chat -q "prompt"
            result = subprocess.run(
                [grok_path, "chat", "-q", prompt],
                capture_output=True, text=True, timeout=60,
                env={**__import__('os').environ},
            )

            if result.returncode != 0:
                return AdapterResponse.error_response(
                    self.adapter_id, self.seat,
                    f"grok_cli_exit_{result.returncode}: {result.stderr[:200]}",
                    self.provider, self.transport,
                )

            content = result.stdout.strip()

            response = AdapterResponse(
                adapter_id=self.adapter_id,
                seat=self.seat,
                transport=self.transport,
                provider=self.provider,
                model_id=self._model_id,
                request_id=request_id,
                schema_valid=True,
                simulated=False,
                usage_mode=UsageMode.ESTIMATED,
                input_tokens=len(prompt) // 4,
                output_tokens=len(content) // 4,
                raw_response_preview=content[:200],
            )
            response.compute_response_hash(content)
            return response

        except subprocess.TimeoutExpired:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, "timeout",
                self.provider, self.transport,
            )
        except Exception as e:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, str(e)[:200],
                self.provider, self.transport,
            )
