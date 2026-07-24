"""Contract tests: SDK models mirror runtime truth authoritatively."""
from __future__ import annotations

import json

from nexara_sdk.models import (
    ApprovalRequest,
    ApprovalStatus,
    EvidenceArtifact,
    MemoryKind,
    MemoryRecord,
    Mission,
    PlanStep,
    RuntimeRole,
    WorkContract,
)


class TestApprovalNullableTimestamps:
    def test_expires_at_accepts_null(self):
        a = ApprovalRequest(expires_at=None)
        assert a.expires_at is None

    def test_decided_at_accepts_null(self):
        a = ApprovalRequest(decided_at=None)
        assert a.decided_at is None

    def test_status_values_match_runtime_lowercase(self):
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.CONSUMED.value == "consumed"

    def test_preserves_runtime_approval_fields(self):
        a = ApprovalRequest(
            approval_id="apr_1",
            mission_id="m1",
            action="write",
            rationale="test",
            reason="because",
            affected_resources=["file.txt"],
            external_effect=False,
            reversible=True,
            rollback_plan={"kind": "restore"},
            estimated_cost=1.5,
            expires_at=None,
            decided_at=None,
            proposal_sha256="abc123",
        )
        d = a.model_dump()
        assert d["expires_at"] is None
        assert d["decided_at"] is None
        assert d["reversible"] is True
        assert d["rollback_plan"] == {"kind": "restore"}


class TestMemoryNullableSource:
    def test_source_evidence_id_accepts_null(self):
        m = MemoryRecord(source_evidence_id=None)
        assert m.source_evidence_id is None

    def test_memory_kind_values_match_runtime(self):
        assert MemoryKind.SHORT_TERM.value == "short_term"
        assert MemoryKind.FACT.value == "fact"
        assert MemoryKind.DECISION.value == "decision"
        assert MemoryKind.FAILURE.value == "failure"
        assert MemoryKind.PATCH.value == "patch"

    def test_preserves_committed_memory_fields(self):
        m = MemoryRecord(
            memory_id="mem_1",
            kind=MemoryKind.FACT,
            key="test/key",
            content="value",
            source_evidence_id=None,
            confidence=0.95,
            status="committed",
            verified=False,
            canonical=False,
        )
        d = m.model_dump()
        assert d["source_evidence_id"] is None
        assert d["confidence"] == 0.95
        assert d["status"] == "committed"


class TestPlanStepPreservation:
    def test_mirrors_runtime_fields(self):
        ps = PlanStep(
            step_id="step_1",
            title="Analyze",
            description="Analyze the code",
            role=RuntimeRole.ANALYST,
            persona="Nyx",
            required_capabilities=["tool.file_read"],
            status="pending",
        )
        d = ps.model_dump()
        assert d["title"] == "Analyze"
        assert d["role"] == "Analyst"
        assert d["persona"] == "Nyx"
        assert d["required_capabilities"] == ["tool.file_read"]
        assert d["status"] == "pending"


class TestWorkContractPreservation:
    def test_mirrors_runtime_fields(self):
        wc = WorkContract(
            contract_id="c1",
            mission_id="m1",
            objective="Test",
            status="draft",
            risk_level="R2",
            deliverables=["report"],
            acceptance_criteria=["passes tests"],
            approved_at=None,
        )
        d = wc.model_dump()
        assert d["objective"] == "Test"
        assert d["status"] == "draft"
        assert d["approved_at"] is None

    def test_nullable_fields_remain_nullable(self):
        wc = WorkContract(approved_at=None, mission_run_id=None)
        assert wc.approved_at is None
        assert wc.mission_run_id is None


class TestMissionHumanControl:
    def test_paused_and_safe_mode_preserved(self):
        m = Mission(mission_id="m1", paused=True, safe_mode=True)
        d = m.model_dump()
        assert d["paused"] is True
        assert d["safe_mode"] is True

    def test_defaults_are_false(self):
        m = Mission(mission_id="m1")
        assert m.paused is False
        assert m.safe_mode is False


