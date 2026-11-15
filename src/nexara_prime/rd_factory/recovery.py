"""Restart, timeout and zombie-lease recovery for the factory ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .ledger import TaskLedger, utc_now


@dataclass(frozen=True)
class RecoveryReport:
    requeued: list[str]
    pending: list[str]
    in_flight: list[str]

    def as_dict(self) -> dict:
        return {
            "requeued": self.requeued,
            "pending": self.pending,
            "in_flight": self.in_flight,
        }


def recover(ledger: TaskLedger, now: datetime | None = None) -> RecoveryReport:
    """Reap expired leases, then report what the next claim may pick up.

    Called at the start of every worker turn, so a machine that slept through a
    lease expiry resumes from durable state instead of trusting a stale owner.
    """
    requeued = ledger.requeue_expired(now or utc_now())
    pending = [task.task_id for task in ledger.list_tasks("queued")]
    in_flight = [
        task.task_id
        for task in ledger.list_tasks()
        if task.state in ("claimed", "running", "verifying") and not task.lease_expired
    ]
    return RecoveryReport(requeued=requeued, pending=pending, in_flight=in_flight)


def resume_pending(ledger: TaskLedger) -> list[str]:
    return [task.task_id for task in ledger.list_tasks("queued")]
