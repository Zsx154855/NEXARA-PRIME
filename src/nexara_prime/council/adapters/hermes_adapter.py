"""NEXARA Council V2 — Hermes Executor Adapter (H-EXEC)

Hermes as execution adapter. Spawns Hermes subprocesses for task execution.
NOT used as a provider for other council seats.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from typing import Optional

from nexara_prime.council.adapters.base import BaseAdapter
from nexara_prime.council.adapters.schemas import (
    AdapterResponse, AdapterDiscovery,
    TransportType, UsageMode,
)


class HermesAdapter(BaseAdapter):
    """Hermes executor adapter — spawns real Hermes subprocesses."""

    def __init__(self):
        super().__init__(
            adapter_id="hermes-executor-adapter",
            seat="H-EXEC",
            provider="hermes",
            transport=TransportType.HERMES_WORKER,
        )

    @property
    def _env_key(self) -> str:
        return ""  # Hermes uses binary availability, not env

    @property
    def _keychain_service(self) -> str:
        return ""  # Hermes uses binary availability, not keychain

    def _resolve_credential(self) -> Optional[str]:
        hermes_path = self._which("hermes")
        if hermes_path:
            return "hermes_binary_available"
        return None

    def _resolve_model(self) -> str:
        # Read from active Hermes config
        try:
            r = subprocess.run(
                ["hermes", "config", "get", "model.default"],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip() if r.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _check_client(self) -> bool:
        return self._which("hermes") is not None

    def discover(self) -> AdapterDiscovery:
        d = super().discover()
        hermes_path = self._which("hermes")
        if hermes_path:
            d.cli_path = hermes_path
            d.cli_version = self._cli_version(hermes_path)
        return d

    def _do_invoke(self, prompt: str, max_tokens: int = 300) -> AdapterResponse:
        hermes_path = self._which("hermes")
        if not hermes_path:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, "hermes_not_found",
                self.provider, self.transport,
            )

        request_id = f"req-{uuid.uuid4().hex[:12]}"
        try:
            # Hermes one-shot: hermes chat -q "prompt" --quiet
            result = subprocess.run(
                [hermes_path, "chat", "-q", prompt, "--quiet"],
                capture_output=True, text=True, timeout=120,
                env={**os.environ},
            )

            if result.returncode != 0:
                return AdapterResponse.error_response(
                    self.adapter_id, self.seat,
                    f"hermes_exit_{result.returncode}: {result.stderr[:200]}",
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
                input_tokens=len(prompt) // 3,
                output_tokens=len(content) // 3,
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
