"""Formal Error Taxonomy for NEXARA PRIME (L2 module).

This is a standalone L2 module. It does NOT import or modify any Core module
(models.py / runtime.py / api.py / memory.py / evidence.py / tools.py /
recovery.py). It defines a canonical, deterministic classification of every
operational error the Chief Brain runtime can emit, together with the retry,
backoff, recovery, and evidence policy that governs each class.

The single special case is TOOL_IDEMPOTENCY_CONFLICT, which MUST NOT be
folded into the generic TOOL_ERROR policy: an idempotency conflict means the
work was already executed under the same key, so the correct recovery is to
REUSE the existing result (retryable=False, recovery_strategy='reuse_existing'),
never to blindly retry (which would re-run a side-effecting tool) nor to fail.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorTaxonomyEntry:
    """One class of operational error and its governing policy."""

    error_code: str
    retryable: bool
    max_retry: int
    backoff: str
    recovery_strategy: str
    terminal_state: str
    evidence_required: bool


class ErrorTaxonomy:
    """Canonical, deterministic error taxonomy with policy lookup.

    Use ``ErrorTaxonomy.lookup(code)`` to resolve an error_code to its
    governing ``ErrorTaxonomyEntry``. Unknown codes resolve to UNKNOWN
    (fail-closed: no retry, terminal, evidence required).
    """

    # (code, retryable, max_retry, backoff, recovery_strategy, terminal_state, evidence_required)
    _POLICIES: dict[str, tuple] = {
        "TRANSIENT":                  ("TRANSIENT", True,  5, "exponential", "retry",          "recoverable",     False),
        "TIMEOUT":                    ("TIMEOUT",   True,  3, "exponential", "retry",          "recoverable",     False),
        "RATE_LIMIT":                 ("RATE_LIMIT", True, 5, "exponential", "retry",          "recoverable",     False),
        "PROVIDER_ERROR":             ("PROVIDER_ERROR", True, 3, "exponential", "retry",      "recoverable",     False),
        "TOOL_ERROR":                 ("TOOL_ERROR", True,  2, "exponential", "retry",         "recoverable",     False),
        "TOOL_IDEMPOTENCY_CONFLICT":  ("TOOL_IDEMPOTENCY_CONFLICT", False, 0, "none", "reuse_existing", "reused", True),
        "TOOL_PERMISSION_DENIED":     ("TOOL_PERMISSION_DENIED",   False, 0, "none", "fail_terminal",  "failed_terminal", True),
        "TOOL_INVALID_OUTPUT":        ("TOOL_INVALID_OUTPUT",      True,  3, "exponential", "retry",          "recoverable",     True),
        "GOVERNANCE_DENIED":          ("GOVERNANCE_DENIED",        False, 0, "none", "fail_terminal",  "failed_terminal", True),
        "PERSISTENCE_ERROR":          ("PERSISTENCE_ERROR",        True,  3, "exponential", "retry",          "recoverable",     False),
        "CHECKPOINT_ERROR":           ("CHECKPOINT_ERROR",         True,  3, "exponential", "retry",          "recoverable",     True),
        "NETWORK_ERROR":              ("NETWORK_ERROR",            True,  5, "exponential", "retry",          "recoverable",     False),
        "CONFIG_ERROR":               ("CONFIG_ERROR",             False, 0, "none", "fail_terminal",  "failed_terminal", True),
        "SYSTEM_ERROR":               ("SYSTEM_ERROR",             False, 1, "exponential", "fail_terminal",  "failed_terminal", True),
        "UNKNOWN":                    ("UNKNOWN",                  False, 0, "none", "fail_terminal",  "failed_terminal", True),
    }

    _ENTRIES: dict[str, ErrorTaxonomyEntry] = {
        code: ErrorTaxonomyEntry(
            error_code=code,
            retryable=retryable,
            max_retry=max_retry,
            backoff=backoff,
            recovery_strategy=recovery_strategy,
            terminal_state=terminal_state,
            evidence_required=evidence_required,
        )
        for code, (_, retryable, max_retry, backoff, recovery_strategy, terminal_state, evidence_required) in _POLICIES.items()
    }

    @classmethod
    def lookup(cls, error_code: str) -> ErrorTaxonomyEntry:
        """Resolve an error_code to its policy entry (case-insensitive).

        Returns the UNKNOWN entry (fail-closed) for unrecognized codes.
        """
        return cls._ENTRIES.get(error_code.upper(), cls._ENTRIES["UNKNOWN"])

    @classmethod
    def all_entries(cls) -> list[ErrorTaxonomyEntry]:
        """Return every taxonomy entry in definition order."""
        return list(cls._ENTRIES.values())

    @classmethod
    def codes(cls) -> list[str]:
        """Return the canonical error_code strings in definition order."""
        return list(cls._ENTRIES.keys())


__all__ = ["ErrorTaxonomy", "ErrorTaxonomyEntry"]
