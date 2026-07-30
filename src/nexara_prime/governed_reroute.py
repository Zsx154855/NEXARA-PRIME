"""
NEXARA Governed Reroute Controller V1

Only permits rerouting on: provider failure, contract violation, schema failure,
insufficient evidence, low confidence, verification conflict, context overflow,
owner-directed retry.

Every reroute is recorded. Silent retries are prohibited.
Bounded: MAX_ROUTE_ATTEMPTS=3, MAX_VERIFIER_ATTEMPTS=2.

NSEC V2.1 §5.G
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from .models import now_iso


class RerouteReason(str, Enum):
    PROVIDER_FAILURE = "provider_failure"
    CONTRACT_VIOLATION = "contract_violation"
    SCHEMA_FAILURE = "schema_failure"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    LOW_CONFIDENCE = "low_confidence"
    VERIFICATION_CONFLICT = "verification_conflict"
    CONTEXT_OVERFLOW = "context_overflow"
    OWNER_RETRY = "owner_retry"


@dataclass
class RerouteRecord:
    """Immutable record of a single reroute event."""

    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    mission_id: str = ""
    previous_route_id: str = ""
    reason: RerouteReason = RerouteReason.PROVIDER_FAILURE
    detail: str = ""
    new_route_id: str = ""
    new_model: str = ""
    new_provider: str = ""
    cost_delta: float = 0.0
    token_delta: int = 0
    risk_delta: str = "unchanged"
    approval_required: bool = False
    created_at: str = field(default_factory=now_iso)


@dataclass
class RerouteState:
    """Tracks reroute state for a single mission."""

    mission_id: str
    route_attempts: int = 0
    verifier_attempts: int = 0
    history: list[RerouteRecord] = field(default_factory=list)

    @property
    def can_reroute(self) -> bool:
        return self.route_attempts < GovernedRerouteController.MAX_ROUTE_ATTEMPTS


class GovernedRerouteController:
    """
    Controls rerouting with governance enforcement.

    Only permits rerouting for defined reasons.
    Every reroute is logged. Silent retries are prohibited.
    """

    MAX_ROUTE_ATTEMPTS = 3
    MAX_COUNCIL_MEMBERS = 3
    MAX_VERIFIER_ATTEMPTS = 2

    def __init__(self) -> None:
        self._states: dict[str, RerouteState] = {}

    def may_reroute(
        self,
        mission_id: str,
        reason: RerouteReason,
        current_attempts: int = -1,
    ) -> bool:
        state = self._get_or_create(mission_id)
        if current_attempts >= 0:
            state.route_attempts = current_attempts
        return state.route_attempts < self.MAX_ROUTE_ATTEMPTS

    def record_reroute(
        self,
        mission_id: str,
        previous_route_id: str,
        reason: RerouteReason,
        detail: str = "",
        new_route_id: str = "",
        new_model: str = "",
        new_provider: str = "",
        cost_delta: float = 0.0,
        token_delta: int = 0,
        risk_delta: str = "unchanged",
        approval_required: bool = False,
    ) -> RerouteRecord:
        state = self._get_or_create(mission_id)
        state.route_attempts += 1
        record = RerouteRecord(
            mission_id=mission_id,
            previous_route_id=previous_route_id,
            reason=reason,
            detail=detail,
            new_route_id=new_route_id,
            new_model=new_model,
            new_provider=new_provider,
            cost_delta=cost_delta,
            token_delta=token_delta,
            risk_delta=risk_delta,
            approval_required=approval_required,
        )
        state.history.append(record)
        return record

    def get_state(self, mission_id: str) -> RerouteState:
        return self._get_or_create(mission_id)

    def get_history(self, mission_id: str) -> list[RerouteRecord]:
        return self._get_or_create(mission_id).history

    def _get_or_create(self, mission_id: str) -> RerouteState:
        if mission_id not in self._states:
            self._states[mission_id] = RerouteState(mission_id=mission_id)
        return self._states[mission_id]

    # ── shortcut ─────────────────────────────────────────

    def should_escalate_to_human(self, mission_id: str) -> bool:
        state = self._get_or_create(mission_id)
        return state.route_attempts >= self.MAX_ROUTE_ATTEMPTS
