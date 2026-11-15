"""Fail-closed remote execution gate.

The factory may dispatch off this machine only when a remote target is both
configured and provably reachable. With no authorized remote, the honest
outcome of a Mac-offline window is zero progress: leases expire and are reaped
on return, and nothing pretends the local DSH is still running.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Callable, Mapping


class RemoteUnavailable(RuntimeError):
    """No authorized remote executor exists for off-machine work."""


@dataclass(frozen=True)
class RemoteTarget:
    host: str
    workspace: str
    label: str = "remote"


class RemoteGate:
    def __init__(
        self,
        target: RemoteTarget | None = None,
        prober: Callable[[RemoteTarget], bool] | None = None,
    ):
        self.target = target
        self._prober = prober or self._ssh_probe

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RemoteGate":
        values = os.environ if env is None else env
        raw = (values.get("NEXARA_FACTORY_REMOTE") or "").strip()
        if not raw:
            return cls()
        host, _, workspace = raw.partition(":")
        if not host or not workspace:
            return cls()
        return cls(RemoteTarget(host=host, workspace=workspace))

    @property
    def configured(self) -> bool:
        return self.target is not None

    def available(self) -> bool:
        if self.target is None:
            return False
        try:
            return bool(self._prober(self.target))
        except Exception:
            return False

    def require(self) -> RemoteTarget:
        if self.target is None:
            raise RemoteUnavailable(
                "no authorized remote executor: set NEXARA_FACTORY_REMOTE=host:/workspace"
            )
        if not self.available():
            raise RemoteUnavailable(f"remote unreachable: {self.target.host}")
        return self.target

    def policy(self) -> dict:
        return {
            "mode": "fail-closed",
            "configured": self.configured,
            "target": None if self.target is None else self.target.host,
            "offline_effect": "no progress; leases expire and are reaped on return",
        }

    @staticmethod
    def _ssh_probe(target: RemoteTarget) -> bool:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", target.host,
             f"test -d {target.workspace}"],
            capture_output=True,
            timeout=15,
        )
        return proc.returncode == 0
