"""Sovereign Authority Receipt — generates and verifies sovereign CI receipts.

SHA-256 based, excludes self-referential fields, bound to exact HEAD.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class AuthorityReceipt:
    """Generates sovereign authority receipts with SHA-256 verification."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = Path(repo_root)

    def generate(
        self,
        target_head: str,
        authority_context: str,
        gate_results: dict[str, bool],
        evidence_sha256: str,
        protection_before: str,
        protection_after: str,
        publisher_identity: str = "nexara-sovereign-bridge",
    ) -> dict:
        """Generate a sovereign authority receipt."""
        payload = {
            "receipt_type": "sovereign_ci_authority_v1",
            "target_head": target_head,
            "authority_context": authority_context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gate_results": gate_results,
            "evidence_sha256": evidence_sha256,
            "protection_before_sha256": protection_before,
            "protection_after_sha256": protection_after,
            "publisher_identity": publisher_identity,
            "final_decision": self._decision(gate_results),
        }
        payload["sha256"] = self._hash(payload)
        return payload

    @staticmethod
    def _decision(gate_results: dict[str, bool]) -> str:
        """Determine final decision from gate results."""
        mandatory = [
            "A1_TARGET_HEAD", "A2_REPOSITORY", "A3_GOVERNANCE",
            "A4_CONTRACT", "A5_FULL_VALIDATION", "A6_STATIC_AND_SECURITY",
            "A7_EVIDENCE", "A8_RECEIPT", "A10_REVIEW",
        ]
        if all(gate_results.get(g, False) for g in mandatory):
            return "success"
        return "failure"

    @staticmethod
    def _hash(payload: dict) -> str:
        """Canonical SHA-256 excluding self-referential and mutable fields."""
        excluded = {"sha256", "timestamp"}
        cleaned = {k: v for k, v in payload.items() if k not in excluded}
        encoded = json.dumps(
            cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def save(self, receipt: dict, subdir: str = "sovereign_ci_authority_bridge_v1") -> Path:
        """Save receipt to reports directory."""
        out_dir = self.repo_root / "reports" / subdir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"receipt_{receipt['target_head'][:8]}.json"
        out_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        return out_path
