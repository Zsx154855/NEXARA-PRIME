"""R9-B1: real SQLite, real local report I/O and approval/receipt contracts.

The provider is explicitly a *test mock*, used only to drive a local Mission
without paid API calls. A CONTRACT_PASS here is NOT independent agent identity,
business correctness, autonomous reasoning, or task A->B transfer.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nexara_prime.config import Settings
from nexara_prime.report_contract_acceptance import ReportMissionContractVerifier
from nexara_prime.runtime import NexaraRuntime


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, check=True,
        capture_output=True, text=True, timeout=10,
    )


@pytest.fixture
def completed_report(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "local-report-input"
    repo.mkdir(parents=True)
    (repo / "README.md").write_text(
        "Locally inspect this source and produce a bounded report.\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "R9 Local Test")
    _git(repo, "config", "user.email", "r9-test@example.invalid")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "fixture baseline")

    settings = Settings(
        db_path=tmp_path / "runtime" / "nexara.db",
        workspace_root=workspace,
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=0,
    )
    runtime = NexaraRuntime(settings)
    try:
        mission = runtime.create_mission("Read-only repository audit", source_dir=str(repo))
        planned = runtime.plan_mission(mission.mission_id)
        assert planned.result.get("context_hash"), "real repository context required"
        runtime.approve_mission(mission.mission_id, approved=True, actor="human")
        outcome = runtime.run_mission(mission.mission_id)
        assert outcome.state == "Completed"
        verifier = ReportMissionContractVerifier(
            store=runtime.store,
            evidence=runtime.evidence,
            approvals=runtime.approvals,
            report_root=settings.report_root,
        )
        yield runtime, outcome, verifier
    finally:
        runtime.telemetry.stop()
        runtime.store.close()


def test_real_file_tool_approval_receipt_and_evaluation_recheck(completed_report):
    runtime, mission, verifier = completed_report
    verdict = verifier.evaluate(
        mission.mission_id, mission.result["verification_evidence_id"],
    )
    assert verdict.status == "CONTRACT_PASS", verdict
    assert len(verdict.checks) == 4
    assert all(verdict.checks.values())
    assert verdict.business_outcome_verified is False


def test_same_evidence_not_accepted_for_another_mission(completed_report):
    _rt, mission, verifier = completed_report
    verdict = verifier.evaluate(
        "different-mission", mission.result["verification_evidence_id"],
    )
    assert verdict.status != "CONTRACT_PASS"
    assert verdict.business_outcome_verified is False


def test_unapproved_or_changed_acceptance_criteria_are_unknown(completed_report):
    runtime, mission, verifier = completed_report
    live = runtime.get_mission(mission.mission_id)
    live.contract.acceptance_criteria.append("prove invoice reconciled with bank")
    runtime._save_mission(live)
    verdict = verifier.evaluate(
        mission.mission_id, mission.result["verification_evidence_id"],
    )
    assert verdict.status == "OUTCOME_UNKNOWN", verdict
    assert verdict.business_outcome_verified is False


def test_report_tampering_fails_canonical_sha_recheck(completed_report):
    _rt, mission, verifier = completed_report
    report = Path(mission.result["report_path"])
    report.write_bytes(report.read_bytes() + b"\nmodified after acceptance\n")
    verdict = verifier.evaluate(
        mission.mission_id, mission.result["verification_evidence_id"],
    )
    assert verdict.status != "CONTRACT_PASS", verdict
    assert verdict.checks["report is written only after approval"] is False
    assert verdict.business_outcome_verified is False


def test_valid_heartbeat_cannot_replace_report_verification(completed_report):
    runtime, mission, verifier = completed_report
    heartbeat = runtime.evidence.add(
        mission.mission_id, "environment", "Heartbeat", "host online",
        mission.trace_id, actor="system", source="runtime",
        verification_status="verified",
    )
    verdict = verifier.evaluate(mission.mission_id, heartbeat.evidence_id)
    assert verdict.status != "CONTRACT_PASS", verdict
    assert verdict.checks["verification and evidence are present"] is False


def test_completion_state_without_full_event_chain_does_not_pass(completed_report):
    runtime, mission, verifier = completed_report
    # Source DB remains an isolated temporary DB; simulate missing event
    # by making the persisted final Mission state invalid. No production edits.
    changed = runtime.get_mission(mission.mission_id)
    from nexara_prime.models import MissionState
    changed.state = MissionState.RUNNING
    runtime._save_mission(changed)
    verdict = verifier.evaluate(
        mission.mission_id, mission.result["verification_evidence_id"],
    )
    assert verdict.status != "CONTRACT_PASS", verdict
    assert verdict.checks["full state machine trace exists"] is False


def test_consumed_approval_identity_is_required(completed_report):
    runtime, mission, verifier = completed_report
    changed = runtime.get_mission(mission.mission_id)
    changed.pending_approval_id = None
    runtime._save_mission(changed)
    verdict = verifier.evaluate(
        mission.mission_id, mission.result["verification_evidence_id"],
    )
    assert verdict.status != "CONTRACT_PASS", verdict
    assert verdict.checks["report is written only after approval"] is False


def test_evaluation_id_must_exist_in_authoritative_sqlite(completed_report):
    runtime, mission, verifier = completed_report
    changed = runtime.get_mission(mission.mission_id)
    changed.result["evaluation_id"] = "eval_missing_from_store"
    changed.result["evaluation_passed"] = True
    runtime._save_mission(changed)
    verdict = verifier.evaluate(
        mission.mission_id, mission.result["verification_evidence_id"],
    )
    assert verdict.status != "CONTRACT_PASS", verdict
    assert verdict.checks["evaluation passes safety and evidence gates"] is False
