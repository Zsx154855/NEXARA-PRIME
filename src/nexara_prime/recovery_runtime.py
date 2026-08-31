"""Recovery Runtime executor (L2 module) — deterministic recovery decisions.

This is a standalone L2 module. It imports NOTHING from the frozen Core set
(models.py / runtime.py / api.py / memory.py / evidence.py / tools.py /
recovery.py / governance.py). Its only dependency is the sibling L2 module
:mod:`error_taxonomy`, which supplies the canonical 15-class error policy.

``RecoveryExecutor`` turns a raw ``(exception_type, error_msg)`` pair into a
concrete recovery decision by (1) normalising the exception type, (2) resolving
it to a canonical error_code via the taxonomy, and (3) returning the governing
policy. ``recovery.py`` (Core) is left untouched.
"""

from __future__ import annotations

import re

from .error_taxonomy import ErrorTaxonomy, ErrorTaxonomyEntry

__all__ = ["RecoveryExecutor"]

# Normalised exception-name → canonical error_code.
_EXCEPTION_NAME_MAP: dict[str, str] = {
    # Timeouts
    "TIMEOUT": "TIMEOUT",
    "TIMEOUT_ERROR": "TIMEOUT",
    "TIMEOUTERROR": "TIMEOUT",
    # Network
    "NETWORK_ERROR": "NETWORK_ERROR",
    "NETWORKERROR": "NETWORK_ERROR",
    "CONNECTION_ERROR": "NETWORK_ERROR",
    "CONNECTIONERROR": "NETWORK_ERROR",
    "CONNECTION_RESET": "NETWORK_ERROR",
    # Rate limiting
    "RATE_LIMIT": "RATE_LIMIT",
    "RATE_LIMIT_ERROR": "RATE_LIMIT",
    "RATELIMITERROR": "RATE_LIMIT",
    # Provider
    "PROVIDER_ERROR": "PROVIDER_ERROR",
    "PROVIDERERROR": "PROVIDER_ERROR",
    # Permission
    "PERMISSION_ERROR": "TOOL_PERMISSION_DENIED",
    "PERMISSIONERROR": "TOOL_PERMISSION_DENIED",
    "PERMISSION_DENIED": "TOOL_PERMISSION_DENIED",
    "TOOL_PERMISSION_DENIED": "TOOL_PERMISSION_DENIED",
    # Governance
    "GOVERNANCE_DENIED": "GOVERNANCE_DENIED",
    "GOVERNANCEDENIED": "GOVERNANCE_DENIED",
    # Persistence / checkpoint
    "PERSISTENCE_ERROR": "PERSISTENCE_ERROR",
    "PERSISTENCEERROR": "PERSISTENCE_ERROR",
    "CHECKPOINT_ERROR": "CHECKPOINT_ERROR",
    "CHECKPOINTERROR": "CHECKPOINT_ERROR",
    # Config / system
    "CONFIG_ERROR": "CONFIG_ERROR",
    "CONFIGERROR": "CONFIG_ERROR",
    "SYSTEM_ERROR": "SYSTEM_ERROR",
    "SYSTEMERROR": "SYSTEM_ERROR",
    # Idempotency
    "TOOL_IDEMPOTENCY_CONFLICT": "TOOL_IDEMPOTENCY_CONFLICT",
    "IDEMPOTENCY_CONFLICT": "TOOL_IDEMPOTENCY_CONFLICT",
    "IDEMPOTENCYCONFLICT": "TOOL_IDEMPOTENCY_CONFLICT",
}

