"""CAB-01 regression cases for the remote PR #62 KernelExecutionGuard.

Evidence: kernel_boundary.py blob 05a1249df8fdf0854c7d9f59888181f7f4f4258d.
These xfails are *open defects*, not passing security controls. Remove xfail
only after fixing the trusted issuance/guard boundary and re-running tests.
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


@pytest.mark.xfail(strict=True, reason="Open finding: guard.admit checks caller-controlled booleans, not trusted issuer")
def test_guard_rejects_untrusted_caller_constructed_context() -> None:
    guard = KernelExecutionGuard()
    with pytest.raises(KernelBoundaryViolation):
        guard.admit(_all_true_context())


def test_guard_rejects_mutated_context_after_admission() -> None:
    guard = KernelExecutionGuard()
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
