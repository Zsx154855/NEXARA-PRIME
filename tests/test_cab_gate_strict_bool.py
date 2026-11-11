"""Reject truthy but non-boolean CAB admission gates.

Dataclass type annotations are not runtime validation: strings such as
"false" and integer 1 previously passed the truthiness-based gate.
This test does not establish trusted issuer provenance.
"""
from __future__ import annotations

import pytest

from nexara_prime.kernel_boundary import (
    KernelAdmissionContext,
    KernelBoundaryViolation,
)


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param("false", id="string-false"),
        pytest.param("0", id="string-zero"),
        pytest.param(1, id="integer-one"),
        pytest.param(object(), id="object"),
    ],
)
@pytest.mark.parametrize(
    "gate",
    [
        "contract_verified",
        "authority_verified",
        "state_valid",
        "governance_approved",
        "evidence_chain_initialized",
    ],
)
def test_all_admission_gates_require_literal_true(gate: str, invalid: object) -> None:
    values = dict(
        mission_id="strict-bool",
        caller="untrusted",
        contract_verified=True,
        authority_verified=True,
        state_valid=True,
        governance_approved=True,
        evidence_chain_initialized=True,
    )
    values[gate] = invalid
    ctx = KernelAdmissionContext(**values)
    with pytest.raises(KernelBoundaryViolation):
        ctx.assert_complete()


def test_all_literal_true_gates_pass_structural_validation() -> None:
    ctx = KernelAdmissionContext(
        mission_id="structural-only",
        caller="untrusted",
        contract_verified=True,
        authority_verified=True,
        state_valid=True,
        governance_approved=True,
        evidence_chain_initialized=True,
    )
    ctx.assert_complete()  # Structural only: issuer provenance is still unverified.
