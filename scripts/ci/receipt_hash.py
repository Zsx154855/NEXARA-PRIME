"""Canonical receipt hashing — single source of truth for receipt integrity.

Used by both Authority (generator) and verify_receipt (verifier).
Ensures the hash contract is identical at both ends.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Fields that must be excluded from the canonical payload hash
# because they are computed AFTER the payload and would be self-referential.
_EXCLUDED_FROM_CANONICAL = frozenset({
    "receipt_payload_sha256",
    "receipt_file_sha256",
})


def canonical_payload_json(payload: dict) -> str:
    """Serialize payload to canonical JSON for hashing.

    Excludes self-referential hash fields. Uses stable serialization:
    - sort_keys=True for key-order independence
    - indent=2 for readability (deterministic in CPython dict ordering)
    - ensure_ascii=False for UTF-8 fidelity
    - No trailing newline
    """
    cleaned = {
        k: v for k, v in payload.items()
        if k not in _EXCLUDED_FROM_CANONICAL
    }
    return json.dumps(cleaned, indent=2, sort_keys=True, ensure_ascii=False)


def compute_payload_sha256(payload: dict) -> str:
    """Compute canonical SHA-256 of a receipt payload."""
    canonical = canonical_payload_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_payload_integrity(payload: dict) -> dict:
    """Verify the payload's self-reported hash matches its canonical content.

    Returns {'status': 'PASS'} or {'status': 'FAIL', 'errors': [...]}
    """
    claimed = payload.get("receipt_payload_sha256", "")
    if not claimed:
        return {"status": "FAIL", "errors": ["missing receipt_payload_sha256"]}
    actual = compute_payload_sha256(payload)
    if actual != claimed:
        return {
            "status": "FAIL",
            "errors": [
                f"payload hash mismatch: claimed={claimed[:16]} actual={actual[:16]}"
            ],
        }
    return {"status": "PASS"}
