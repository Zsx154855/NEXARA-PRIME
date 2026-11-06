"""Fail-closed validation of a repair executor's persisted, process-bound receipt.

The patch executor is an untrusted source of outcome claims. EvidenceStore
provides record integrity, not independent process provenance. Therefore a
separate trusted process verifier is mandatory for acceptance. The latter must
consult process/tool records NOT supplied solely by the callback under test.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")


def validate_repair_receipt(
    evidence_store: Any,
    *,
    mission_id: str,
    contract: Any,
    result: Any,
    trusted_process_verify: Callable[[dict[str, Any]], bool] | None,
) -> tuple[bool, str]:
    """Validate store record + identity + process evidence; never accept callback alone.

    `trusted_process_verify` MUST be implemented by the execution authority,
    not the worker/callback. A verifier in the same unprotected trust domain as
    the executor is not independent or cryptographically trustworthy.
    """
    if evidence_store is None:
        return False, "repair_evidence_store_unavailable"
    if trusted_process_verify is None:
        return False, "repair_process_verifier_unavailable"
    evidence_ids = result.evidence_ids
    if not isinstance(evidence_ids, list) or len(evidence_ids) != 1:
        return False, "repair_execution_receipt_missing_or_ambiguous"
    evidence_id = evidence_ids[0]
    if not isinstance(evidence_id, str) or not evidence_id:
        return False, "repair_execution_receipt_id_invalid"
    try:
        if evidence_store.is_preverified_and_integrity_bound(evidence_id) is not True:
            return False, "repair_execution_receipt_unverified"
        artifact = evidence_store.get_by_id(evidence_id)
        if (
            artifact.evidence_id != evidence_id
            or artifact.mission_id != mission_id
            or artifact.task_id != contract.contract_id
            or artifact.kind != "repair_execution_receipt"
            or not isinstance(artifact.tool_invocation_id, str)
            or not artifact.tool_invocation_id
        ):
            return False, "repair_execution_receipt_identity_mismatch"
        payload = json.loads(artifact.content)
        if not isinstance(payload, dict):
            return False, "repair_execution_receipt_invalid_payload"
        expected = {
            "mission_id": mission_id,
            "contract_id": contract.contract_id,
            "failure_id": contract.failure_id,
            "contract_digest": contract.contract_digest,
            "attempt_number": contract.attempt_number,
            "tool_invocation_id": artifact.tool_invocation_id,
            "tests_passed": result.tests_passed,
            "tests_failed": 0,
            "test_exit_code": 0,
            "patch_applied": True,
        }
        for name, expected_value in expected.items():
            observed = payload.get(name)
            if type(observed) is not type(expected_value) or observed != expected_value:
                return False, f"repair_execution_receipt_field_mismatch:{name}"
        for name in ("run_id", "test_command", "executor_id"):
            if not isinstance(payload.get(name), str) or not payload[name].strip():
                return False, f"repair_execution_receipt_field_missing:{name}"
        for name in ("patch_sha256", "test_log_sha256"):
            value = payload.get(name)
            if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
                return False, f"repair_execution_receipt_digest_invalid:{name}"
        for name in ("base_commit", "post_commit"):
            value = payload.get(name)
            if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
                return False, f"repair_execution_receipt_commit_invalid:{name}"
        if payload["base_commit"] == payload["post_commit"]:
            return False, "repair_execution_receipt_no_code_change"
        # Only trusted host process/tool records can prove these claims.
        if trusted_process_verify(payload) is not True:
            return False, "repair_execution_receipt_process_unverified"
        return True, "repair_execution_receipt_verified"
    except (KeyError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return False, "repair_execution_receipt_invalid"
    except Exception:
        # Backend faults must never become proof of success.
        return False, "repair_execution_receipt_backend_failure"
