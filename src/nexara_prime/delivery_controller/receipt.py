"""Receipt adapter — generates and verifies delivery controller receipts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class DeliveryReceipt:
    """Generates delivery controller receipts with SHA-256 verification."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = Path(repo_root)

    def generate(
        self,
        head: str,
        branch: str,
        gates_passed: int,
        gates_total: int,
        status: str,
        evidence_refs: list[str],
    ) -> dict:
        """Generate a receipt payload."""
        payload = {
            "receipt_type": "delivery_controller_v1",
            "head": head,
            "branch": branch,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gates_passed": gates_passed,
            "gates_total": gates_total,
            "status": status,
            "evidence_refs": evidence_refs,
        }
        payload["sha256"] = self._hash(payload)
        return payload

    @staticmethod
    def _hash(payload: dict) -> str:
        """Canonical SHA-256 of receipt payload (excluding self-referential sha256 and mutable timestamp)."""
        cleaned = {k: v for k, v in payload.items() if k not in ("sha256", "timestamp")}
        encoded = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def save(self, receipt: dict) -> Path:
        """Save receipt to reports/ directory."""
        out_dir = self.repo_root / "reports" / "delivery_controller_bootstrap"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"receipt_{receipt['head'][:8]}.json"
        out_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        return out_path
