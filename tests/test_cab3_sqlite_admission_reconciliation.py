"""CAB-3 bridge: real SQLite record layout, not the OpenMinis stub.

These prove only storage structure / fail-closed checks. They DO NOT establish
host OS principal, approval-origin authenticity or execution ingress coverage.
"""
from __future__ import annotations

import pytest

from nexara_prime.brain.kernel import ChiefBrainKernel
from nexara_prime.db import SQLiteStore
from nexara_prime.kernel_boundary import KernelBoundaryViolation
from nexara_prime.models import now_iso

MISSION = "cab-real-storage-mission"
APPROVAL = "cab-real-storage-approval"


def _store(tmp_path, *, contract_status="approved", approval_status="approved",
           approval_mission=MISSION, has_mission=True, has_approval=True):
    store = SQLiteStore(tmp_path / "cab-3-integration.sqlite3")
    stamp = now_iso()
    if has_mission:
        store.save_record(
            MISSION, "mission",
            {
                "mission_id": MISSION,
                "contract": {
                    "contract_id": "cab-storage-contract",
                    "mission_id": MISSION,
                    "status": contract_status,
                },
            },
            stamp, MISSION,
        )
    if has_approval:
        store.save_record(
            APPROVAL, "approval",
            {"approval_id": APPROVAL, "mission_id": approval_mission,
             "status": approval_status},
            stamp, approval_mission,
        )
    return store


def _submit(store, *, trusted_authorizer=lambda mission_id, caller: True):
    return ChiefBrainKernel(
        store=store, trusted_authorizer=trusted_authorizer,
    ).submit(
        MISSION, "trusted-host-fixture",
        contract_verified=True, governance_approved=True,
        state_valid=True, evidence_initialized=True,
    )


def test_persisted_embedded_contract_is_visible_to_kernel(tmp_path):
    """Storage-layout proof only; fixture approval was not authentically issued."""
    store = _store(tmp_path)
    try:
        ctx = _submit(store)
        assert ctx.mission_id == MISSION
        assert ctx.contract_verified is True
    finally:
        store.close()


@pytest.mark.parametrize("variant", [
    "unconfigured", "absent_mission", "missing_contract",
    "unapproved_contract", "absent_approval", "wrong_mission_approval",
    "pending_approval", "consumed_approval", "false_host",
])
def test_structural_admission_deny_paths(tmp_path, variant):
    kwargs = {}
    if variant == "absent_mission":
        kwargs["has_mission"] = False
    elif variant == "missing_contract":
        kwargs["contract_status"] = None
    elif variant == "unapproved_contract":
        kwargs["contract_status"] = "validated"
    elif variant == "absent_approval":
        kwargs["has_approval"] = False
    elif variant == "wrong_mission_approval":
        kwargs["approval_mission"] = "other-mission"
    elif variant == "pending_approval":
        kwargs["approval_status"] = "pending"
    elif variant == "consumed_approval":
        kwargs["approval_status"] = "consumed"
    store = _store(tmp_path, **kwargs)
    try:
        if variant == "unconfigured":
            with pytest.raises(KernelBoundaryViolation, match="trusted_authorizer_not_configured"):
                _submit(store, trusted_authorizer=None)
        elif variant == "false_host":
            with pytest.raises(KernelBoundaryViolation, match="caller_not_authorised"):
                _submit(store, trusted_authorizer=lambda _m, _c: False)
        else:
            with pytest.raises(KernelBoundaryViolation, match="claim_not_persisted"):
                _submit(store)
    finally:
        store.close()


def test_store_absence_always_denies_even_with_host_callback():
    with pytest.raises(KernelBoundaryViolation, match="persisted_state_unavailable"):
        _submit(None)


@pytest.mark.xfail(
    strict=True,
    reason="OPEN: synthetically inserted approved record lacks ApprovalEngine origin and issuer proof",
)
def test_fabricated_approval_record_must_not_grant_authority(tmp_path):
    store = _store(tmp_path)  # self-issued approval without ApprovalEngine.request/decide
    try:
        with pytest.raises(KernelBoundaryViolation):
            _submit(store)
    finally:
        store.close()
