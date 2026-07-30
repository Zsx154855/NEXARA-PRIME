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

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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


# Valid reason set for validation
_VALID_REASONS: frozenset[str] = frozenset(r.value for r in RerouteReason)


@dataclass(frozen=True)
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
    idempotency_key: str = ""
    created_at: str = field(default_factory=now_iso)


@dataclass
class RerouteState:
    """Tracks reroute state for a single mission."""

    mission_id: str
    route_attempts: int = 0
    verifier_attempts: int = 0
    history: list[RerouteRecord] = field(default_factory=list)
    _idempotency_keys: set[str] = field(default_factory=set)

    @property
    def can_reroute(self) -> bool:
        return self.route_attempts < GovernedRerouteController.MAX_ROUTE_ATTEMPTS

    @property
    def can_verify(self) -> bool:
        return self.verifier_attempts < GovernedRerouteController.MAX_VERIFIER_ATTEMPTS


class GovernedRerouteController:
    """
    Controls rerouting with governance enforcement.

    Only permits rerouting for defined reasons.
    Every reroute is logged. Silent retries are prohibited.
    State is thread-safe and supports persistence.
    """

    MAX_ROUTE_ATTEMPTS = 3
    MAX_COUNCIL_MEMBERS = 3
    MAX_VERIFIER_ATTEMPTS = 2

    def __init__(self, load_state: dict | None = None) -> None:
        self._states: dict[str, RerouteState] = {}
        self._lock = threading.Lock()
        if load_state:
            self._restore_state(load_state)

    # ── persistence ───────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise full controller state."""
        with self._lock:
            result: dict[str, Any] = {}
            for mid, state in self._states.items():
                result[mid] = {
                    "mission_id": state.mission_id,
                    "route_attempts": state.route_attempts,
                    "verifier_attempts": state.verifier_attempts,
                    "history": [
                        {
                            "record_id": r.record_id,
                            "previous_route_id": r.previous_route_id,
                            "reason": r.reason.value,
                            "detail": r.detail,
                            "new_route_id": r.new_route_id,
                            "new_model": r.new_model,
                            "new_provider": r.new_provider,
                            "cost_delta": r.cost_delta,
                            "token_delta": r.token_delta,
                            "risk_delta": r.risk_delta,
                            "approval_required": r.approval_required,
                            "idempotency_key": r.idempotency_key,
                            "created_at": r.created_at,
                        }
                        for r in state.history
                    ],
                    "idempotency_keys": list(state._idempotency_keys),
                }
            return result

    def _restore_state(self, data: dict) -> None:
        """Restore from persisted state."""
        with self._lock:
            for mid, sd in data.items():
                state = RerouteState(
                    mission_id=sd.get("mission_id", mid),
                    route_attempts=sd.get("route_attempts", 0),
                    verifier_attempts=sd.get("verifier_attempts", 0),
                    _idempotency_keys=set(sd.get("idempotency_keys", [])),
                )
                for rd in sd.get("history", []):
                    reason_str = rd.get("reason", "provider_failure")
                    try:
                        reason = RerouteReason(reason_str)
                    except ValueError:
                        reason = RerouteReason.PROVIDER_FAILURE
                    state.history.append(RerouteRecord(
                        record_id=rd.get("record_id", ""),
                        previous_route_id=rd.get("previous_route_id", ""),
                        reason=reason,
                        detail=rd.get("detail", ""),
                        new_route_id=rd.get("new_route_id", ""),
                        new_model=rd.get("new_model", ""),
                        new_provider=rd.get("new_provider", ""),
                        cost_delta=rd.get("cost_delta", 0.0),
                        token_delta=rd.get("token_delta", 0),
                        risk_delta=rd.get("risk_delta", "unchanged"),
                        approval_required=rd.get("approval_required", False),
                        idempotency_key=rd.get("idempotency_key", ""),
                        created_at=rd.get("created_at", ""),
                    ))
                self._states[mid] = state

    # ── reroute gating ────────────────────────────────────

    def may_reroute(
        self,
        mission_id: str,
        reason: RerouteReason,
    ) -> bool:
        """Check if reroute is permitted. Monotonic only — never rewinds."""
        # Validate reason
        if reason.value not in _VALID_REASONS:
            return False
        with self._lock:
            state = self._get_or_create(mission_id)
            return state.route_attempts < self.MAX_ROUTE_ATTEMPTS

    def may_verify(self, mission_id: str) -> bool:
        """Check if verifier retry is permitted. Enforces MAX_VERIFIER_ATTEMPTS."""
        with self._lock:
            state = self._get_or_create(mission_id)
            return state.verifier_attempts < self.MAX_VERIFIER_ATTEMPTS

    def record_verifier_attempt(self, mission_id: str) -> bool:
        """Atomically increment verifier attempt. Returns True if within limit."""
        with self._lock:
            state = self._get_or_create(mission_id)
            if state.verifier_attempts >= self.MAX_VERIFIER_ATTEMPTS:
                return False
            state.verifier_attempts += 1
            return True

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
        idempotency_key: str = "",
    ) -> RerouteRecord:
        """Atomically check limit, increment, and record.
        Idempotent: same idempotency_key replays existing record."""
        # Validate reason
        if reason.value not in _VALID_REASONS:
            raise ValueError(f"Unsupported reroute reason: {reason.value}")

        with self._lock:
            state = self._get_or_create(mission_id)

            # Idempotency: if key exists, return existing record
            if idempotency_key and idempotency_key in state._idempotency_keys:
                for r in state.history:
                    if r.idempotency_key == idempotency_key:
                        return r

            # Atomic: check limit before incrementing
            if state.route_attempts >= self.MAX_ROUTE_ATTEMPTS:
                raise RuntimeError(
                    f"Reroute limit exceeded for mission {mission_id} "
                    f"({state.route_attempts}/{self.MAX_ROUTE_ATTEMPTS})"
                )

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
                idempotency_key=idempotency_key,
            )
            if idempotency_key:
                state._idempotency_keys.add(idempotency_key)
            state.history.append(record)
            return record

    def get_state(self, mission_id: str) -> RerouteState:
        with self._lock:
            return self._get_or_create(mission_id)

    def get_history(self, mission_id: str) -> list[RerouteRecord]:
        """Return immutable snapshot of reroute history."""
        with self._lock:
            return list(self._get_or_create(mission_id).history)

    def _get_or_create(self, mission_id: str) -> RerouteState:
        # Caller must hold _lock
        if mission_id not in self._states:
            self._states[mission_id] = RerouteState(mission_id=mission_id)
        return self._states[mission_id]

    # ── escalation ────────────────────────────────────────

    def should_escalate_to_human(self, mission_id: str) -> bool:
        with self._lock:
            state = self._get_or_create(mission_id)
            return (
                state.route_attempts >= self.MAX_ROUTE_ATTEMPTS
                or state.verifier_attempts >= self.MAX_VERIFIER_ATTEMPTS
            )
