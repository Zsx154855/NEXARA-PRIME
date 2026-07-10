"""EnvironmentSecretStore — reads secrets from environment variables. Test/controlled-dev only."""
from __future__ import annotations

import os

from .base import SecretBackend


class EnvironmentSecretStore(SecretBackend):
    """Reads from env vars. Name is upper-cased and prefixed with NEXARA_SECRET_.
    Explicitly enabled only — never the default production backend."""

    def __init__(self, prefix: str = "NEXARA_SECRET_"):
        self._prefix = prefix
        self._writable: dict[str, str] = {}  # in-memory override for tests

    def _key(self, name: str) -> str:
        return f"{self._prefix}{name.upper().replace('-', '_').replace(' ', '_')}"

    def set(self, name: str, value: str) -> None:
        self._writable[name] = value

    def get(self, name: str) -> str:
        if name in self._writable:
            return self._writable[name]
        val = os.environ.get(self._key(name))
        if val is None:
            raise KeyError(f"Secret '{name}' not found in environment")
        return val

    def exists(self, name: str) -> bool:
        return name in self._writable or self._key(name) in os.environ

    def delete(self, name: str) -> None:
        self._writable.pop(name, None)

    def list_names(self) -> list[str]:
        names = list(self._writable.keys())
        for k, v in os.environ.items():
            if k.startswith(self._prefix):
                names.append(k[len(self._prefix):].lower().replace('_', '-'))
        return sorted(set(names))
