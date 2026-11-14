"""Controlled assembly for trusted experience learning.

The only supported production entry point for ExperienceLearner: it requires a
canonical EvidenceStore and passes the trusted verifier allowlist explicitly.
Construction without a store fails closed instead of silently learning nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .experience_learner import ExperienceLearner, TRUSTED_VERIFIER_ACTORS

if TYPE_CHECKING:
    from ..evidence import EvidenceStore
    from .memory_controller import MemoryController


def build_trusted_experience_learner(
    memory_controller: MemoryController,
    evidence_store: EvidenceStore | None,
    *,
    trusted_verifier_actors: frozenset[str] | None = None,
) -> ExperienceLearner:
    """Build a strict learner; refuse to assemble without a real EvidenceStore."""
    if evidence_store is None:
        raise ValueError("trusted_evidence_store_required")
    return ExperienceLearner(
        memory_controller,
        evidence_store=evidence_store,
        trusted_verifier_actors=(
            TRUSTED_VERIFIER_ACTORS
            if trusted_verifier_actors is None
            else frozenset(trusted_verifier_actors)
        ),
    )