# Keyword → canonical error_code. Ordered: most specific first.
_KEYWORD_PATTERNS: list[tuple[str, str]] = [
    ("idempotency", "TOOL_IDEMPOTENCY_CONFLICT"),
    ("idempotent", "TOOL_IDEMPOTENCY_CONFLICT"),
    ("already executed", "TOOL_IDEMPOTENCY_CONFLICT"),
    ("already exists", "TOOL_IDEMPOTENCY_CONFLICT"),
    ("permission denied", "TOOL_PERMISSION_DENIED"),
    ("forbidden", "TOOL_PERMISSION_DENIED"),
    ("unauthorized", "TOOL_PERMISSION_DENIED"),
    ("rate limit", "RATE_LIMIT"),
    ("too many requests", "RATE_LIMIT"),
    ("429", "RATE_LIMIT"),
    ("timeout", "TIMEOUT"),
    ("timed out", "TIMEOUT"),
    ("connection", "NETWORK_ERROR"),
    ("network", "NETWORK_ERROR"),
    ("dns", "NETWORK_ERROR"),
    ("governance denied", "GOVERNANCE_DENIED"),
    ("policy denied", "GOVERNANCE_DENIED"),
    ("checkpoint", "CHECKPOINT_ERROR"),
    ("persist", "PERSISTENCE_ERROR"),
    ("database", "PERSISTENCE_ERROR"),
    ("sqlite", "PERSISTENCE_ERROR"),
    ("invalid output", "TOOL_INVALID_OUTPUT"),
    ("validation", "TOOL_INVALID_OUTPUT"),
    ("config", "CONFIG_ERROR"),
    ("provider", "PROVIDER_ERROR"),
    ("transient", "TRANSIENT"),
]


class RecoveryExecutor:
    """Turn a raw exception into a deterministic recovery decision.

    Public API:
      - ``classify(exception_type, error_msg=None)`` → decision dict
      - ``should_retry(attempt, error_class)`` → bool
      - ``apply_policy(error_class)`` → policy dict
    """

    # ── classification ────────────────────────────────────────────────────

    @staticmethod
    def _normalize(name: str) -> str:
        """Normalize an exception type/name to an UPPER_SNAKE token."""
        s = str(name).strip()
        if "." in s:
            s = s.rsplit(".", 1)[-1]
        s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)  # camelCase → snake
        s = s.replace("-", "_").replace(" ", "_")
        s = s.upper()
        return re.sub(r"_+", "_", s).strip("_")

    @staticmethod
    def _to_code(error_class: object) -> str:
        """Resolve an error_code / exception name / entry to a canonical code."""
        if isinstance(error_class, ErrorTaxonomyEntry):
            return error_class.error_code
        return RecoveryExecutor._normalize(str(error_class))

    def _resolve_code(self, exception_type: object, error_msg: str | None) -> str:
        """Resolve exception_type (+ optional message) to a canonical error_code."""
        norm = self._normalize(str(exception_type))

        # 1. Already a canonical taxonomy code.
        if norm in ErrorTaxonomy.codes():
            return norm

        # 2. Known exception-name mapping.
        if norm in _EXCEPTION_NAME_MAP:
            return _EXCEPTION_NAME_MAP[norm]

        # 3. Keyword scan over exception_type + error_msg.
        haystack = f"{norm} {error_msg or ''}".lower()
        for keyword, code in _KEYWORD_PATTERNS:
            if keyword in haystack:
                return code

        # 4. Fail-closed.
        return "UNKNOWN"

    def classify(self, exception_type: object, error_msg: str | None = None) -> dict:
        """Classify an exception into a recovery decision dict.

        Returns the governing policy as a dict: error_code, retryable,
        max_retry, backoff, recovery_strategy, terminal_state, evidence_required.
        """
        code = self._resolve_code(exception_type, error_msg)
        return self.apply_policy(code)

    def apply_policy(self, error_class: object) -> dict:
        """Return the policy dict for a given error code / exception / entry."""
        code = self._to_code(error_class)
        entry = ErrorTaxonomy.lookup(code)
        return {
            "error_code": entry.error_code,
            "retryable": entry.retryable,
            "max_retry": entry.max_retry,
            "backoff": entry.backoff,
            "recovery_strategy": entry.recovery_strategy,
            "terminal_state": entry.terminal_state,
            "evidence_required": entry.evidence_required,
        }

    def should_retry(self, attempt: int, error_class: object) -> bool:
        """Return True if the error permits another retry.

        ``attempt`` is the zero-based count of retries already made (0 = first
        failure, retry allowed). A non-retryable class (e.g.
        TOOL_IDEMPOTENCY_CONFLICT) always returns False.
        """
        entry = ErrorTaxonomy.lookup(self._to_code(error_class))
        if not entry.retryable:
            return False
        return attempt < entry.max_retry
