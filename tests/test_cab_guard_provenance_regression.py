"""CAB-01 regression cases for the remote PR #62 KernelExecutionGuard.

Evidence: kernel_boundary.py blob 05a1249df8fdf0854c7d9f59888181f7f4f4258d.
This test suite distinguishes explicit default-deny from genuine host identity.
A test-injected lambda is only an isolated fixture, never an OS identity proof.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from nexara_prime.kernel_boundary import (
    KernelAdmissionContext,
    KernelBoundaryViolation,
    KernelExecutionGuard,
)


def _all_true_context() -> KernelAdmissionContext:
    # No signed issuer, persisted record, or authenticated host is supplied.
    return KernelAdmissionContext(
        mission_id="mission-untrusted",
        caller="untrusted",
        contract_verified=True,
        authority_verified=True,
        state_valid=True,
        governance_approved=True,
        evidence_chain_initialized=True,
    )


def test_guard_rejects_untrusted_caller_constructed_context() -> None:
    guard = KernelExecutionGuard()
    with pytest.raises(KernelBoundaryViolation):
        guard.admit(_all_true_context())


def test_guard_rejects_mutated_context_after_admission() -> None:
    guard = KernelExecutionGuard(_live_admission_validator=lambda _ctx: True)
    ctx = _all_true_context()
    guard.admit(ctx)
    try:
        ctx.authority_verified = False
    except (AttributeError, FrozenInstanceError):
        # A future immutable context is an acceptable mitigation for mutation.
        return
    with pytest.raises(KernelBoundaryViolation):
        guard.assert_admitted(ctx.mission_id)


def test_guard_blocks_when_no_context_was_admitted() -> None:
    guard = KernelExecutionGuard()
    with pytest.raises(KernelBoundaryViolation):
        guard.assert_admitted("mission-untrusted")


@pytest.mark.parametrize(
    "field_name, replacement",
    [
        ("mission_id", "other-mission"),
        ("caller", "other-caller"),
        ("contract_verified", False),
        ("authority_verified", False),
        ("state_valid", False),
        ("governance_approved", False),
        ("evidence_chain_initialized", False),
    ],
)
def test_admission_critical_fields_are_frozen(field_name, replacement) -> None:
    """Normal attribute assignment must not change an admitted decision."""
    ctx = _all_true_context()
    with pytest.raises(FrozenInstanceError):
        setattr(ctx, field_name, replacement)


def test_guard_revalidates_even_if_frozen_protection_is_bypassed() -> None:
    """A frozen dataclass is not a Python process security boundary."""
    guard = KernelExecutionGuard(_live_admission_validator=lambda _ctx: True)
    ctx = _all_true_context()
    guard.admit(ctx)
    object.__setattr__(ctx, "authority_verified", False)
    with pytest.raises(KernelBoundaryViolation):
        guard.assert_admitted(ctx.mission_id)
