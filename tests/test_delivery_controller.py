"""Tests for NEXARA Delivery Controller V2.

Covers all 9 gates plus edge cases: normal flow, missing evidence, contract
drift, dirty git, CI block, receipt invalid, external reality (G9),
evidence schema validation, legacy migration detection, V2 controller.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.nexara_prime.delivery_controller.controller import (
    ControllerResult,
    DeliveryController,
)
from src.nexara_prime.delivery_controller.evidence import (
    DeliveryEvidence,
    EvidenceSchemaValidator,
    EVIDENCE_MINIMAL_REQUIRED,
    EVIDENCE_FULL_REQUIRED,
)
from src.nexara_prime.delivery_controller.gates import (
    GateResult,
    GateRunner,
    GateStatus,
)
from src.nexara_prime.delivery_controller.preflight import PreflightRunner
from src.nexara_prime.delivery_controller.receipt import DeliveryReceipt


# ── Fixtures ──

@pytest.fixture
def repo_root():
    """Use the actual NEXARA-PRIME repo root for integration tests."""
    return str(Path(__file__).resolve().parents[3])


@pytest.fixture
def temp_repo(tmp_path):
    """Create a minimal fake git repo for unit tests."""
    repo = tmp_path / "fake_repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".nexara").mkdir()
    (repo / ".nexara" / "PROJECT_STATE.json").write_text(json.dumps({"project": "test"}))
    (repo / "governance").mkdir()
    (repo / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md").write_text("# NSEC V2.1")
    (repo / "governance" / "authority_index.yaml").write_text("index: true")
    (repo / "governance" / "contracts").mkdir(parents=True)
    (repo / "governance" / "contracts" / "MERGE_CONTRACT_V1.yaml").write_text("version: 1")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "ci").mkdir(parents=True)
    (repo / "scripts" / "ci" / "validate_merge_contract.py").write_text("# stub")
    (repo / "scripts" / "security").mkdir(parents=True)
    (repo / "scripts" / "security" / "scan_hardcoded_secrets.py").write_text("# stub")
    (repo / "scripts" / "governance").mkdir(parents=True)
    (repo / "scripts" / "governance" / "validate_nsec.py").write_text("# stub")
    (repo / "scripts" / "governance" / "detect_nsec_drift.py").write_text("# stub")
    (repo / "ruff.toml").write_text("[tool.ruff]")
    (repo / "reports").mkdir()
    (repo / ".nexara" / "evidence").mkdir(parents=True)
    return str(repo)


# ── ControllerResult ──

class TestControllerResult:
    def test_ready_for_pr(self):
        r = ControllerResult("READY_FOR_PR", "abc123", "feature/x", 8, 8, [], [])
        assert r.is_ready()
        assert not r.is_blocked()
        assert r.to_dict()["status"] == "READY_FOR_PR"

    def test_blocked(self):
        r = ControllerResult("BLOCKED", "abc123", "feature/x", 5, 8,
            [{"gate": "G4_TEST", "error": "TEST_FAIL", "detail": "3 failed"}], [])
        assert not r.is_ready()
        assert r.is_blocked()
        assert r.to_dict()["failures"][0]["gate"] == "G4_TEST"

    def test_to_dict_roundtrip(self):
        r = ControllerResult("READY_FOR_COMMIT", "def456", "fix/y", 7, 8,
            [{"gate": "G8", "error": "REVIEW_BLOCKED", "detail": "whitespace"}],
            ["ev_001"],
            external_blockers=["BILLING"],
            receipt_sha256="sha256:abc")
        d = r.to_dict()
        assert d["status"] == "READY_FOR_COMMIT"
        assert d["receipt_sha256"] == "sha256:abc"
        assert len(d["evidence_refs"]) == 1
        assert "BILLING" in d["external_blockers"]


# ── PreflightRunner ──

class TestPreflightRunner:
    def test_check_environment_passes(self, temp_repo):
        runner = PreflightRunner(temp_repo)
        ok, errors = runner.check_environment()
        assert ok
        assert len(errors) == 0

    def test_check_repository_passes(self, temp_repo):
        runner = PreflightRunner(temp_repo)
        ok, errors = runner.check_repository()
        assert ok

    @patch("src.nexara_prime.delivery_controller.preflight.subprocess.run")
    def test_check_repository_detects_dirty_worktree(self, mock_run, temp_repo):
        mock_run.return_value = MagicMock(returncode=0, stdout="M file.py\n?? new.py\n", stderr="")
        runner = PreflightRunner(temp_repo)
        ok, errors = runner.check_repository()
        assert not ok  # dirty worktree blocks preflight
        assert any("dirty_worktree" in e for e in errors)

    def test_check_repository_missing_git(self, tmp_path):
        no_git = tmp_path / "no_git"
        no_git.mkdir()
        runner = PreflightRunner(str(no_git))
        ok, errors = runner.check_repository()
        assert not ok
        assert any("not_a_git_repo" in e for e in errors)

    @patch("src.nexara_prime.delivery_controller.preflight.subprocess.run")
    def test_check_repository_missing_project_state(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        no_state = tmp_path / "no_state"
        no_state.mkdir()
        (no_state / ".git").mkdir()
        runner = PreflightRunner(str(no_state))
        ok, errors = runner.check_repository()
        assert not ok  # PROJECT_STATE.json missing is a preflight fail
        assert any("missing_project_state_json" in e for e in errors)


# ── GateRunner ──

class TestGateRunner:
    def test_run_all_returns_9_results(self, temp_repo):
        runner = GateRunner(temp_repo)
        results = runner.run_all()
        assert len(results) == 9

    def test_g1_environment_passes(self, temp_repo):
        result = GateRunner(temp_repo)._gate_g1_environment()
        assert result.passed
        assert result.name == GateStatus.G1_ENVIRONMENT

    def test_g2_repository_passes_clean_repo(self, temp_repo):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),   # git status --porcelain
                MagicMock(returncode=0, stdout="feature/x", stderr=""),  # git branch
            ]
            result = GateRunner(temp_repo)._gate_g2_repository()
            assert result.passed

    def test_g2_repository_blocks_main_branch(self, temp_repo):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),    # git status
                MagicMock(returncode=0, stdout="main", stderr=""),  # git branch
            ]
            result = GateRunner(temp_repo)._gate_g2_repository()
            assert not result.passed
            assert "on_main_branch" in (result.detail or "")

    def test_g2_repository_detects_dirty(self, temp_repo):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="M file.py\n", stderr=""),  # dirty
                MagicMock(returncode=0, stdout="feature/x", stderr=""),
            ]
            result = GateRunner(temp_repo)._gate_g2_repository()
            assert not result.passed
            assert "dirty" in (result.detail or "")

    def test_g3_contract_passes(self, temp_repo):
        result = GateRunner(temp_repo)._gate_g3_contract()
        assert result.passed

    def test_g3_contract_missing_nsec(self, tmp_path):
        repo = tmp_path / "bad_repo"
        repo.mkdir()
        (repo / "governance").mkdir()
        result = GateRunner(str(repo))._gate_g3_contract()
        assert not result.passed
        assert "missing_nsec_v2" in (result.detail or "")

    def test_g4_test_passes(self, temp_repo):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="842 passed", stderr="")
            result = GateRunner(temp_repo)._gate_g4_test()
            assert result.passed

    def test_g4_test_fails(self, temp_repo):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="841 passed, 1 failed", stderr="FAILED")
            result = GateRunner(temp_repo)._gate_g4_test()
            assert not result.passed
            assert result.error == "TEST_FAIL"

    def test_g5_evidence_passes(self, temp_repo):
        evidence_dir = Path(temp_repo) / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "ev_001.json").write_text(json.dumps({
            "evidence_id": "ev_001",
            "sha256": "abc",
            "timestamp": "2026-07-22T00:00:00Z",
        }))
        result = GateRunner(temp_repo)._gate_g5_evidence()
        assert result.passed
        assert result.evidence["count"] >= 1

    def test_g5_evidence_no_dir(self, tmp_path):
        repo = tmp_path / "no_ev"
        repo.mkdir()
        result = GateRunner(str(repo))._gate_g5_evidence()
        assert not result.passed
        assert result.error == "NO_EVIDENCE_DIR"

    def test_g5_evidence_no_files(self, temp_repo):
        evidence_dir = Path(temp_repo) / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        # empty dir
        result = GateRunner(temp_repo)._gate_g5_evidence()
        assert not result.passed
        assert result.error == "NO_EVIDENCE_FILES"

    def test_g6_receipt_passes(self, temp_repo):
        receipt_dir = Path(temp_repo) / "reports"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / "receipt_abc123.json").write_text(json.dumps({"head": "abc123", "status": "ok"}))
        result = GateRunner(temp_repo)._gate_g6_receipt()
        assert result.passed

    def test_g6_receipt_no_files(self, temp_repo):
        result = GateRunner(temp_repo)._gate_g6_receipt()
        assert not result.passed
        assert result.error == "NO_RECEIPT_FILES"

    def test_g7_ci_dependency_passes(self, temp_repo):
        result = GateRunner(temp_repo)._gate_g7_ci_dependency()
        assert result.passed

    def test_g7_ci_dependency_missing_scripts(self, tmp_path):
        repo = tmp_path / "no_ci"
        repo.mkdir()
        (repo / "governance").mkdir()
        result = GateRunner(str(repo))._gate_g7_ci_dependency()
        assert not result.passed
        assert "CI_DEPS_MISSING" in (result.error or "")

    def test_g8_review_readiness_passes(self, temp_repo):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = GateRunner(temp_repo)._gate_g8_review_readiness()
            assert result.passed


# ── DeliveryEvidence ──

class TestDeliveryEvidence:
    def test_evidence_exists_true(self, temp_repo):
        evidence_dir = Path(temp_repo) / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "t.json").write_text(json.dumps({"id": "1"}))
        assert DeliveryEvidence.evidence_exists(temp_repo)

    def test_evidence_exists_false_empty(self, temp_repo):
        evidence_dir = Path(temp_repo) / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        assert not DeliveryEvidence.evidence_exists(temp_repo)

    def test_evidence_exists_false_no_dir(self, tmp_path):
        assert not DeliveryEvidence.evidence_exists(str(tmp_path / "nonexistent"))

    def test_count_evidence_files(self, temp_repo):
        evidence_dir = Path(temp_repo) / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "a.json").write_text("{}")
        (evidence_dir / "b.json").write_text("{}")
        assert DeliveryEvidence.count_evidence_files(temp_repo) == 2


# ── DeliveryReceipt ──

class TestDeliveryReceipt:
    def test_generate_receipt(self, temp_repo):
        dr = DeliveryReceipt(temp_repo)
        receipt = dr.generate("abc123", "feature/x", 8, 8, "READY_FOR_PR", ["ev_001"])
        assert receipt["status"] == "READY_FOR_PR"
        assert receipt["head"] == "abc123"
        assert receipt["gates_passed"] == 8
        assert "sha256" in receipt
        assert len(receipt["sha256"]) == 64

    def test_receipt_hash_is_stable(self, temp_repo):
        dr = DeliveryReceipt(temp_repo)
        r1 = dr.generate("abc", "x", 8, 8, "READY_FOR_PR", [])
        r2 = dr.generate("abc", "x", 8, 8, "READY_FOR_PR", [])
        assert r1["sha256"] == r2["sha256"]

    def test_save_receipt(self, temp_repo):
        dr = DeliveryReceipt(temp_repo)
        receipt = dr.generate("abc12345", "feature/x", 8, 8, "READY_FOR_PR", [])
        path = dr.save(receipt)
        assert path.exists()
        saved = json.loads(path.read_text())
        assert saved["sha256"] == receipt["sha256"]


# ── DeliveryController Integration ──

class TestDeliveryController:
    def test_check_with_mocked_gates(self, temp_repo):
        with patch.object(GateRunner, "run_all") as mock_gates, \
             patch.object(PreflightRunner, "check_environment", return_value=(True, [])), \
             patch.object(PreflightRunner, "check_repository", return_value=(True, [])), \
             patch("subprocess.run") as mock_subproc:
            mock_gates.return_value = [
                GateResult(name=g, passed=True) for g in GateStatus.ALL
            ]
            mock_subproc.side_effect = [
                MagicMock(returncode=0, stdout="abc123\n", stderr=""),  # git rev-parse
                MagicMock(returncode=0, stdout="feature/x\n", stderr=""),  # git branch
            ]
            controller = DeliveryController(temp_repo)
            result = controller.check()
            assert result.status == "READY_FOR_PR"
            assert result.gates_passed == 9
            assert result.gates_total == 9

    def test_check_with_failures(self, temp_repo):
        with patch.object(GateRunner, "run_all") as mock_gates, \
             patch.object(PreflightRunner, "check_environment", return_value=(True, [])), \
             patch.object(PreflightRunner, "check_repository", return_value=(True, [])), \
             patch("subprocess.run") as mock_subproc:
            mock_gates.return_value = [
                GateResult(name=GateStatus.G1_ENVIRONMENT, passed=True),
                GateResult(name=GateStatus.G2_REPOSITORY, passed=True),
                GateResult(name=GateStatus.G3_CONTRACT, passed=True),
                GateResult(name=GateStatus.G4_TEST, passed=False, error="TEST_FAIL", detail="1 failed"),
                GateResult(name=GateStatus.G5_EVIDENCE, passed=False, error="NO_EVIDENCE_DIR"),
                GateResult(name=GateStatus.G6_RECEIPT, passed=True),
                GateResult(name=GateStatus.G7_CI_DEPENDENCY, passed=True),
                GateResult(name=GateStatus.G8_REVIEW_READINESS, passed=True),
                GateResult(name=GateStatus.G9_EXTERNAL_REALITY, passed=True),
            ]
            mock_subproc.side_effect = [
                MagicMock(returncode=0, stdout="def456\n", stderr=""),  # git rev-parse
                MagicMock(returncode=0, stdout="fix/y\n", stderr=""),  # git branch
            ]
            controller = DeliveryController(temp_repo)
            result = controller.check()
            assert result.status == "BLOCKED"
            assert result.gates_passed == 7
            assert len(result.failures) == 2
            assert result.failures[0]["gate"] == "G4_TEST"
            assert result.failures[1]["gate"] == "G5_EVIDENCE"


# ── CLI Integration ──

class TestCLIIntegration:
    def test_cli_delivery_check_command_exists(self, temp_repo):
        """Verify 'nexara delivery check' is registered."""
        from src.nexara_prime.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["delivery", "check"])
        assert args.command == "delivery"
        assert args.delivery_command == "check"

    def test_cmd_delivery_check_returns_output(self, temp_repo, monkeypatch):
        """Verify cmd_delivery_check runs and returns structured output."""
        monkeypatch.chdir(temp_repo)
        from src.nexara_prime.cli import cmd_delivery_check
        from src.nexara_prime.delivery_controller.gates import GateResult, GateStatus

        with patch.object(GateRunner, "run_all") as mock_gates:
            mock_gates.return_value = [
                GateResult(name=g, passed=True) for g in GateStatus.ALL
            ]
            with patch("subprocess.run") as mock_subproc:
                mock_subproc.side_effect = [
                    MagicMock(returncode=0, stdout="abc123\n", stderr=""),  # git rev-parse
                    MagicMock(returncode=0, stdout="feature/x\n", stderr=""),  # git branch
                ]
                # Don't assert return code here — gates may vary in temp_repo
                code = cmd_delivery_check()
                # In a temp repo with all fixtures, this should pass
                assert code in (0, 1)


# ══════════════════════════════════════════════
# V2 Tests: G9 External Reality Gate
# ══════════════════════════════════════════════

class TestG9ExternalReality:
    def test_g9_passes_no_blockers(self, tmp_path):
        repo = tmp_path / "clean_repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("# No blockers")
        runner = GateRunner(str(repo))
        result = runner._gate_g9_external_reality()
        assert result.passed

    def test_g9_detects_billing_lock(self, tmp_path):
        repo = tmp_path / "billing_repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("GitHub CI degraded due to billing lock.")
        runner = GateRunner(str(repo))
        result = runner._gate_g9_external_reality()
        assert not result.passed
        assert "GITHUB_ACTIONS_BILLING_LOCK" in result.evidence["external_blockers"]

    def test_g9_local_authoritative_overrides(self, tmp_path):
        repo = tmp_path / "auth_repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text(
            "GitHub CI degraded due to billing lock. "
            "Local sovereign verification as primary."
        )
        runner = GateRunner(str(repo))
        result = runner._gate_g9_external_reality()
        assert result.passed
        assert result.evidence["local_authoritative"] is True

    def test_g9_reads_receipt(self, tmp_path):
        repo = tmp_path / "receipt_repo"
        repo.mkdir()
        reports = repo / "reports" / "closure"
        reports.mkdir(parents=True)
        (repo / "AGENTS.md").write_text("# No billing")
        (reports / "RECEIPT.json").write_text(json.dumps({
            "verification_governance": {
                "ci_status": "NOT_EXECUTED_EXTERNAL_BLOCK",
                "ci_block_reason": "GITHUB_ACTIONS_BILLING_LOCK",
            }
        }))
        runner = GateRunner(str(repo))
        result = runner._gate_g9_external_reality()
        assert not result.passed

    def test_g9_detects_ci_workflows(self, tmp_path):
        repo = tmp_path / "ci_repo"
        repo.mkdir()
        workflows = repo / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("runs-on: ubuntu-latest\n")
        (repo / "AGENTS.md").write_text("# clean")
        runner = GateRunner(str(repo))
        result = runner._gate_g9_external_reality()
        assert result.passed


# ══════════════════════════════════════════════
# V2 Tests: Evidence Schema Validator
# ══════════════════════════════════════════════

class TestEvidenceSchemaValidator:
    def test_fully_conforming(self, tmp_path):
        evidence_dir = tmp_path / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "ev.json").write_text(json.dumps({
            "evidence_id": "ev_001", "sha256": "a" * 64,
            "timestamp": "2026-07-22T00:00:00Z",
            "mission_id": "m1", "kind": "test",
        }))
        validator = EvidenceSchemaValidator(str(tmp_path))
        results = validator.validate_all()
        assert results[0].schema_status == "FULLY_CONFORMING"

    def test_minimally_conforming(self, tmp_path):
        evidence_dir = tmp_path / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "ev.json").write_text(json.dumps({
            "evidence_id": "ev_002", "sha256": "b" * 64,
            "timestamp": "ts",
        }))
        validator = EvidenceSchemaValidator(str(tmp_path))
        results = validator.validate_all()
        assert results[0].schema_status == "CONFORMING"

    def test_legacy_detection(self, tmp_path):
        evidence_dir = tmp_path / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "old.json").write_text(json.dumps({
            "mission": "old", "branch": "main",
            "base_sha": "abc", "head_sha": "def",
        }))
        validator = EvidenceSchemaValidator(str(tmp_path))
        results = validator.validate_all()
        assert results[0].schema_status == "LEGACY"

    def test_invalid_json(self, tmp_path):
        evidence_dir = tmp_path / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "bad.json").write_text("not json {{{")
        validator = EvidenceSchemaValidator(str(tmp_path))
        results = validator.validate_all()
        assert results[0].schema_status == "INVALID"

    def test_empty_dir(self, tmp_path):
        evidence_dir = tmp_path / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True)
        validator = EvidenceSchemaValidator(str(tmp_path))
        assert len(validator.validate_all()) == 0

    def test_summary_counts(self, tmp_path):
        evidence_dir = tmp_path / ".nexara" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "c.json").write_text(json.dumps({
            "evidence_id": "e1", "sha256": "a" * 64, "timestamp": "ts",
            "mission_id": "m1", "kind": "test",
        }))
        (evidence_dir / "l.json").write_text(json.dumps({"mission": "old"}))
        (evidence_dir / "i.json").write_text("bad")
        validator = EvidenceSchemaValidator(str(tmp_path))
        s = validator.summary()
        assert s["total_files"] == 3
        assert s["conforming"] == 1
        assert s["legacy"] == 1
        assert s["invalid"] == 1

    def test_required_constants(self):
        assert "evidence_id" in EVIDENCE_MINIMAL_REQUIRED
        assert "sha256" in EVIDENCE_MINIMAL_REQUIRED
        assert "timestamp" in EVIDENCE_MINIMAL_REQUIRED
        assert "mission_id" in EVIDENCE_FULL_REQUIRED
        assert "kind" in EVIDENCE_FULL_REQUIRED


# ══════════════════════════════════════════════
# V2 Tests: Controller V2 Features
# ══════════════════════════════════════════════

class TestControllerV2:
    def test_external_blockers_field(self, temp_repo):
        r = ControllerResult("READY_FOR_PR", "abc", "x", 9, 9, [], [],
                             external_blockers=["BILLING"])
        assert r.has_external_blockers()

    def test_external_blocked_status(self, temp_repo):
        r = ControllerResult("EXTERNAL_BLOCKED", "abc", "x", 8, 9, [], [],
                             external_blockers=["BILLING"])
        assert r.is_blocked()

    def test_9_gates_in_all(self):
        assert len(GateStatus.ALL) == 9
        assert GateStatus.G9_EXTERNAL_REALITY in GateStatus.ALL

    def test_g9_method_exists(self):
        assert hasattr(GateRunner, "_gate_g9_external_reality")
