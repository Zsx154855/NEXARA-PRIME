"""Cross Reference Integrity Validator — validates artifact reference chains:

  Artifact → Receipt → Evidence Bundle → Mission

Part of NEXARA Agent Mission Lifecycle Manager Phase 1 Hardening.
"""
from __future__ import annotations

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


def validate_cross_references(
    receipt: dict[str, Any],
    artifacts: list[dict[str, Any]],
    evidence_bundle: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate cross-references between a receipt and its referenced artifacts.

    Checks:
      1. Every artifact_id referenced in the receipt exists in the artifacts list.
      2. Every referenced artifact has a matching sha256 digest.
      3. Every referenced artifact has the same mission_id as the receipt.
      4. No duplicate references to the same artifact_id.
      5. Evidence bundle (if provided) contains all referenced artifacts.

    Args:
        receipt: Receipt dict with evidence_chain or cross_refs.
        artifacts: List of artifact dicts that the receipt references.
        evidence_bundle: Optional bundle metadata for completeness check.

    Returns:
        ValidationResult.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    # Extract referenced IDs from receipt
    refs: list[dict[str, Any]] = []
    chain = receipt.get("evidence_chain", receipt.get("cross_refs", []))
    if isinstance(chain, dict):
        # evidence_chain as {artifacts: [...]} or {chain: [...]}
        refs = chain.get("artifacts", chain.get("chain", []))
    elif isinstance(chain, list):
        refs = chain

    if not refs:
        warnings.append(ValidationError(
            code="NO_CROSS_REFS",
            message="Receipt has no cross-references in evidence_chain or cross_refs.",
            detail={"receipt_id": receipt.get("receipt_id", "unknown")},
        ))
        return ValidationResult(valid=True, errors=errors, warnings=warnings)

    # Build lookup: artifact_id → artifact
    artifact_map: dict[str, dict[str, Any]] = {}
    for a in artifacts:
        aid = a.get("artifact_id", "")
        if aid:
            artifact_map[aid] = a

    receipt_mission = receipt.get("mission_id", "")

    seen_ids: set[str] = set()

    for ref in refs:
        ref_id = ref.get("artifact_id", ref.get("id", ""))
        ref_sha = ref.get("sha256", "")
        ref_mission = ref.get("mission_id", receipt_mission)

        if not ref_id:
            errors.append(ValidationError(
                code="MISSING_REFERENCE_ID",
                message="Cross-reference entry has no artifact_id.",
                detail={"ref": ref},
            ))
            continue

        # Check 4: duplicate
        if ref_id in seen_ids:
            errors.append(ValidationError(
                code="DUPLICATE_REFERENCE",
                message=f"Artifact '{ref_id}' referenced multiple times.",
                detail={"artifact_id": ref_id},
            ))
            continue
        seen_ids.add(ref_id)

        # Check 1: artifact exists
        actual = artifact_map.get(ref_id)
        if actual is None:
            errors.append(ValidationError(
                code="MISSING_ARTIFACT",
                message=f"Artifact '{ref_id}' referenced in receipt but not found in artifact list.",
                detail={"artifact_id": ref_id},
            ))
            continue

        # Check 2: digest match
        if ref_sha:
            actual_sha = actual.get("sha256", "")
            if actual_sha and ref_sha != actual_sha:
                errors.append(ValidationError(
                    code="DIGEST_MISMATCH",
                    message=(
                        f"Artifact '{ref_id}' digest mismatch: "
                        f"receipt={ref_sha[:16]}... actual={actual_sha[:16]}..."
                    ),
                    detail={
                        "artifact_id": ref_id,
                        "receipt_sha256": ref_sha,
                        "actual_sha256": actual_sha,
                    },
                ))

        # Check 3: mission match (receipt mission must match artifact mission)
        if receipt_mission:
            actual_mission = actual.get("mission_id", "")
            if actual_mission and receipt_mission != actual_mission:
                errors.append(ValidationError(
                    code="MISSION_MISMATCH",
                    message=(
                        f"Artifact '{ref_id}' mission mismatch: "
                        f"receipt={receipt_mission} actual={actual_mission}"
                    ),
                    detail={
                        "artifact_id": ref_id,
                        "receipt_mission": receipt_mission,
                        "actual_mission": actual_mission,
                    },
                ))

    # Check 5: evidence bundle completeness
    if evidence_bundle:
        bundle_ids = set(evidence_bundle.get("artifact_ids", []))
        missing_from_bundle = seen_ids - bundle_ids
        if missing_from_bundle:
            warnings.append(ValidationError(
                code="BUNDLE_INCOMPLETE",
                message=f"Evidence bundle missing {len(missing_from_bundle)} referenced artifacts.",
                detail={"missing": sorted(missing_from_bundle)},
            ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
