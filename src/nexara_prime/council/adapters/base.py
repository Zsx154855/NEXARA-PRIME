"""NEXARA Council V2 — Base Adapter

Abstract base class for all model adapters. Every adapter must implement:
- discover() — check availability
- invoke() — make a real call
- All output must be redacted for secrets before storage.
"""

from __future__ import annotations

import abc
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

from nexara_prime.council.adapters.schemas import (
    AdapterDiscovery, AdapterResponse, AdapterStatus, CanaryRequest,
    TransportType,
)
from nexara_prime.council.adapters.redaction import redact


class BaseAdapter(abc.ABC):
    """Abstract base for all model adapters."""

    def __init__(self, adapter_id: str, seat: str, provider: str,
                 transport: TransportType = TransportType.API):
        self.adapter_id = adapter_id
        self.seat = seat
        self.provider = provider
        self.transport = transport
        self._model_id: str = ""

    def _resolve_credential(self) -> Optional[str]:
        # 1. Try .env file (Hermes stores credentials here)
        import os
        env_files = [
            os.path.expanduser("~/.hermes/.env"),
        ]
        for env_file in env_files:
            try:
                if os.path.exists(env_file):
                    with open(env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("#"):
                                continue
                            if "=" in line:
                                key, _, val = line.partition("=")
                                if key.strip() == self._env_key:
                                    return val.strip().strip('"').strip("'")
            except Exception:
                pass
        # 2. Try Keychain
        return self._keychain_get(self._keychain_service)

    @property
    @abc.abstractmethod
    def _env_key(self) -> str:
        """Environment variable name for this provider."""
        ...

    @property
    @abc.abstractmethod
    def _keychain_service(self) -> str:
        """Keychain service name for this provider."""
        ...

    @abc.abstractmethod
    def _do_invoke(self, prompt: str, max_tokens: int = 300) -> AdapterResponse:
        """Execute the actual model call."""
        ...

    @abc.abstractmethod
    def _resolve_model(self) -> str:
        """Resolve model ID."""
        ...

    def discover(self) -> AdapterDiscovery:
        d = AdapterDiscovery(
            adapter_id=self.adapter_id, seat=self.seat,
            provider=self.provider, transport=self.transport,
        )
        try:
            cred = self._resolve_credential()
            d.credential_present = cred is not None and len(cred) > 0
            d.credential_source = self._credential_source()
        except Exception as e:
            d.status = AdapterStatus.AUTH_FAILED
            d.error_detail = redact(str(e))
            return d
        if not d.credential_present:
            d.status = AdapterStatus.AUTH_FAILED
            d.error_detail = "credential_not_found"
            return d
        d.client_found = self._check_client()
        try:
            d.model_resolved = self._resolve_model()
            self._model_id = d.model_resolved
        except Exception as e:
            d.status = AdapterStatus.ERROR
            d.error_detail = redact(str(e))
            return d
        d.status = AdapterStatus.READY
        return d

    def invoke(self, prompt: str, max_tokens: int = 300) -> AdapterResponse:
        t0 = time.monotonic()
        started = datetime.now(timezone.utc).isoformat()
        try:
            resp = self._do_invoke(prompt, max_tokens)
        except Exception as e:
            resp = AdapterResponse.error_response(
                self.adapter_id, self.seat, redact(str(e)),
                self.provider, self.transport,
            )
        resp.started_at = started
        resp.completed_at = datetime.now(timezone.utc).isoformat()
        resp.latency_ms = (time.monotonic() - t0) * 1000
        resp.adapter_id = self.adapter_id
        resp.seat = self.seat
        resp.transport = self.transport
        resp.provider = self.provider
        resp.model_id = self._model_id
        resp.backend_identity = f"{self.provider}:{self._model_id}"
        resp.raw_response_preview = redact(str(resp.raw_response_preview))
        return resp

    def canary(self, nonce: Optional[str] = None) -> AdapterResponse:
        req = CanaryRequest()
        if nonce:
            req.nonce = nonce
        return self.invoke(req.to_prompt(self.seat), max_tokens=100)

    def close(self) -> None:
        pass

    def _credential_source(self) -> str:
        return "keychain"

    def _check_client(self) -> bool:
        return True

    @staticmethod
    def _keychain_get(service: str, account: str = "agentos") -> Optional[str]:
        try:
            r = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _which(binary: str) -> Optional[str]:
        try:
            r = subprocess.run(["which", binary], capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None

    @staticmethod
    def _cli_version(binary: str) -> str:
        try:
            r = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10)
            return r.stdout.strip().split("\n")[0] if r.stdout else "UNKNOWN"
        except Exception:
            return "UNKNOWN"
