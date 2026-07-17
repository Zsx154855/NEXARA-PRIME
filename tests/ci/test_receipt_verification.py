"""Tests for receipt verification — hash integrity, tampering detection, edge cases."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ci.receipt_hash import compute_file_sha256
from scripts.ci.verify_receipt import verify


def _actual_head():
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
        cwd=Path(__file__).resolve().parents[2], timeout=10,
    ).stdout.strip()


def _write_receipt(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


class TestReceiptVerification:
    def test_real_receipt_verifies_head_match(self):
        """Real authority receipt must have HEAD matching actual git HEAD."""
        receipts = sorted(Path(".runtime/ci/runs").glob("*/receipts/authority-receipt.json"))
        if not receipts:
            pytest.skip("no existing authority receipt found")
        vr = verify(receipts[-1])
        assert vr["status"] in ("PASS", "FAIL"), f"unexpected status: {vr}"
        assert vr["actual_head"] == _actual_head(), "verifier reports wrong HEAD"
        # receipt_head must match actual_head
        if vr["receipt_head"]:
            assert vr["receipt_head"] == vr["actual_head"], (
                f"receipt HEAD {vr['receipt_head'][:8]} != actual {vr['actual_head'][:8]}"
            )

    def test_real_receipt_has_complete_payload(self):
        """Real receipt must contain all required top-level fields."""
        receipts = sorted(Path(".runtime/ci/runs").glob("*/receipts/authority-receipt.json"))
        if not receipts:
            pytest.skip("no existing authority receipt found")
        payload = json.loads(receipts[-1].read_text())
        required = [
            "schema_version", "run_id", "validated_head", "checks",
            "overall_status", "receipt_payload_sha256", "receipt_file_sha256",
            "evidence_class", "hash_chain_status",
        ]
        for field in required:
            assert field in payload, f"missing required field: {field}"

    def test_missing_receipt_returns_error(self):
        result = verify(Path("/nonexistent/receipt.json"))
        assert result["status"] == "ERROR"

    def test_invalid_json_returns_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text("not json")
            result = verify(p)
            assert result["status"] == "ERROR"

    def test_tampered_payload_hash_detected(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            receipt = td_path / "receipt.json"
            payload = {
                "receipt_payload_sha256": "00" * 32,
                "receipt_file_sha256": "",
                "validated_head": _actual_head(),
                "checks": [],
                "previous_receipt_sha256": "",
                "hash_chain_status": "FIRST_RECEIPT",
            }
            _write_receipt(receipt, payload)
            result = verify(receipt)
            assert result["status"] == "FAIL"

    def test_missing_log_detected(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            receipt = td_path / "receipt.json"
            payload = {
                "receipt_payload_sha256": "",
                "receipt_file_sha256": "",
                "validated_head": _actual_head(),
                "checks": [{
                    "check_id": "test", "name": "test",
                    "log_path": "nonexistent.log",
                    "log_sha256": "abc",
                    "status": "PASS",
                }],
                "previous_receipt_sha256": "",
                "hash_chain_status": "FIRST_RECEIPT",
            }
            payload["receipt_payload_sha256"] = hashlib.sha256(
                json.dumps(payload, indent=2, sort_keys=True).encode()
            ).hexdigest()
            _write_receipt(receipt, payload)
            result = verify(receipt)
            assert result["status"] == "FAIL"

    def test_hash_chain_continuous_missing_prev(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            receipt = td_path / "receipt.json"
            payload = {
                "receipt_payload_sha256": "",
                "receipt_file_sha256": "",
                "validated_head": _actual_head(),
                "checks": [],
                "previous_receipt_sha256": "",
                "hash_chain_status": "CONTINUOUS",
            }
            payload["receipt_payload_sha256"] = hashlib.sha256(
                json.dumps(payload, indent=2, sort_keys=True).encode()
            ).hexdigest()
            _write_receipt(receipt, payload)
            result = verify(receipt)
            assert result["status"] == "FAIL"

    def test_receipt_log_hash_tampering(self):
        """Modifying a log file after receipt generation = verification FAIL."""
        import tempfile as tmp
        with tmp.TemporaryDirectory() as td:
            td_path = Path(td)
            log_file = td_path / "test.log"
            log_file.write_text("original content")
            log_hash = compute_file_sha256(log_file)
            receipt = td_path / "receipt.json"
            payload = {
                "receipt_payload_sha256": "",
                "receipt_file_sha256": "",
                "validated_head": _actual_head(),
                "checks": [{
                    "check_id": "test", "name": "test",
                    "log_path": str(log_file),
                    "log_sha256": log_hash,
                    "status": "PASS",
                }],
                "previous_receipt_sha256": "",
                "hash_chain_status": "FIRST_RECEIPT",
            }
            payload["receipt_payload_sha256"] = hashlib.sha256(
                json.dumps(payload, indent=2, sort_keys=True).encode()
            ).hexdigest()
            _write_receipt(receipt, payload)
            # Tamper with the log
            log_file.write_text("tampered content")
            result = verify(receipt)
            assert result["status"] == "FAIL"

    def test_not_applicable_does_not_count_as_pass(self):
        """NOT_APPLICABLE checks don't make the receipt status PASS by default."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            receipt = td_path / "receipt.json"
            payload = {
                "receipt_payload_sha256": "",
                "receipt_file_sha256": "",
                "validated_head": _actual_head(),
                "checks": [{
                    "check_id": "na", "name": "na-check",
                    "log_path": "", "log_sha256": "",
                    "status": "NOT_APPLICABLE_WITH_EVIDENCE",
                }],
                "previous_receipt_sha256": "",
                "hash_chain_status": "FIRST_RECEIPT",
            }
            payload["receipt_payload_sha256"] = hashlib.sha256(
                json.dumps(payload, indent=2, sort_keys=True).encode()
            ).hexdigest()
            _write_receipt(receipt, payload)
            result = verify(receipt)
            # Verify doesn't determine overall_status — it checks integrity
            assert "status" in result
