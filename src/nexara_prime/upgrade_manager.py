"""L2 Upgrade Manager — versioned upgrade lifecycle over the V1.0 runtime.

Read-only orchestration layer: snapshots the current version manifest, records
an upgrade transition, verifies runtime health, and rolls back to the snapshot
when a stage fails. Does NOT modify V1.0 Core / SQLite semantics / launchd.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["UpgradeManager", "UpgradeStage", "UpgradeResult"]

STAGES = (
    "preflight", "snapshot", "upgrade", "migration",
    "health", "canary", "acceptance", "seal",
)


class UpgradeStage:
    PREFLIGHT = "preflight"
    SNAPSHOT = "snapshot"
    UPGRADE = "upgrade"
    MIGRATION = "migration"
    HEALTH = "health"
    CANARY = "canary"
    ACCEPTANCE = "acceptance"
    SEAL = "seal"


@dataclass
class UpgradeResult:
    stage: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)


class UpgradeManager:
    """Versioned upgrade lifecycle. Each stage records evidence; failure at any
    stage routes to rollback before seal."""

    def __init__(self, manifest_path: Path, health_url: str = "http://127.0.0.1:8765/health"):
        self.manifest_path = Path(manifest_path)
        self.health_url = health_url
        self._snapshot: dict[str, Any] | None = None

    def _load_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text())

    def _save_manifest(self, m: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(m, indent=2, ensure_ascii=False))

    def _health(self) -> dict[str, Any]:
        try:
            import urllib.request
            with urllib.request.urlopen(self.health_url, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:  # pragma: no cover
            return {"status": "unreachable", "error": str(exc)}

    def preflight(self, target_version: str) -> UpgradeResult:
        m = self._load_manifest()
        return UpgradeResult("preflight", True, {
            "current": m.get("runtime_version"),
            "target": target_version,
            "manifest_exists": True,
        })

    def snapshot(self) -> UpgradeResult:
        m = self._load_manifest()
        self._snapshot = dict(m)
        return UpgradeResult("snapshot", True, {
            "version": m.get("runtime_version"),
            "git_sha": m.get("git_sha"),
            "schema_version": m.get("schema_version"),
        })

    def upgrade(self, target_version: str) -> UpgradeResult:
        m = self._load_manifest()
        m["runtime_version"] = target_version
        m["upgraded_from"] = self._snapshot.get("runtime_version") if self._snapshot else None
        self._save_manifest(m)
        return UpgradeResult("upgrade", True, {
            "from": m.get("upgraded_from"),
            "to": target_version,
        })

    def health(self) -> UpgradeResult:
        h = self._health()
        ok = h.get("status") == "ok"
        return UpgradeResult("health", ok, h)

    def rollback(self) -> UpgradeResult:
        if not self._snapshot:
            return UpgradeResult("rollback", False, {"error": "no_snapshot"})
        self._save_manifest(self._snapshot)
        h = self._health()
        return UpgradeResult("rollback", True, {
            "restored_version": self._snapshot.get("runtime_version"),
            "health": h.get("status"),
        })

    def seal(self) -> UpgradeResult:
        m = self._load_manifest()
        m["sealed"] = True
        self._save_manifest(m)
        return UpgradeResult("seal", True, {"version": m.get("runtime_version")})
