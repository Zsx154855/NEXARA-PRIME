"""Evidence adapter V2 — unified schema contract with legacy migration detection.

Defines the canonical evidence schema contract per Delivery Controller V2.
Validates all .nexara/evidence/*.json files against the unified schema.
Detects legacy-format evidence and reports migration needs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Evidence Schema Contract ──

EVIDENCE_MINIMAL_REQUIRED: set[str] = {"evidence_id", "sha256", "timestamp"}
EVIDENCE_FULL_REQUIRED: set[str] = {"evidence_id", "sha256", "timestamp", "mission_id", "kind"}
EVIDENCE_LEGACY_INDICATORS: list[str] = ["mission", "branch", "base_sha", "head_sha"]


@dataclass
class EvidenceSchemaResult:
    """Result of evidence schema validation."""

    file_name: str
    is_valid_json: bool
    schema_status: str  # "CONFORMING", "FULLY_CONFORMING", "LEGACY", "INVALID"
    missing_fields: list[str] = field(default_factory=list)
    legacy_fields: list[str] = field(default_factory=list)
    evidence_id: str | None = None
    sha256: str | None = None


class EvidenceSchemaValidator:
    """Validates evidence files against the unified schema contract."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = Path(repo_root)
        self._evidence_dir = self.repo_root / ".nexara" / "evidence"

    def validate_all(self) -> list[EvidenceSchemaResult]:
        """Validate all evidence JSON files. Returns results for every file found."""
        results: list[EvidenceSchemaResult] = []
        if not self._evidence_dir.is_dir():
            return results

        for f in sorted(self._evidence_dir.glob("*.json")):
            result = self._validate_file(f)
            results.append(result)
        return results

    def _validate_file(self, path: Path) -> EvidenceSchemaResult:
        """Validate a single evidence JSON file."""
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return EvidenceSchemaResult(
                file_name=path.name,
                is_valid_json=False,
                schema_status="INVALID",
            )

        if not isinstance(data, dict):
            return EvidenceSchemaResult(
                file_name=path.name,
                is_valid_json=True,
                schema_status="INVALID",
            )

        keys = set(data.keys())
        has_minimal = EVIDENCE_MINIMAL_REQUIRED.issubset(keys)
        has_full = EVIDENCE_FULL_REQUIRED.issubset(keys)
        has_legacy = any(k in keys for k in EVIDENCE_LEGACY_INDICATORS)

        if has_full:
            return EvidenceSchemaResult(
                file_name=path.name,
                is_valid_json=True,
                schema_status="FULLY_CONFORMING",
                evidence_id=str(data.get("evidence_id", "")),
                sha256=str(data.get("sha256", "")),
            )
        elif has_minimal:
            missing_full = sorted(EVIDENCE_FULL_REQUIRED - keys)
            return EvidenceSchemaResult(
                file_name=path.name,
                is_valid_json=True,
                schema_status="CONFORMING",
                missing_fields=missing_full,
                evidence_id=str(data.get("evidence_id", "")),
                sha256=str(data.get("sha256", "")),
            )
        elif has_legacy:
            return EvidenceSchemaResult(
                file_name=path.name,
                is_valid_json=True,
                schema_status="LEGACY",
                missing_fields=sorted(EVIDENCE_MINIMAL_REQUIRED - keys),
                legacy_fields=[k for k in EVIDENCE_LEGACY_INDICATORS if k in keys],
            )
        else:
            return EvidenceSchemaResult(
                file_name=path.name,
                is_valid_json=True,
                schema_status="INVALID",
                missing_fields=sorted(EVIDENCE_MINIMAL_REQUIRED - keys),
            )

    def summary(self) -> dict[str, Any]:
        """Generate a summary of all evidence schema validation."""
        results = self.validate_all()
        conforming = sum(1 for r in results if r.schema_status in ("CONFORMING", "FULLY_CONFORMING"))
        legacy = sum(1 for r in results if r.schema_status == "LEGACY")
        invalid = sum(1 for r in results if r.schema_status == "INVALID")
        return {
            "total_files": len(results),
            "conforming": conforming,
            "legacy": legacy,
            "invalid": invalid,
            "all_conforming": invalid == 0 and legacy == 0,
            "needs_migration": legacy > 0,
            "details": [
                {
                    "file": r.file_name,
                    "status": r.schema_status,
                    "missing": r.missing_fields,
                    "legacy": r.legacy_fields,
                }
                for r in results
            ],
        }


class DeliveryEvidence:
    """Thin adapter over the existing EvidenceStore for delivery controller use."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root

    @staticmethod
    def evidence_exists(repo_root: str) -> bool:
        """Check if evidence directory has at least one valid JSON file."""
        evidence_dir = Path(repo_root) / ".nexara" / "evidence"
        if not evidence_dir.is_dir():
            return False
        for f in evidence_dir.glob("*.json"):
            try:
                json.loads(f.read_text())
                return True
            except (json.JSONDecodeError, OSError):
                continue
        return False

    @staticmethod
    def count_evidence_files(repo_root: str) -> int:
        evidence_dir = Path(repo_root) / ".nexara" / "evidence"
        if not evidence_dir.is_dir():
            return 0
        return len(list(evidence_dir.glob("*.json")))
