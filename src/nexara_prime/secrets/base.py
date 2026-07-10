"""Secret management abstraction — backends, store, and redaction."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import now_iso, new_id


@dataclass
class SecretReference:
    backend: str  # "keychain" | "environment" | "in_memory"
    path: str  # e.g. "nexara/provider/main"
    name_hint: str = ""


class SecretBackend(ABC):
    @abstractmethod
    def set(self, name: str, value: str) -> None: ...

    @abstractmethod
    def get(self, name: str) -> str: ...

    @abstractmethod
    def exists(self, name: str) -> bool: ...

    @abstractmethod
    def delete(self, name: str) -> None: ...

    @abstractmethod
    def list_names(self) -> list[str]: ...


class SecretStore:
    def __init__(self, backend: SecretBackend):
        self._backend = backend

    @property
    def backend_name(self) -> str:
        return type(self._backend).__name__

    def set(self, name: str, value: str) -> None:
        if not value or not name:
            raise ValueError("name and value required")
        self._backend.set(name, value)

    def get(self, name: str) -> str:
        return self._backend.get(name)

    def exists(self, name: str) -> bool:
        return self._backend.exists(name)

    def delete(self, name: str) -> None:
        self._backend.delete(name)

    def list_names(self) -> list[str]:
        return self._backend.list_names()


def redact_secrets(text: str) -> str:
    """Redact sensitive patterns (API keys, tokens, auth headers, passwords)
    from arbitrary text, replacing the matched secret value with a placeholder."""
    patterns = [
        (r"(?i)(sk-[A-Za-z0-9_-]{8,})", "[REDACTED_API_KEY]"),
        (r"(?i)(bearer\s+)[A-Za-z0-9_\-\.=]+", r"\1[REDACTED_TOKEN]"),
        (r"(?i)(authorization:\s*)[A-Za-z0-9_\-\.=]+", r"\1[REDACTED_AUTH]"),
        (r'(?i)(api_key\s*[=:]\s*)["\']?[^"\'\s,}]+', r"\1[REDACTED]"),
        (r'(?i)(password\s*[=:]\s*)["\']?[^"\'\s,}]+', r"\1[REDACTED]"),
        (r'(?i)(private_key\s*[=:]\s*)["\']?[^"\'\s,}]+', r"\1[REDACTED]"),
    ]
    for pat, repl in patterns:
        text = re.sub(pat, repl, text)
    return text
