"""CAB-3: exercise the real SQLite + ApprovalEngine contract.

These tests use genuine pending/decision transitions, NOT hand-written
approved rows. They remain local-only tests; host principal authenticity and
runtime dispatch coverage have separate open regression cases.
"""
from __future__ import annotations

import time

import pytest

from nexara_prime.brain.kernel import ChiefBrainKernel
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.governance import ApprovalEngine
from nexara_prime.kernel_boundary import KernelBoundaryViolation
from nexara_prime.models import RiskLevel, now_iso

MISSION = "cab-real-storage-mission"


def _store(
    tmp_path,
    *,
    has_mission=True,
    contract_status="approved",
    approval_kind="approved",
    approval_mission=MISSION,
    expires_in_seconds=900,
):
    store = SQLiteStore(tmp_path / "cab-3-integration.sqlite3")
    approvals = ApprovalEngine(store, EventBus(store))
    pending_approval_id = "missing-approval"
    if approval_kind in {"approved", "pending"}:
        requested = approvals.request(
            approval_mission, "file_write_report", RiskLevel.R2,
            "Bounded test approval", ["Test-only report"], "trace-cab3",
            expires_in_seconds=expires_in_seconds,
        )
        pending_approval_id = requested.approval_id
        if approval_kind == "approved":
            approvals.decide(
                pending_approval_id, True, "fixture_operator",
                "Test harness approval", "trace-cab3",
            )
    elif approval_kind == "synthetic":
        # Deliberately bypass ApprovalEngine origin/decision events.
        pending_approval_id = "synthetic-approval"
        store.save_record(
            pending_approval_id, "approval",
            {"approval_id": pending_approval_id, "mission_id": MISSION,
             "status": "approved"}, now_iso(), MISSION,
        )
    if has_mission:
        store.save_record(
            MISSION, "mission",
            {"mission_id": MISSION, "pending_approval_id": pending_approval_id,
             "contract": {"contract_id": "cab-storage-contract",
                          "mission_id": MISSION, "status": contract_status}},
            now_iso(), MISSION,
        )
    return store, approvals


def _submit(store, approvals=None, *, authorizer=lambda mission_id, caller: True):
    return ChiefBrainKernel(
        store=store, approvals=approvals, trusted_authorizer=authorizer,
    ).submit(
        MISSION, "trusted-host-fixture",
        contract_verified=True, governance_approved=True,
        state_valid=True, evidence_initialized=True,
    )


def test_real_approval_engine_and_embedded_contract_are_accepted(tmp_path):
    """Proves persisted state + origin/transition, not OS principal identity."""
    store, approvals = _store(tmp_path)
    try:
        ctx = _submit(store, approvals)
        assert ctx.contract_verified is True
        assert ctx.mission_id == MISSION
    finally:
        store.close()


@pytest.mark.parametrize("variant", [
    "no_mission", "no_contract", "unapproved_contract", "no_approval",
    "pending_approval", "other_mission_approval", "false_authorizer",
    "missing_authorizer", "approval_store_mismatch",
])
def test_untrusted_or_missing_evidence_is_denied(tmp_path, variant):
    kwargs = {}
    if variant == "no_mission":
        kwargs["has_mission"] = False
    elif variant == "no_contract":
        kwargs["contract_status"] = None
    elif variant == "unapproved_contract":
        kwargs["contract_status"] = "validated"
    elif variant == "no_approval":
        kwargs["approval_kind"] = "absent"
    elif variant == "pending_approval":
        kwargs["approval_kind"] = "pending"
    elif variant == "other_mission_approval":
        kwargs["approval_mission"] = "some-other-mission"
    store, approvals = _store(tmp_path, **kwargs)
    try:
        if variant == "false_authorizer":
            with pytest.raises(KernelBoundaryViolation, match="caller_not_authorised"):
                _submit(store, approvals, authorizer=lambda _m, _c: False)
        elif variant == "missing_authorizer":
            with pytest.raises(KernelBoundaryViolation, match="trusted_authorizer_not_configured"):
                _submit(store, approvals, authorizer=None)
        elif variant == "approval_store_mismatch":
            other_store = SQLiteStore(tmp_path / "other.sqlite3")
            try:
                with pytest.raises(KernelBoundaryViolation, match="governance_claim_not_persisted"):
                    _submit(store, ApprovalEngine(other_store, EventBus(other_store)))
            finally:
                other_store.close()
        else:
            with pytest.raises(KernelBoundaryViolation, match="claim_not_persisted"):
                _submit(store, approvals)
    finally:
        store.close()


def test_store_absence_is_denied_even_if_authorizer_says_yes():
    with pytest.raises(KernelBoundaryViolation, match="persisted_state_unavailable"):
        _submit(None)


def test_fabricated_approved_record_without_origin_is_denied(tmp_path):
    store, approvals = _store(tmp_path, approval_kind="synthetic")
    try:
        with pytest.raises(KernelBoundaryViolation):
            _submit(store, approvals)
    finally:
        store.close()


def test_expired_genuine_approval_is_denied(tmp_path):
    store, approvals = _store(tmp_path, expires_in_seconds=1)
    try:
        time.sleep(1.2)
        with pytest.raises(KernelBoundaryViolation, match="governance_claim_not_persisted"):
            _submit(store, approvals)
    finally:
        store.close()
