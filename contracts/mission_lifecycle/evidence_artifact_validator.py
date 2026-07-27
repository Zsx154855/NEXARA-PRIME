"""Evidence Artifact Validator — validates artifacts against the
Artifact→Validator→Evidence→Gate pipeline.

Part of NEXARA Agent Mission Lifecycle Manager Phase 1.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


# ── Artifact types ──

VALID_ARTIFACT_TYPES = frozenset({
    "CODE", "TEST_RESULT", "EVIDENCE", "RECEIPT",
    "REVIEW", "LOGS", "PLAN", "REPORT",
})
VALID_PRODUCERS = frozenset({"WRITER", "REVIEWER", "COORDINATOR", "APPROVER", "SYSTEM"})


def validate_artifact(
    artifact_type: str,
    artifact_data: dict[str, Any],
) -> ValidationResult:
    """Validate an evidence artifact.

    Checks common to all artifact types:
      1. artifact_type is valid.
      2. Required fields present: id, type, source, timestamp, mission_id.
      3. digest (SHA256) present for CODE/TEST_RESULT/EVIDENCE/RECEIPT.
      4. producer is a valid role.
      5. mission_id is bound.
      6. Type-specific validation rules.

    Args:
        artifact_type: One of VALID_ARTIFACT_TYPES.
        artifact_data: Dict with artifact fields.

    Returns:
        ValidationResult.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    atype = str(artifact_type).strip().upper()

    # Rule 1: valid type
    if atype not in VALID_ARTIFACT_TYPES:
        errors.append(ValidationError(
            code="INVALID_ARTIFACT_TYPE",
            message=f"'{artifact_type}' is not valid. Must be one of {sorted(VALID_ARTIFACT_TYPES)}.",
            detail={"artifact_type": artifact_type},
        ))
        return ValidationResult(valid=False, errors=errors)

    # Rule 2: required fields
    required_fields = {
        "artifact_id": str,
        "mission_id": (str, type(None)),
        "source": str,
        "timestamp": str,
    }
    for field, expected_type in required_fields.items():
        val = artifact_data.get(field)
        if val is None:
            errors.append(ValidationError(
                code="MISSING_REQUIRED_FIELD",
                message=f"Artifact missing required field '{field}'.",
                detail={"artifact_type": atype, "field": field},
            ))
        elif isinstance(expected_type, tuple):
            if not isinstance(val, expected_type):
                errors.append(ValidationError(
                    code="INVALID_FIELD_TYPE",
                    message=f"Field '{field}' expected {expected_type}, got {type(val).__name__}.",
                    detail={"artifact_type": atype, "field": field},
                ))
        elif not isinstance(val, expected_type):
            errors.append(ValidationError(
                code="INVALID_FIELD_TYPE",
                message=f"Field '{field}' expected {expected_type.__name__}, got {type(val).__name__}.",
                detail={"artifact_type": atype, "field": field, "expected": expected_type.__name__},
            ))

    # Rule 3: digest required for content-bearing types
    digest_required_types = frozenset({"CODE", "TEST_RESULT", "EVIDENCE", "RECEIPT"})
    if atype in digest_required_types:
        sha = artifact_data.get("sha256", "")
        if not sha or not isinstance(sha, str) or len(sha) != 64:
            errors.append(ValidationError(
                code="MISSING_SHA256",
                message=f"{atype} artifact requires valid sha256 digest (64 hex chars).",
                detail={"artifact_type": atype, "sha256": str(sha)[:20]},
            ))
        elif not all(c in "0123456789abcdef" for c in sha.lower()):
            errors.append(ValidationError(
                code="INVALID_SHA256",
                message=f"sha256 '{sha[:16]}...' is not valid hex.",
                detail={"artifact_type": atype},
            ))

    # Rule 4: valid producer
    producer = str(artifact_data.get("producer", "")).strip().upper()
    if producer and producer not in VALID_PRODUCERS:
        warnings.append(ValidationError(
            code="UNKNOWN_PRODUCER",
            message=f"Producer '{producer}' is not a recognized role. Must be one of {sorted(VALID_PRODUCERS)}.",
            detail={"producer": producer},
        ))

    # Rule 5: mission_id binding (warning only — validator doesn't block on pattern)
    mission_id = str(artifact_data.get("mission_id", ""))
    if not mission_id or not mission_id.startswith("mission_"):
        warnings.append(ValidationError(
            code="UNBOUND_MISSION",
            message=f"mission_id '{mission_id[:30]}' does not match expected pattern 'mission_*'.",
            detail={"mission_id": mission_id[:30]},
        ))

    # Rule 6: type-specific checks
    if atype == "CODE":
        if "ruff_check" not in artifact_data and "pytest_result" not in artifact_data:
            warnings.append(ValidationError(
                code="CODE_VALIDATION_MISSING",
                message="CODE artifact should include ruff_check and/or pytest_result.",
                detail={"artifact_type": atype},
            ))
    elif atype == "RECEIPT":
        cross_refs = artifact_data.get("cross_refs") or artifact_data.get("evidence_chain", {})
        if isinstance(cross_refs, dict) and not cross_refs:
            warnings.append(ValidationError(
                code="RECEIPT_NO_CROSS_REFS",
                message="RECEIPT artifact has no evidence cross-references.",
                detail={"artifact_type": atype},
            ))
        elif isinstance(cross_refs, list) and len(cross_refs) == 0:
            warnings.append(ValidationError(
                code="RECEIPT_NO_CROSS_REFS",
                message="RECEIPT artifact has no evidence cross-references.",
                detail={"artifact_type": atype},
            ))
        elif not cross_refs:
            warnings.append(ValidationError(
                code="RECEIPT_NO_CROSS_REFS",
                message="RECEIPT artifact has no evidence cross-references.",
                detail={"artifact_type": atype},
            ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
