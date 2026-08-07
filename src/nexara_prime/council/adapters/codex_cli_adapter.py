"""NEXARA Council V2 — Codex CLI Adapter (H-CODE)

Independent CLI adapter for OpenAI Codex.
NOT treated as a Hermes provider — direct CLI invocation.
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


class CodexCLIAdapter(BaseAdapter):
    """Codex CLI adapter — independent, not a Hermes provider."""

    def __init__(self):
        super().__init__(
            adapter_id="codex-cli-adapter",
            seat="H-CODE",
            provider="codex",
            transport=TransportType.CLI,
        )

    @property
    def _env_key(self) -> str:
        return ""  # Codex uses CLI auth, not env

    @property
    def _keychain_service(self) -> str:
        return ""  # Codex uses CLI auth, not keychain

    def _resolve_credential(self) -> Optional[str]:
        # Codex CLI uses its own auth (OAuth device flow) — check if CLI is logged in
        codex_path = self._which("codex")
        if not codex_path:
            return None
        # Check if codex has valid auth by running a minimal command
        try:
            result = subprocess.run(
                [codex_path, "chat", "-q", "echo ready", "--max-turns", "1"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return "codex_cli_authenticated"  # Non-null sentinel
        except Exception:
            pass
        return None

    def _resolve_model(self) -> str:
        return "codex-cli-default"

    def _check_client(self) -> bool:
        return self._which("codex") is not None

    def discover(self) -> AdapterDiscovery:
        d = super().discover()
        codex_path = self._which("codex")
        if codex_path:
            d.cli_path = codex_path
            d.cli_version = self._cli_version(codex_path)
        return d

    def _do_invoke(self, prompt: str, max_tokens: int = 300) -> AdapterResponse:
        codex_path = self._which("codex")
        if not codex_path:
            return AdapterResponse.error_response(
                self.adapter_id, self.seat, "codex_cli_not_found",
                self.provider, self.transport,
            )

        request_id = f"req-{uuid.uuid4().hex[:12]}"
        try:
            # Codex one-shot: codex exec "prompt"
            result = subprocess.run(
                [codex_path, "exec", prompt],
                capture_output=True, text=True, timeout=120,
                env={**os.environ},
            )

            if result.returncode != 0:
                return AdapterResponse.error_response(
                    self.adapter_id, self.seat,
                    f"codex_cli_exit_{result.returncode}: {result.stderr[:200]}",
                    self.provider, self.transport,
                )

            content = result.stdout.strip()
            if not content:
                content = result.stderr.strip()

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
