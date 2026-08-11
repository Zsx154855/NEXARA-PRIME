"""State Transition Validator — enforces legal state transitions
for the NEXARA Agent Mission Lifecycle Manager 10-state FSM.

Part of NEXARA Agent Mission Lifecycle Manager Phase 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


# ── States ──

CREATED = "CREATED"
ASSIGNED = "ASSIGNED"
PLANNING = "PLANNING"
RUNNING = "RUNNING"
WAITING_REVIEW = "WAITING_REVIEW"
VERIFYING = "VERIFYING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
BLOCKED = "BLOCKED"
CANCELLED = "CANCELLED"

TERMINAL_STATES: frozenset[str] = frozenset({COMPLETED, FAILED, CANCELLED})
ALL_STATES: frozenset[str] = frozenset({
    CREATED, ASSIGNED, PLANNING, RUNNING, WAITING_REVIEW,
    VERIFYING, COMPLETED, FAILED, BLOCKED, CANCELLED,
})

# ── Transition Matrix ──

TRANSITIONS: dict[str, frozenset[str]] = {
    CREATED:        frozenset({ASSIGNED, FAILED, CANCELLED}),
    ASSIGNED:       frozenset({PLANNING, BLOCKED, CANCELLED}),
    PLANNING:       frozenset({RUNNING, BLOCKED, CANCELLED}),
    RUNNING:        frozenset({WAITING_REVIEW, VERIFYING, FAILED, BLOCKED}),
    WAITING_REVIEW: frozenset({VERIFYING, RUNNING, BLOCKED, FAILED, CANCELLED}),
    VERIFYING:      frozenset({COMPLETED, RUNNING, FAILED, BLOCKED, CANCELLED}),
    COMPLETED:      frozenset(),   # terminal
    FAILED:         frozenset(),   # terminal
    CANCELLED:      frozenset(),   # terminal
    BLOCKED:        frozenset({ASSIGNED, PLANNING, RUNNING, CANCELLED, FAILED}),
}

# ── Actor permissions for transitions ──

ACTOR_TRANSITIONS: dict[str, frozenset[tuple[str, str]]] = {
    "CTO":          frozenset({(s, CANCELLED) for s in [CREATED, ASSIGNED, PLANNING, RUNNING, WAITING_REVIEW, VERIFYING, BLOCKED]}),
    "COORDINATOR":  frozenset({
        (CREATED, ASSIGNED), (CREATED, FAILED),
        (ASSIGNED, BLOCKED),
        (PLANNING, RUNNING),
        (RUNNING, WAITING_REVIEW), (RUNNING, VERIFYING),
        (WAITING_REVIEW, BLOCKED),
        (VERIFYING, COMPLETED), (VERIFYING, RUNNING),
        (VERIFYING, FAILED),
        (BLOCKED, ASSIGNED), (BLOCKED, PLANNING), (BLOCKED, RUNNING),
    }),
    "WRITER":       frozenset({
        (ASSIGNED, PLANNING), (RUNNING, BLOCKED),
    }),
    "REVIEWER":     frozenset({
        (PLANNING, BLOCKED), (WAITING_REVIEW, VERIFYING),
        (WAITING_REVIEW, RUNNING), (VERIFYING, BLOCKED),
    }),
    "SYSTEM":       frozenset({
        (RUNNING, FAILED), (WAITING_REVIEW, FAILED),
        (BLOCKED, FAILED),
    }),
    "VERIFIER":     frozenset({
        (VERIFYING, COMPLETED), (VERIFYING, RUNNING),
        (VERIFYING, FAILED), (VERIFYING, BLOCKED),
    }),
}


def validate_transition(
    current: str,
    target: str,
    actor: str,
    *,
    evidence_ids: list[str] | None = None,
) -> ValidationResult:
    """Validate a state transition.

    Checks:
      1. current and target are valid states.
      2. target is a legal transition from current.
      3. current is not a terminal state.
      4. actor is authorized for this transition.
      5. evidence is provided for transitions that require it.

    Args:
        current: Current mission state.
        target: Target mission state.
        actor: Actor performing the transition.
        evidence_ids: Evidence artifacts backing this transition.

    Returns:
        ValidationResult — valid=True iff transition is legal.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    evidence_ids = evidence_ids or []

    cur = str(current).strip().upper()
    tgt = str(target).strip().upper()
    act = str(actor).strip().upper()

    # Check 1: valid states
    if cur not in ALL_STATES:
        errors.append(ValidationError(
            code="INVALID_CURRENT_STATE",
            message=f"'{cur}' is not a valid lifecycle state. Must be one of {sorted(ALL_STATES)}.",
            detail={"current": cur},
        ))
    if tgt not in ALL_STATES:
        errors.append(ValidationError(
            code="INVALID_TARGET_STATE",
            message=f"'{tgt}' is not a valid lifecycle state. Must be one of {sorted(ALL_STATES)}.",
            detail={"target": tgt},
        ))

    if errors:
        return ValidationResult(valid=False, errors=errors)

    # Check 2: terminal state
    if cur in TERMINAL_STATES:
        errors.append(ValidationError(
            code="TERMINAL_STATE_TRANSITION",
            message=f"Cannot transition from terminal state '{cur}'. Terminal states have no outgoing transitions.",
            detail={"current": cur, "target": tgt},
        ))

    # Check 3: legal transition
    allowed = TRANSITIONS.get(cur, frozenset())
    if tgt not in allowed:
        errors.append(ValidationError(
            code="ILLEGAL_TRANSITION",
            message=f"Transition '{cur} → {tgt}' is not legal. Allowed from '{cur}': {sorted(allowed)}.",
            detail={"current": cur, "target": tgt, "allowed": sorted(allowed)},
        ))

    # Check 4: actor authorization
    actor_allowed = ACTOR_TRANSITIONS.get(act, frozenset())
    if (cur, tgt) not in actor_allowed:
        errors.append(ValidationError(
            code="UNAUTHORIZED_ACTOR",
            message=f"Actor '{act}' is not authorized for transition '{cur} → {tgt}'.",
            detail={"actor": act, "current": cur, "target": tgt},
        ))

    # Check 5: evidence for non-trivial transitions
    evidence_required_transitions = {
        (RUNNING, WAITING_REVIEW), (RUNNING, VERIFYING),
        (WAITING_REVIEW, VERIFYING), (VERIFYING, COMPLETED),
    }
    if (cur, tgt) in evidence_required_transitions and not evidence_ids:
        warnings.append(ValidationError(
            code="EVIDENCE_RECOMMENDED",
            message=f"Transition '{cur} → {tgt}' should be backed by evidence artifacts.",
            detail={"current": cur, "target": tgt},
        ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_happy_path(states: list[str]) -> ValidationResult:
    """Validate a complete state sequence as a legal happy path."""
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    for i in range(len(states) - 1):
        cur, tgt = states[i], states[i + 1]
        r = validate_transition(cur, tgt, "COORDINATOR")
        if not r.valid:
            errors.extend(r.errors)
        warnings.extend(r.warnings)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
