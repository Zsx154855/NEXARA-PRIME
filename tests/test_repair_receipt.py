"""Isolated, deterministic unit contract for the receipt gate (not full NEXARA E2E)."""
import json

from nexara_prime.repair_receipt import validate_repair_receipt


def obj(**kw):
    return type("Record", (), kw)()


def case():
    cid = "repair-current"
    record = {
        "mission_id": "mission-1", "contract_id": cid, "failure_id": "failure-1",
        "contract_digest": "a" * 64, "attempt_number": 1,
        "tool_invocation_id": "tool-1", "tests_passed": 2, "tests_failed": 0,
        "test_exit_code": 0, "patch_applied": True, "run_id": "run-1",
        "test_command": "python -m pytest -q", "executor_id": "runner-1",
        "patch_sha256": "b" * 64, "test_log_sha256": "c" * 64,
        "base_commit": "d" * 40, "post_commit": "e" * 40,
    }
    contract = obj(contract_id=cid, failure_id="failure-1", contract_digest="a" * 64, attempt_number=1)
    result = obj(evidence_ids=["evidence-1"], tests_passed=2)
    artifact = obj(
        evidence_id="evidence-1", mission_id="mission-1", task_id=cid,
        kind="repair_execution_receipt", tool_invocation_id="tool-1",
        content=json.dumps(record),
    )
    class Store:
        def is_preverified_and_integrity_bound(self, eid):
            return eid == "evidence-1"
        def get_by_id(self, eid):
            return artifact
    return Store(), contract, result, artifact, record


def run(store, contract, result, *, check=lambda payload: True):
    return validate_repair_receipt(store, mission_id="mission-1", contract=contract,
                                  result=result, trusted_process_verify=check)


def test_valid_bound_receipt_with_separate_process_verification():
    store, contract, result, artifact, payload = case()
    assert run(store, contract, result)[0] is True


def test_missing_store():
    _, contract, result, _, _ = case()
    assert run(None, contract, result)[0] is False


def test_missing_trusted_verifier():
    store, contract, result, _, _ = case()
    assert run(store, contract, result, check=None)[1] == "repair_process_verifier_unavailable"


def test_empty_receipt():
    store, contract, result, _, _ = case()
    result.evidence_ids = []
    assert run(store, contract, result)[0] is False


def test_duplicate_receipt():
    store, contract, result, _, _ = case()
    result.evidence_ids = ["evidence-1", "evidence-1"]
    assert run(store, contract, result)[0] is False


def test_stale_receipt_contract_mismatch():
    store, contract, result, artifact, _ = case()
    contract.contract_id = "repair-other"
    assert run(store, contract, result)[1] == "repair_execution_receipt_identity_mismatch"


def test_other_mission_receipt():
    store, contract, result, artifact, _ = case()
    artifact.mission_id = "mission-other"
    assert run(store, contract, result)[0] is False


def test_missing_tool_invocation():
    store, contract, result, artifact, _ = case()
    artifact.tool_invocation_id = None
    assert run(store, contract, result)[0] is False


def test_unverified_evidence():
    _, contract, result, artifact, _ = case()
    class Store:
        def is_preverified_and_integrity_bound(self, eid):
            return False
    store = Store()
    assert run(store, contract, result)[1] == "repair_execution_receipt_unverified"


def test_forged_pass_counter():
    store, contract, result, artifact, payload = case()
    payload["tests_passed"] = 99
    artifact.content = json.dumps(payload)
    assert run(store, contract, result)[0] is False


def test_fake_test_exit_code():
    store, contract, result, artifact, payload = case()
    payload["test_exit_code"] = 3
    artifact.content = json.dumps(payload)
    assert run(store, contract, result)[0] is False


def test_reported_no_code_change():
    store, contract, result, artifact, payload = case()
    payload["post_commit"] = payload["base_commit"]
    artifact.content = json.dumps(payload)
    assert run(store, contract, result)[0] is False


def test_missing_test_log_digest():
    store, contract, result, artifact, payload = case()
    payload["test_log_sha256"] = ""
    artifact.content = json.dumps(payload)
    assert run(store, contract, result)[0] is False


def test_independent_process_verifier_rejects_claim():
    store, contract, result, _, _ = case()
    assert run(store, contract, result, check=lambda payload: False)[1] == "repair_execution_receipt_process_unverified"


def test_backend_exception_fails_closed():
    _, contract, result, _, _ = case()
    def exploding(_eid):
        raise OSError("backend unavailable")
    class Store:
        def is_preverified_and_integrity_bound(self, eid):
            return exploding(eid)
    store = Store()
    assert run(store, contract, result)[1] == "repair_execution_receipt_backend_failure"


def test_invalid_json_fails_closed():
    store, contract, result, artifact, _ = case()
    artifact.content = "{broken"
    assert run(store, contract, result)[0] is False


def test_type_spoofing_boolean_zero_fails_closed():
    store, contract, result, artifact, payload = case()
    payload["test_exit_code"] = False
    artifact.content = json.dumps(payload)
    assert run(store, contract, result)[0] is False
