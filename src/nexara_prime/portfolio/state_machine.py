"""Portfolio state machine — validates ProgramRecord status transitions."""
from __future__ import annotations

from nexara_prime.portfolio.models import ProgramRecord, ProgramStatus, ProgramDecision


VALID_TRANSITIONS: dict[ProgramStatus, set[ProgramStatus]] = {
    ProgramStatus.PLANNED: {
        ProgramStatus.READY, ProgramStatus.CANCELLED, ProgramStatus.ARCHIVED,
    },
    ProgramStatus.READY: {
        ProgramStatus.RUNNING, ProgramStatus.WAIT_APPROVAL,
        ProgramStatus.WAIT_RESOURCE, ProgramStatus.PLANNED,
        ProgramStatus.CANCELLED,
    },
    ProgramStatus.RUNNING: {
        ProgramStatus.WAIT_EXTERNAL, ProgramStatus.WAIT_APPROVAL,
        ProgramStatus.PAUSED, ProgramStatus.RECOVERING,
        ProgramStatus.BLOCKED, ProgramStatus.COMPLETED,
        ProgramStatus.FAILED,
    },
    ProgramStatus.WAIT_EXTERNAL: {
        ProgramStatus.READY, ProgramStatus.RUNNING,
        ProgramStatus.BLOCKED, ProgramStatus.CANCELLED,
        ProgramStatus.ARCHIVED,
    },
    ProgramStatus.WAIT_APPROVAL: {
        ProgramStatus.READY, ProgramStatus.RUNNING,
        ProgramStatus.BLOCKED, ProgramStatus.CANCELLED,
    },
    ProgramStatus.WAIT_RESOURCE: {
        ProgramStatus.READY, ProgramStatus.RUNNING,
        ProgramStatus.BLOCKED, ProgramStatus.CANCELLED,
    },
    ProgramStatus.PAUSED: {
        ProgramStatus.RUNNING, ProgramStatus.READY,
        ProgramStatus.CANCELLED, ProgramStatus.FAILED,
    },
    ProgramStatus.RECOVERING: {
        ProgramStatus.RUNNING, ProgramStatus.READY,
        ProgramStatus.BLOCKED, ProgramStatus.FAILED,
    },
    ProgramStatus.BLOCKED: {
        ProgramStatus.READY, ProgramStatus.FAILED,
        ProgramStatus.CANCELLED, ProgramStatus.ARCHIVED,
    },
    ProgramStatus.COMPLETED: {
        ProgramStatus.ARCHIVED,
    },
    ProgramStatus.CANCELLED: {
        ProgramStatus.ARCHIVED,
    },
    ProgramStatus.FAILED: {
        ProgramStatus.READY, ProgramStatus.RECOVERING,
        ProgramStatus.CANCELLED, ProgramStatus.ARCHIVED,
    },
    ProgramStatus.ARCHIVED: set(),
}


class PortfolioStateMachine:
    """Validates and records program state transitions."""

    def transition(
        self,
        program: ProgramRecord,
        target: ProgramStatus,
        decision: ProgramDecision | None = None,
    ) -> ProgramRecord:
        """Transition a program to a new status, validating legality.

        Returns the updated program.  Raises ValueError for illegal transitions.
        """
        allowed = VALID_TRANSITIONS.get(program.status, set())
        if target not in allowed:
            raise ValueError(
                f"Illegal program transition: {program.status.value} → {target.value}"
            )
        program.status = target
        if decision:
            program.metadata.setdefault("decisions", []).append(
                {
                    "decision_id": decision.decision_id,
                    "reason": decision.reason,
                    "from_status": str(program.status.value),
                    "to_status": target.value,
                }
            )
        return program

    @staticmethod
    def can_transition(current: ProgramStatus, target: ProgramStatus) -> bool:
        return target in VALID_TRANSITIONS.get(current, set())
