#!/usr/bin/env python3
"""Verify a NEXARA CI Authority receipt — all logs, hashes, and chain integrity.

Uses scripts/ci/receipt_hash.py as the single source of truth for
canonical payload hashing. Both the Authority generator and this
verifier use the same function — eliminating hash drift.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Shared canonical hash contract
from scripts.ci.receipt_hash import (  # noqa: E402
    verify_payload_integrity,
    compute_file_sha256,
)


def verify(receipt_path: Path) -> dict:
    if not receipt_path.exists():
        return {"status": "ERROR", "reason": f"receipt not found: {receipt_path}"}

    # Parse
    try:
        content = receipt_path.read_text()
        payload = json.loads(content)
    except json.JSONDecodeError as e:
        return {"status": "ERROR", "reason": f"invalid JSON: {e}"}

    errors = []

    # 1. Canonical payload hash integrity (shared contract)
    result = verify_payload_integrity(payload)
    if result["status"] != "PASS":
        errors.extend(result.get("errors", ["payload hash verification failed"]))

    # 2. Verify HEAD
    import subprocess
    actual_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
        cwd=REPO_ROOT, timeout=10,
    ).stdout.strip()
    receipt_head = payload.get("validated_head", "")
    if actual_head != receipt_head:
        errors.append(f"HEAD mismatch: receipt={receipt_head[:8]} actual={actual_head[:8]}")

    # 3. Verify all logs exist with correct hashes
    for check in payload.get("checks", []):
        log_path = check.get("log_path", "")
        if log_path:
            log_file = REPO_ROOT / log_path
            if not log_file.exists():
                errors.append(f"missing log: {log_path}")
            else:
                actual_log_hash = compute_file_sha256(log_file)
                claimed_log_hash = check.get("log_sha256", "")
                if actual_log_hash != claimed_log_hash:
                    errors.append(f"log hash mismatch: {log_path}")

    # 4. Verify hash chain
    prev = payload.get("previous_receipt_sha256", "")
    chain_status = payload.get("hash_chain_status", "")
    if chain_status == "CONTINUOUS" and not prev:
        errors.append("hash chain claims CONTINUOUS but no previous_receipt_sha256")

    if errors:
        return {"status": "FAIL", "errors": errors,
                "receipt_head": receipt_head, "actual_head": actual_head}
    return {"status": "PASS", "receipt_head": receipt_head, "actual_head": actual_head}


def main():
    if len(sys.argv) < 2:
        print("Usage: verify_receipt.py <receipt.json|latest.json>")
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.is_absolute():
        path = REPO_ROOT / path

    result = verify(path)
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
