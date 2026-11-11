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


def test_backward_compatible_standalone_guard():
    """Legacy direct Guard users keep old structural contract, NOT issuer proof."""
    guard = KernelExecutionGuard()
    guard.admit(_admitted())
    assert guard.assert_admitted("mission-one").mission_id == "mission-one"
