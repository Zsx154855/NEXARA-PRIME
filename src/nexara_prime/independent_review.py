"""Independent Reviewer and Auditor for repository-context missions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence import EvidenceStore
from .memory import MemoryKernel
from .real_context import RepositoryContext


class IndependentReview:
    """Two separate, read-only verdicts with no shared verdict state."""

    @staticmethod
    def reviewer_verdict(mission_id: str, report_path: str, context: RepositoryContext) -> dict[str, Any]:
        path = Path(report_path)
        if not path.exists() or not path.is_file():
            return {"mission_id": mission_id, "actor": "reviewer", "passed": False, "reason": "report_missing", "context_hash": context.context_hash}
        data = path.read_bytes()
        report_hash = hashlib.sha256(data).hexdigest()
        text = data.decode("utf-8", errors="replace")
        passed = (
            f"Context Hash: `{context.context_hash}`" in text
            and f"Repository Branch: `{context.branch}`" in text
            and f"Repository HEAD: `{context.head_sha}`" in text
            and "Provider:" in text
            and bool(data)
        )
        return {
            "mission_id": mission_id,
            "actor": "reviewer",
            "passed": passed,
            "reason": "report_context_and_provider_bound" if passed else "report_binding_invalid",
            "report_sha256": report_hash,
            "context_hash": context.context_hash,
        }

    @staticmethod
    def auditor_verdict(
        mission_id: str,
        context: RepositoryContext,
        evidence: EvidenceStore,
        memory: MemoryKernel,
    ) -> dict[str, Any]:
        chain = evidence.verify_receipt_chain(mission_id)
        bindings = memory.verify_evidence_binding(mission_id)
        passed = bool(chain["chain_intact"] and bindings["all_bound"])
        return {
            "mission_id": mission_id,
            "actor": "auditor",
            "passed": passed,
            "reason": "receipt_chain_and_memory_binding_valid" if passed else "governance_chain_invalid",
            "context_hash": context.context_hash,
            "receipt_chain": chain,
            "memory_binding": bindings,
        }

    @staticmethod
    def encode(verdict: dict[str, Any]) -> str:
        return json.dumps(verdict, ensure_ascii=False, sort_keys=True, indent=2)
