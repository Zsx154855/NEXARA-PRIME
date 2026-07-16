"""Multi-strategy auto-recovery engine with backoff, circuit breaker, dead-letter."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any


class RecoveryStrategy(str, Enum):
    RETRY = "retry"
    COMPACT_CONTEXT = "compact_context"
    SWITCH_WORKER = "switch_worker"
    ISOLATED_WORKTREE = "isolated_worktree"
    ROLLBACK = "rollback"
    RESTORE_FROM_EVIDENCE = "restore_from_evidence"
    BLOCK = "block"
    ESCALATE = "escalate"


@dataclass
class RecoveryResult:
    strategy: RecoveryStrategy
    success: bool
    attempt: int
    max_attempts: int
    reason: str
    evidence_ref: str = ""
    next_action: str = ""


class RecoveryEngine:
    """Implements progressive recovery with configurable backoff and circuit breaker.

    Recovery order:
      1. RETRY current step
      2. COMPACT_CONTEXT and retry
      3. SWITCH_WORKER
      4. ISOLATED_WORKTREE
      5. ROLLBACK current change
      6. RESTORE_FROM_EVIDENCE
      7. BLOCK (dead-letter)
      8. ESCALATE to human
    """

    STRATEGIES: list[RecoveryStrategy] = [
        RecoveryStrategy.RETRY,
        RecoveryStrategy.COMPACT_CONTEXT,
        RecoveryStrategy.SWITCH_WORKER,
        RecoveryStrategy.ISOLATED_WORKTREE,
        RecoveryStrategy.ROLLBACK,
        RecoveryStrategy.RESTORE_FROM_EVIDENCE,
        RecoveryStrategy.BLOCK,
        RecoveryStrategy.ESCALATE,
    ]

    def __init__(
        self, max_retries: int = 3, base_delay_s: float = 1.0,
        max_delay_s: float = 60.0, circuit_breaker_threshold: int = 5,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self._failure_counts: dict[str, int] = {}
        self._circuit_open: set[str] = set()

    def recover(
        self, mission_id: str, failure_type: str,
        attempt: int, last_error: str = "",
    ) -> RecoveryResult:
        """Determine next recovery action based on attempt count and failure type.

        Thread 5 (Codex V11): RecoveryStrategy.BLOCK returns success=False
        so callers treat it as a terminal failure.  BLOCK is never retryable
        — missions that reach BLOCK must transition to BLOCKED, not requeue.
        """
        key = f"{mission_id}:{failure_type}"
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

        if self._failure_counts[key] >= self.circuit_breaker_threshold:
            self._circuit_open.add(key)
            return RecoveryResult(
                strategy=RecoveryStrategy.ESCALATE, success=False,
                attempt=attempt, max_attempts=self.max_retries,
                reason=f"Circuit breaker open after {self._failure_counts[key]} failures",
            )

        strategy_idx = min(attempt - 1, len(self.STRATEGIES) - 1)
        strategy = self.STRATEGIES[strategy_idx]

        if strategy == RecoveryStrategy.RETRY and attempt <= self.max_retries:
            self._backoff(attempt)
            return RecoveryResult(
                strategy=strategy, success=True, attempt=attempt,
                max_attempts=self.max_retries,
                reason=f"Retry {attempt}/{self.max_retries}: {last_error}",
            )

        # Thread 5 (Codex V11): BLOCK is a terminal strategy — it means
        # the mission is dead and must NOT be retried or requeued.
        if strategy == RecoveryStrategy.BLOCK:
            return RecoveryResult(
                strategy=strategy, success=False, attempt=attempt,
                max_attempts=self.max_retries,
                reason=f"Recovery BLOCK — terminal failure after {attempt} attempts",
            )

        if strategy == RecoveryStrategy.ESCALATE:
            return RecoveryResult(
                strategy=strategy, success=False, attempt=attempt,
                max_attempts=self.max_retries,
                reason=f"All recovery strategies exhausted for {failure_type}",
            )

        return RecoveryResult(
            strategy=strategy, success=True, attempt=attempt,
            max_attempts=self.max_retries,
            reason=f"Progressive recovery: {strategy.value} after {attempt} attempts",
        )

    def _backoff(self, attempt: int) -> None:
        delay = min(self.base_delay_s * (2 ** (attempt - 1)), self.max_delay_s)
        time.sleep(delay)

    def reset(self, mission_id: str, failure_type: str = "") -> None:
        key = f"{mission_id}:{failure_type}"
        self._failure_counts.pop(key, None)
        self._circuit_open.discard(key)

    def is_circuit_open(self, mission_id: str, failure_type: str) -> bool:
        key = f"{mission_id}:{failure_type}"
        return key in self._circuit_open

    def to_evidence(self) -> dict[str, Any]:
        return {
            "circuit_open": list(self._circuit_open),
            "failure_counts": dict(self._failure_counts),
            "max_retries": self.max_retries,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
        }
