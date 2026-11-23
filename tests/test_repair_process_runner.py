"""Real local Git/pytest subprocess regression, using a disposable repo.

The EvidenceStore test double checks transport only. Full production
EvidenceStore and macOS CI integration remain separate acceptance gates.
"""

import base64
import json
import subprocess

import pytest

from nexara_prime.repair_loop import RepairContract, RepairLoop, RepairStatus
from nexara_prime.repair_process_runner import ApprovedDiffPatchGenerator, LocalRepairProcessRunner
from nexara_prime.repair_receipt import validate_repair_receipt


class EvidenceDouble:
    def __init__(self):
        self.records = {}
        self.valid = set()

    def add(self, mid, kind, title, content, trace, **kw):
        from types import SimpleNamespace
        eid = f"ev-{len(self.records) + 1}"
        record = SimpleNamespace(
            evidence_id=eid, mission_id=mid, kind=kind, content=content,
            task_id=kw["task_id"], tool_invocation_id=kw["tool_invocation_id"],
        )
        self.records[eid] = record
        return record

    def verify(self, eid):
        self.valid.add(eid)
        return True

    def is_preverified_and_integrity_bound(self, eid):
        return eid in self.valid

    def get_by_id(self, eid):
        return self.records[eid]


def git(directory, *argv):
    return subprocess.run(
        ["git", *argv], cwd=directory, capture_output=True, text=True, check=True,
    ).stdout.strip()


def setup_case(tmp_path, *, repaired="return x + 1", test_body="assert calc(2) == 3", timeout=20):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "fix/isolated")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    (root / "calc.py").write_text("def calc(x):\n    return x + 0\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_calc.py").write_text(
        "from calc import calc\n\ndef test_real_process():\n    " + test_body + "\n"
    )
    git(root, "add", "calc.py", "tests/test_calc.py")
    git(root, "commit", "-qm", "fixture")
    initial = git(root, "rev-parse", "HEAD")
    (root / "calc.py").write_text("def calc(x):\n    " + repaired + "\n")
    patch = git(root, "diff", "--", "calc.py") + "\n"
    git(root, "checkout", "--", "calc.py")
    evidence = EvidenceDouble()
    runner = LocalRepairProcessRunner(
        worktree=root, mission_id="mission-1", evidence_store=evidence,
        patch_diff=patch, pytest_targets=("tests/test_calc.py",), timeout_s=timeout,
    )
    contract = RepairContract(
        contract_id="repair-e2e", failure_id="failure-1",
        proposed_patch=patch, affected_files=["calc.py"], attempt_number=1,
    )
    contract.compute_digest()
    return root, runner, contract, evidence, initial


def test_real_patch_git_commit_pytest_and_receipt_verification(tmp_path):
    root, runner, contract, evidence, initial = setup_case(tmp_path)
    result = runner(contract)
    assert result.success, result.error
    assert result.patch_applied and result.tests_passed == 1
    assert git(root, "rev-parse", "HEAD") != initial
    ok, reason = validate_repair_receipt(
        evidence, mission_id="mission-1", contract=contract,
        result=result, trusted_process_verify=runner.verify_process,
    )
    assert ok, reason
    payload = json.loads(evidence.records[result.evidence_ids[0]].content)
    assert b"1 passed" in base64.b64decode(payload["test_log_b64"])


def test_real_repair_loop_accepts_audited_process(tmp_path):
    _, runner, _, evidence, _ = setup_case(tmp_path)
    generator = ApprovedDiffPatchGenerator(runner, ("calc.py",))
    loop = RepairLoop(
        patch_gen=generator, evidence_store=evidence,
        trusted_process_verify=runner.verify_process,
    )
    result = loop.repair(
        "mission-1", "AssertionError: unexpected result",
        traceback='File "calc.py", line 1', apply_patch_fn=runner,
    )
    assert result.status is RepairStatus.RESOLVED, result.error
    assert result.success and result.evidence_ids


def test_real_test_failure_is_not_success(tmp_path):
    _, runner, contract, evidence, _ = setup_case(tmp_path, repaired="return x + 9")
    result = runner(contract)
    assert not result.success
    assert result.patch_applied and result.error == "repair_tests_failed_or_missing"
    assert len(evidence.records) == 1
    payload = json.loads(next(iter(evidence.records.values())).content)
    assert payload["test_exit_code"] != 0