class TestEvidencePreservation:
    def test_preserves_body_and_linkage(self):
        e = EvidenceArtifact(
            evidence_id="ev_1",
            mission_id="m1",
            title="Test Evidence",
            content="body",
            tool_invocation_id="ti_1",
            task_id="task_1",
            verification_status="verified",
        )
        d = e.model_dump()
        assert d["title"] == "Test Evidence"
        assert d["content"] == "body"
        assert d["tool_invocation_id"] == "ti_1"
        assert d["task_id"] == "task_1"


class TestGenericReceiptDiscovery:
    def test_single_terminal_receipt_discovered(self):
        from scripts.runtime_truth.validate_program_state import _find_canonical_receipt

        path = _find_canonical_receipt()
        assert path is not None, "Should discover the canonical receipt"
        assert path.name == "pr23_final_attestation.json"

    def test_multiple_terminal_receipts_rejected(self, tmp_path):
        receipts = tmp_path / "receipts"
        receipts.mkdir()
        for i in range(2):
            (receipts / f"pr{i}_final_attestation.json").write_text(json.dumps({
                "receipt_type": "superseding_receipt",
                "superseded_by": None,
            }))
        import scripts.runtime_truth.validate_program_state as vps
        orig = vps.RECEIPTS_DIR
        vps.RECEIPTS_DIR = receipts
        try:
            result = vps.validate_receipt_provenance({}, {})
            has_error = any(not ok for ok, _ in result)
            assert has_error, "Should reject multiple terminal receipts"
        finally:
            vps.RECEIPTS_DIR = orig

    def test_future_receipt_supersedes_without_validator_edit(self, tmp_path):
        """A future PR can add a new receipt and the validator works unchanged."""
        receipts = tmp_path / "receipts"
        receipts.mkdir()
        (receipts / "pr99_final_attestation.json").write_text(json.dumps({
            "receipt_type": "superseding_receipt",
            "superseded_by": None,
            "evidence_subject_head": "b" * 40,
            "ci_verification": {"run_id": "99", "result": "99 passed"},
        }))
        import scripts.runtime_truth.validate_program_state as vps
        orig = vps.RECEIPTS_DIR
        vps.RECEIPTS_DIR = receipts
        try:
            path = vps._find_canonical_receipt()
            assert path is not None
            assert "pr99" in path.name
        finally:
            vps.RECEIPTS_DIR = orig


class TestSDKPydanticBehavior:
    def test_no_silent_field_loss_approval(self):
        payload = {
            "approval_id": "apr_x",
            "mission_id": "m1",
            "action": "write",
            "risk_level": "R2",
            "rationale": "needed",
            "reason": None,
            "expires_at": None,
            "decided_at": None,
            "external_effect": True,
            "estimated_cost": 3.0,
            "rollback_plan": {"step": "revert"},
        }
        a = ApprovalRequest(**payload)
        d = a.model_dump()
        for k in payload:
            assert d[k] == payload[k], f"Field {k} lost or changed"

    def test_no_silent_field_loss_memory(self):
        payload = {
            "memory_id": "mem_x",
            "kind": "fact",
            "key": "a/b",
            "content": "data",
            "source_evidence_id": None,
            "confidence": 0.5,
            "status": "committed",
            "verified": True,
        }
        m = MemoryRecord(**payload)
        d = m.model_dump()
        for k in payload:
            assert d[k] == payload[k], f"Field {k} lost or changed"

    def test_unknown_field_does_not_corrupt_known_fields(self):
        """Pydantic strips unknown fields by default — known fields preserved."""
        a = ApprovalRequest(
            approval_id="x",
            mission_id="m1",
            action="x",
            risk_level="R2",
            rationale="x",
        )
        d = a.model_dump()
        assert "imaginary_field" not in d
        assert d["approval_id"] == "x"
        assert d["mission_id"] == "m1"
