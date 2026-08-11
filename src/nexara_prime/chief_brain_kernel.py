"""ChiefBrainKernel — DEPRECATED compatibility shim (v1.0.0 F2 consolidation).

This module is retained ONLY for backward compatibility with code that
imports from `nexara_prime.chief_brain_kernel`.

ALL functionality moved to `nexara_prime.brain.kernel` — the single
ChiefBrainKernel authority for the project.

Migration:
    from nexara_prime.chief_brain_kernel import ChiefBrainKernel  # OLD
    from nexara_prime.brain.kernel import ChiefBrainKernel        # NEW
"""

from __future__ import annotations

# Re-export from the canonical location
from .brain.kernel import ChiefBrainKernel  # noqa: F401

__all__ = ["ChiefBrainKernel"]
