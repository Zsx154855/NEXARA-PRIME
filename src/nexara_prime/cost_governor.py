"""Token / Cost Governor (L2 module) — five-layer token & cost budgets.

Standalone L2 module: imports NOTHING from the frozen Core set. Provides a
five-scope budget ledger (session / mission / provider / model / daily) with a
soft (WARN) and hard (BLOCK) limit per scope.

Semantics:
  - A scope is unlimited until ``set_budget`` is called with a positive limit.
  - ``record_usage`` always counts tokens. When ``cost_usd`` is ``None`` the
    token count is still recorded but NO cost is accumulated (never forge a
    fake ``0.0`` cost — absence of cost data is preserved, not zeroed).
  - Exceeding the hard limit returns BLOCK; crossing the soft threshold
    (``warn_ratio * limit``) returns WARN; otherwise OK.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["TokenGovernor", "ScopeUsage"]

# Canonical budget scopes. ``daily`` is a global scope (not keyed by key).
SCOPES: frozenset[str] = frozenset(
    {"session", "mission", "provider", "model", "daily"}
)

# Record statuses returned by record_usage.
OK = "OK"
WARN = "WARN"
BLOCK = "BLOCK"


@dataclass
class ScopeUsage:
    """Accumulated usage for a single (scope, key)."""

    scope: str
    key: str
    tokens: int = 0
    cost_usd: float = 0.0  # only accumulated for non-None cost_usd inputs

    def add(self, tokens: int, cost_usd: float | None) -> None:
        self.tokens += tokens
        if cost_usd is not None:
            self.cost_usd += cost_usd


class TokenGovernor:
    """Five-layer token/cost budget ledger with soft/hard enforcement."""

    def __init__(self, warn_ratio: float = 0.8) -> None:
        if not 0.0 < warn_ratio <= 1.0:
            raise ValueError("warn_ratio must be in (0.0, 1.0]")
        self.warn_ratio = warn_ratio
        self._budgets: dict[tuple[str, str], int | None] = {}
        self._usage: dict[tuple[str, str], ScopeUsage] = {}

    # ── helpers ───────────────────────────────────────────────────────────

    def _scope_key(self, scope: str, key: str) -> tuple[str, str]:
        scope = scope.lower()
        if scope not in SCOPES:
            raise ValueError(f"unknown budget scope: {scope!r}")
        if scope == "daily":
            # daily is a single global scope; key is normalised to a constant.
            key = "daily"
        return (scope, key)

    def _get_usage(self, scope: str, key: str) -> ScopeUsage:
        sk = self._scope_key(scope, key)
        if sk not in self._usage:
            self._usage[sk] = ScopeUsage(scope=sk[0], key=sk[1])
        return self._usage[sk]

    def _limit(self, scope: str, key: str) -> int | None:
        return self._budgets.get(self._scope_key(scope, key))

    @staticmethod
    def _status(tokens: int, limit: int | None, warn_ratio: float) -> str:
        if limit is None:
            return OK
        if tokens > limit:
            return BLOCK
        if tokens >= int(limit * warn_ratio):
            return WARN
        return OK

    # ── public API ────────────────────────────────────────────────────────

    def set_budget(self, scope: str, key: str, limit: int | None) -> None:
        """Set a token budget for (scope, key). ``limit=None`` means unlimited."""
        sk = self._scope_key(scope, key)
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise ValueError("limit must be a non-negative int or None")
        self._budgets[sk] = limit

    def record_usage(
        self,
        scope: str,
        key: str,
        tokens: int,
        cost_usd: float | None = None,
    ) -> str:
        """Record usage and return OK / WARN / BLOCK.

        Tokens are always counted. ``cost_usd=None`` counts tokens only and
        leaves cost untouched (never records a fake 0.0 cost).
        """
        if not isinstance(tokens, int) or tokens < 0:
            raise ValueError("tokens must be a non-negative int")
        usage = self._get_usage(scope, key)
        usage.add(tokens, cost_usd)
        return self._status(usage.tokens, self._limit(scope, key), self.warn_ratio)

    def check(self, scope: str, key: str) -> dict:
        """Return current usage + budget status for (scope, key)."""
        sk = self._scope_key(scope, key)
        usage = self._get_usage(scope, key)
        limit = self._limit(scope, key)
        remaining = None if limit is None else max(0, limit - usage.tokens)
        return {
            "scope": sk[0],
            "key": sk[1],
            "limit_tokens": limit,
            "used_tokens": usage.tokens,
            "used_cost_usd": usage.cost_usd,
            "remaining_tokens": remaining,
            "status": self._status(usage.tokens, limit, self.warn_ratio),
        }

    def reset_daily(self) -> int:
        """Clear all usage under the daily scope. Returns entries cleared."""
        cleared = 0
        for sk in [k for k in self._usage if k[0] == "daily"]:
            del self._usage[sk]
            cleared += 1
        return cleared

    def snapshot(self) -> dict:
        """Return a summary of every tracked (scope, key) usage."""
        return {
            f"{scope}:{key}": {
                "limit_tokens": self._budgets.get((scope, key)),
                "used_tokens": usage.tokens,
                "used_cost_usd": usage.cost_usd,
            }
            for (scope, key), usage in sorted(self._usage.items())
        }
