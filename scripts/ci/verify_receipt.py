#!/usr/bin/env python3
"""Verify a NEXARA CI Authority receipt — all logs, hashes, and chain integrity."""
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def verify(receipt_path: Path) -> dict:
    if not receipt_path.exists():
        return {"status": "ERROR", "reason": f"receipt not found: {receipt_path}"}

    try:
        json.loads(receipt_path.read_text())
    except json.JSONDecodeError as e:
        return {"status": "ERROR", "reason": f"invalid JSON: {e}"}

    errors = []

    # 1. Verify receipt file hash
    content = receipt_path.read_text()
    payload = json.loads(content)
    payload.pop("receipt_file_sha256", "")
    payload_minus_hash = json.dumps(payload, indent=2, sort_keys=True)
    claimed_payload_hash = payload.get("receipt_payload_sha256", "")

    actual_payload_hash = hashlib.sha256(payload_minus_hash.encode()).hexdigest()
    if actual_payload_hash != claimed_payload_hash:
        errors.append(f"payload hash mismatch: claimed={claimed_payload_hash[:16]} actual={actual_payload_hash[:16]}")

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
                actual_log_hash = sha256_file(log_file)
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
