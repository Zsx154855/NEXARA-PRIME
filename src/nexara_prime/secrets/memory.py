"""InMemorySecretStore — ephemeral secret store for tests only."""
from __future__ import annotations

from .base import SecretBackend


class InMemorySecretStore(SecretBackend):
    """Stores secrets in a dict. Never persists. Test-only."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, name: str, value: str) -> None:
        self._store[name] = value

    def get(self, name: str) -> str:
        if name not in self._store:
            raise KeyError(f"Secret '{name}' not found")
        return self._store[name]

    def exists(self, name: str) -> bool:
        return name in self._store

    def delete(self, name: str) -> None:
        self._store.pop(name, None)

    def list_names(self) -> list[str]:
        return sorted(self._store.keys())