def test_test_timeout_blocks_acceptance(tmp_path):
    _, runner, contract, _, _ = setup_case(
        tmp_path, test_body='__import__("time").sleep(5); assert calc(2) == 3', timeout=1,
    )
    result = runner(contract)
    assert not result.success and result.patch_applied
    assert result.error == "repair_process_timeout"


def test_duplicate_patch_cannot_be_reapplied(tmp_path):
    _, runner, contract, evidence, _ = setup_case(tmp_path)
    assert runner(contract).success
    again = runner(contract)
    assert not again.success and again.error == "repair_worktree_already_changed"
    assert len(evidence.records) == 1


def test_unreviewed_patch_is_rejected_before_execution(tmp_path):
    root, runner, contract, _, initial = setup_case(tmp_path)
    contract.proposed_patch = "different patch"
    assert runner(contract).error == "repair_patch_contract_mismatch"
    assert git(root, "rev-parse", "HEAD") == initial


def test_mutated_contract_digest_rejected(tmp_path):
    root, runner, contract, _, initial = setup_case(tmp_path)
    contract.hypothesis = "changed after review"
    assert runner(contract).error == "repair_contract_integrity_invalid"
    assert git(root, "rev-parse", "HEAD") == initial


def test_forged_process_id_cannot_validate_receipt(tmp_path):
    _, runner, contract, evidence, _ = setup_case(tmp_path)
    result = runner(contract)
    payload = json.loads(evidence.records[result.evidence_ids[0]].content)
    payload["run_id"] = "old-run"
    assert not runner.verify_process(payload)


def test_modified_test_log_is_not_valid_receipt(tmp_path):
    _, runner, contract, evidence, _ = setup_case(tmp_path)
    result = runner(contract)
    payload = json.loads(evidence.records[result.evidence_ids[0]].content)
    payload["test_log_b64"] += "AA"
    assert not runner.verify_process(payload)


def test_patch_outside_contract_scope_is_rejected(tmp_path):
    _, runner, contract, evidence, _ = setup_case(tmp_path)
    contract.affected_files = ["unauthorized.py"]
    contract.compute_digest()
    result = runner(contract)
    assert not result.success and result.patch_applied
    assert result.error == "repair_patch_outside_contract_scope"
    assert not evidence.records


def test_missing_evidence_store_fails_closed(tmp_path):
    root, runner, contract, _, initial = setup_case(tmp_path)
    runner.evidence = None
    assert runner(contract).error == "repair_evidence_store_unavailable"
    assert git(root, "rev-parse", "HEAD") == initial


def test_unsafe_pytest_target_rejected_before_process(tmp_path):
    root, runner, _, evidence, _ = setup_case(tmp_path)
    with pytest.raises(ValueError, match="pytest_targets_not_allowlisted"):
        LocalRepairProcessRunner(
            worktree=root, mission_id="mission-1", evidence_store=evidence,
            patch_diff=runner.patch_diff, pytest_targets=("../secret.py",),
        )


def test_concurrent_git_worktree_lock_prevents_double_apply(tmp_path):
    import fcntl
    root, runner, contract, _, initial = setup_case(tmp_path)
    with runner._lock_path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            result = runner(contract)
            assert not result.success
            assert result.error == "repair_runner_busy"
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    assert git(root, "rev-parse", "HEAD") == initial


def test_test_path_traversal_is_rejected(tmp_path):
    root, runner, _, evidence, _ = setup_case(tmp_path)
    (tmp_path / "escape.py").write_text("raise AssertionError('outside tests')\n")
    with pytest.raises(ValueError, match="pytest_target_escapes_workspace"):
        LocalRepairProcessRunner(
            worktree=root, mission_id="mission-1", evidence_store=evidence,
            patch_diff=runner.patch_diff,
            pytest_targets=("tests/../../escape.py",),
        )


def test_failure_still_returns_real_persisted_evidence_id(tmp_path):
    _, runner, contract, evidence, _ = setup_case(tmp_path, repaired="return x + 9")
    result = runner(contract)
    assert not result.success and result.patch_applied
    assert len(result.evidence_ids) == 1
    assert result.evidence_ids[0] in evidence.records
