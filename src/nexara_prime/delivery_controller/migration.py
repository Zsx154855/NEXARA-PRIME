"""Legacy Evidence Migration Tool — converts pre-V2 evidence to unified schema.

Maps legacy fields to V2 Evidence Schema Contract:
  mission     → mission_id
  branch      → preserved in content
  base_sha    → preserved in content
  head_sha    → preserved in content
  timestamp   → timestamp (preserved as-is)
  evidence_sha256 → sha256

Generates evidence_id from SHA-256 of original content for idempotency.
All original fields are preserved under `legacy_data` for audit trail.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LegacyEvidenceMigrator:
    """Migrates legacy evidence JSON files to V2 schema."""

    LEGACY_FIELD_MAP = {
        "mission": "mission_id",
        "evidence_sha256": "sha256",
    }

    PRESERVED_LEGACY_KEYS = {
        "mission", "branch", "base_sha", "head_sha", "commit_count",
        "commits", "test_ledger", "crash_recovery_matrix", "defects",
        "fixes", "nsec_validator", "drift_detector", "ruff",
        "secret_scan", "import_cycles", "receipt_verifier",
        "evidence_sha256", "timestamp",
    }

    def __init__(self, repo_root: str) -> None:
        self.repo_root = Path(repo_root)
        self._evidence_dir = self.repo_root / ".nexara" / "evidence"

    def migrate_all(self, dry_run: bool = False) -> list[dict[str, Any]]:
        """Migrate all legacy evidence files. Returns migration report."""
        results: list[dict[str, Any]] = []
        legacy_files = self._find_legacy_files()
        for file_path in legacy_files:
            result = self._migrate_one(file_path, dry_run=dry_run)
            results.append(result)
        return results

    def _find_legacy_files(self) -> list[Path]:
        """Find JSON evidence files with legacy schema."""
        legacy: list[Path] = []
        if not self._evidence_dir.is_dir():
            return legacy
        for f in sorted(self._evidence_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            # Legacy indicator: has 'mission' or 'branch' but no 'evidence_id'
            has_legacy = any(k in data for k in ("mission", "branch", "head_sha"))
            has_v2 = "evidence_id" in data
            if has_legacy and not has_v2:
                legacy.append(f)
        return legacy

    def _migrate_one(self, path: Path, dry_run: bool = False) -> dict[str, Any]:
        """Migrate a single legacy evidence file to V2 schema."""
        original = json.loads(path.read_text())
        original_sha = hashlib.sha256(
            json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        evidence_id = f"evidence_migrated_{original_sha[:12]}"
        sha256 = original.get("evidence_sha256", "") or hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        timestamp = original.get("timestamp", datetime.now(timezone.utc).isoformat())

        # Map legacy fields
        mission_id = original.get("mission", "")
        kind = "legacy_migrated"

        # Build V2-conforming evidence
        v2_evidence: dict[str, Any] = {
            "evidence_id": evidence_id,
            "sha256": sha256,
            "timestamp": timestamp,
            "mission_id": mission_id,
            "kind": kind,
            "source": "legacy_migration_tool_v2.1",
            "content": f"Migrated from legacy evidence: {path.name}. Original SHA: {original_sha}",
            "legacy_data": {
                k: v for k, v in original.items()
                if k in self.PRESERVED_LEGACY_KEYS
            },
            "migration_metadata": {
                "original_file": path.name,
                "original_sha256": original_sha,
                "migrated_at": datetime.now(timezone.utc).isoformat(),
                "migrator_version": "v2.1",
                "schema_version": 2,
            },
        }

        # Compute final SHA for the new evidence
        final_payload = {k: v for k, v in v2_evidence.items() if k not in ("sha256",)}
        v2_evidence["sha256"] = hashlib.sha256(
            json.dumps(final_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        if not dry_run:
            # Write migrated file (preserve original as .legacy.bak)
            backup_path = path.with_suffix(".json.legacy.bak")
            backup_path.write_text(path.read_text())
            path.write_text(json.dumps(v2_evidence, ensure_ascii=False, indent=2))
        else:
            backup_path = None

        return {
            "file": path.name,
            "original_sha256": original_sha,
            "new_evidence_id": evidence_id,
            "new_sha256": v2_evidence["sha256"],
            "mission_id": mission_id,
            "dry_run": dry_run,
            "backup_created": str(backup_path) if not dry_run else None,
        }
