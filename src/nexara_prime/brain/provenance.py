"""ProvenanceTracker — trace memory records back to source evidence.

Every brain memory write records a provenance chain:
  memory_id → evidence_id → source_file → commit_sha → trace_id

Enables full audit trail and integrity verification.
"""

from __future__ import annotations

import hashlib
from typing import Any, TYPE_CHECKING


if TYPE_CHECKING:
    from .db import BrainDB


class ProvenanceTracker:
    """Tracks and verifies the provenance chain for brain memories."""

    def __init__(self, db: "BrainDB") -> None:
        self._db = db

    def record(
        self,
        memory_id: str,
        evidence_id: str,
        source_file: str = "",
        commit_sha: str = "",
        trace_id: str = "",
    ) -> str:
        """Record provenance for a memory. Returns provenance_id."""
        return self._db.record_provenance(
            memory_id=memory_id,
            evidence_id=evidence_id,
            source_file=source_file,
            commit_sha=commit_sha,
            trace_id=trace_id,
        )

    def get_chain(self, memory_id: str) -> dict[str, Any] | None:
        """Get the full provenance chain for a memory."""
        return self._db.get_provenance(memory_id)

    def verify_chain(self, memory_id: str) -> bool:
        """Verify provenance chain integrity. Returns True if chain is intact."""
        prov = self._db.get_provenance(memory_id)
        if not prov:
            return False
        # Chain is intact if provenance exists and evidence_id is non-empty
        return bool(prov.get("evidence_id"))

    def compute_chain_hash(self, memory_id: str) -> str | None:
        """Compute SHA-256 of provenance chain for integrity verification."""
        prov = self._db.get_provenance(memory_id)
        if not prov:
            return None
        chain_str = (
            f"{prov.get('memory_id','')}:{prov.get('evidence_id','')}:"
            f"{prov.get('source_file','')}:{prov.get('commit_sha','')}:"
            f"{prov.get('trace_id','')}"
        )
        return hashlib.sha256(chain_str.encode()).hexdigest()
