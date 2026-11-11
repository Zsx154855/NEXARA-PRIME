"""Execution-time CAB admission freshness; no DB, tools, or model calls.

This tests the exact production KernelExecutionGuard class. A non-None live
checker must return literal True at *every* execution boundary. These tests
alone do not prove trusted host issuer authentication or Runtime wiring.
"""
from __future__ import annotations

import pytest

from nexara_prime.kernel_boundary import (
    ExecutionBoundaryViolation,
    KernelAdmissionContext,
    KernelExecutionGuard,
)


def _admitted(mission_id: str = "mission-one") -> KernelAdmissionContext:
    return KernelAdmissionContext(
        mission_id=mission_id,
        caller="host-fixture",
        contract_verified=True,
        authority_verified=True,
        state_valid=True,
        governance_approved=True,
        evidence_chain_initialized=True,
    )


def test_live_authorization_allows_valid_context():
    guard = KernelExecutionGuard(_live_admission_validator=lambda ctx: True)
    guard.admit(_admitted())
    assert guard.assert_admitted("mission-one").mission_id == "mission-one"


def test_live_revocation_is_denied_and_clears_old_context():
    live = {"ok": True}
    guard = KernelExecutionGuard(
        _live_admission_validator=lambda ctx: live["ok"]
    )
    guard.admit(_admitted())
    assert guard.assert_admitted("mission-one")
    live["ok"] = False
    with pytest.raises(ExecutionBoundaryViolation, match="no longer valid"):
        guard.assert_admitted("mission-one")
    with pytest.raises(ExecutionBoundaryViolation, match="No kernel admission"):
        guard.assert_admitted("mission-one")


def test_live_store_failure_denied_and_context_cleared():
    def broken_store(_ctx):
        raise RuntimeError("simulated DB lookup failure")

    guard = KernelExecutionGuard(_live_admission_validator=broken_store)
    guard.admit(_admitted())
    with pytest.raises(ExecutionBoundaryViolation, match="freshness check failed"):
        guard.assert_admitted("mission-one")
    with pytest.raises(ExecutionBoundaryViolation, match="No kernel admission"):
        guard.assert_admitted("mission-one")


@pytest.mark.parametrize("improper_value", ["yes", 1, object(), None])
def test_live_checker_rejects_truthy_non_boolean_values(improper_value):
    guard = KernelExecutionGuard(
        _live_admission_validator=lambda _ctx: improper_value
    )
    guard.admit(_admitted())
    with pytest.raises(ExecutionBoundaryViolation, match="no longer valid"):
        guard.assert_admitted("mission-one")


def test_cross_mission_reuse_stays_denied():
    guard = KernelExecutionGuard(_live_admission_validator=lambda ctx: True)
    guard.admit(_admitted())
    with pytest.raises(ExecutionBoundaryViolation, match="does not match"):
        guard.assert_admitted("mission-two")


def test_standalone_guard_requires_explicit_live_validator():
    """A constructed all-True context alone cannot grant execution authority."""
    guard = KernelExecutionGuard()
    with pytest.raises(ExecutionBoundaryViolation, match="Trusted issuer validator required"):
        guard.admit(_admitted())


def test_mutated_gate_is_denied_and_cleared():
    guard = KernelExecutionGuard(_live_admission_validator=lambda ctx: True)
    context = _admitted()
    guard.admit(context)
    # Frozen dataclass is not a Python process privilege boundary.
    object.__setattr__(context, "authority_verified", False)
    from nexara_prime.kernel_boundary import KernelBoundaryViolation
    with pytest.raises(KernelBoundaryViolation, match="incomplete"):
        guard.assert_admitted("mission-one")
    with pytest.raises(ExecutionBoundaryViolation, match="No kernel admission"):
        guard.assert_admitted("mission-one")
