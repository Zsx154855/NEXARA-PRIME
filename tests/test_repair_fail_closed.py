"""Regression: automated repair must fail closed without a real executor.

A callback in these tests is a deterministic test double. Passing these
contract tests does not prove that a production patch/tool was executed.
"""

from nexara_prime.repair_loop import RepairLoop, RepairResult, RepairStatus

TRACE = 'File "example.py", line 4\n    assert actual == expected'


def _failure(loop):
    return loop.detect_failure(
        "mission-unit-test", "AssertionError: mismatched value",
        traceback=TRACE, component="unit-test",
    )


def _callback_result(contract, *, success=True, applied=True, passed=1,
                     failed=0, weakened=None):
    return RepairResult(
        contract_id=contract.contract_id, success=success,
        patch_applied=applied, tests_passed=passed, tests_failed=failed,
        tests_weakened=weakened or [],
    )


def test_missing_executor_does_not_fabricate_patch_or_tests():
    loop = RepairLoop()
    result = loop.repair(
        "mission-unit-test", "AssertionError: mismatched value", traceback=TRACE,
    )
    assert not result.success
    assert result.status is RepairStatus.FAILED
    assert result.error == "patch_executor_unavailable"
    assert not result.patch_applied
    assert result.tests_passed == 0
    assert result.tests_failed == 0
    assert loop.stats()["resolved"] == 0
    assert len(loop.get_history()) == 3  # detection, analysis, failed attempt


def test_missing_executor_does_not_consume_retry_budget():
    loop = RepairLoop()
    failure = _failure(loop)
    result = loop.attempt_repair(failure.failure_id)
    assert not result.success
    assert failure.retry_count == 0
    assert result.error == "patch_executor_unavailable"


def test_executor_reports_unapplied_patch():
    loop = RepairLoop()
    fid = _failure(loop).failure_id
    result = loop.attempt_repair(
        fid, apply_patch_fn=lambda c: _callback_result(c, applied=False),
    )
    assert not result.success
    assert result.error == "patch_application_unverified"
    assert not result.patch_applied


def test_executor_reports_no_passing_tests():
    loop = RepairLoop()
    fid = _failure(loop).failure_id
    result = loop.attempt_repair(
        fid, apply_patch_fn=lambda c: _callback_result(c, passed=0),
    )
    assert not result.success
    assert result.patch_applied
    assert result.tests_passed == 0
    assert result.error == "patch_verification_missing"


def test_executor_reports_failed_tests():
    loop = RepairLoop()
    fid = _failure(loop).failure_id
    result = loop.attempt_repair(
        fid, apply_patch_fn=lambda c: _callback_result(c, failed=2),
    )
    assert not result.success
    assert result.tests_failed == 2
    assert result.error == "patch_verification_failed"


def test_executor_reports_weakened_tests():
    loop = RepairLoop()
    fid = _failure(loop).failure_id
    result = loop.attempt_repair(
        fid, apply_patch_fn=lambda c: _callback_result(
            c, weakened=["removed_regression_case"],
        ),
    )
    assert not result.success
    assert result.tests_weakened == ["removed_regression_case"]
    assert result.error == "tests_weakened"


def test_executor_failure_is_not_accepted():
    loop = RepairLoop()
    fid = _failure(loop).failure_id
    result = loop.attempt_repair(
        fid, apply_patch_fn=lambda c: _callback_result(c, success=False),
    )
    assert not result.success
    assert result.error == "patch_executor_reported_failure"


def test_callback_contract_can_accept_verified_test_double():
    loop = RepairLoop()
    result = loop.repair(
        "mission-unit-test", "AssertionError: mismatched value", traceback=TRACE,
        apply_patch_fn=lambda c: _callback_result(c, passed=2),
    )
    assert result.success
    assert result.status is RepairStatus.RESOLVED
    assert result.patch_applied
    assert result.tests_passed == 2


def test_executor_does_not_leak_to_later_mission():
    loop = RepairLoop()
    first = loop.repair(
        "mission-1", "AssertionError: mismatch", traceback=TRACE,
        apply_patch_fn=lambda c: _callback_result(c),
    )
    second = loop.repair(
        "mission-2", "AssertionError: mismatch", traceback=TRACE,
    )
    assert first.success
    assert not second.success
    assert second.error == "patch_executor_unavailable"


def test_executor_exception_does_not_claim_success():
    loop = RepairLoop()
    fid = _failure(loop).failure_id

    def broken(_contract):
        raise RuntimeError("simulated_apply_failure")

    result = loop.attempt_repair(fid, apply_patch_fn=broken)
    assert not result.success
    assert not result.patch_applied
    assert result.tests_passed == 0
    assert result.tests_failed == 1
    assert result.error == "apply_patch_fn_failed:simulated_apply_failure"


def test_failing_executor_retries_are_bounded():
    loop = RepairLoop()
    attempts = []

    def failing(contract):
        attempts.append(contract.attempt_number)
        return _callback_result(contract, success=False)

    result = loop.repair(
        "mission-unit-test", "AssertionError: mismatched value",
        traceback=TRACE, apply_patch_fn=failing,
    )
    assert not result.success
    assert result.status is RepairStatus.ESCALATED
    assert attempts == [1, 2, 3]
