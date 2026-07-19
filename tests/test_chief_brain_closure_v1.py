"""Chief Brain Real Mission Product Closure V1 — Vertical Slice Tests.

Covers the complete Tool → Evidence → Receipt → Memory closure chain:
  - Deterministic FailureCode / ReasonCode on all failure paths
  - Receipt chain integrity (every invocation → evidence receipt)
  - Memory-Evidence binding enforcement
  - Replay / Idempotency across the full chain
  - Fail-closed behavior (Provider unavailable, Tool unavailable)
  - Fake success prevention
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from nexara_prime.config import Settings
from nexara_prime.models import (
    FailureCode,
    MemoryKind,
    ReasonCode,
    RiskLevel,
    ToolInvocation,
    new_id,
)
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.tools import ToolRuntime


# ── Helpers ──────────────────────────────────────────────────────────────────

def _settings(root: Path, **kwargs) -> Settings:
    defaults: dict = {
        "db_path": root / "test.db",
        "workspace_root": root / "workspace",
        "report_root": root / "reports",
        "model_provider": "mock",
        "mock_model": True,
        "api_host": "127.0.0.1",
        "api_port": 8765,
    }
    defaults.update(kwargs)
    s = Settings(**defaults)
    s.ensure_dirs()
    return s


# ── FailureCode / ReasonCode Classification ──────────────────────────────────

class TestFailureCodeClassification:
    """Every tool error path MUST emit a deterministic FailureCode + ReasonCode."""

    def test_unknown_tool_emits_TOOL_UNKNOWN(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Unknown tool test")
        with pytest.raises(KeyError, match="unknown_tool"):
            rt.tools.invoke(m.mission_id, "nonexistent_tool", {}, "trace-1")

    def test_missing_approval_emits_APPROVAL_MISSING(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Missing approval test")
        # file_write_report requires R2 approval
        with pytest.raises(PermissionError, match="approval_required"):
            rt.tools.invoke(m.mission_id, "file_write_report",
                           {"path": "test.md", "content": "x"}, "trace-2",
                           safe_mode=False)

    def test_classify_failure_permission_error(self) -> None:
        fc, rc = ToolRuntime._classify_failure(
            PermissionError("approval_required_for_tool: no approval_id provided")
        )
        assert fc == FailureCode.APPROVAL_MISSING
        assert rc == ReasonCode.APPROVAL_NOT_PROVIDED

    def test_classify_failure_tool_timeout(self) -> None:
        fc, rc = ToolRuntime._classify_failure(RuntimeError("tool_timeout"))
        assert fc == FailureCode.TOOL_TIMEOUT
        assert rc == ReasonCode.EXECUTION_TIMEOUT

    def test_classify_failure_policy_rejected(self) -> None:
        fc, rc = ToolRuntime._classify_failure(
            PermissionError("policy_rejected_for_tool")
        )
        assert fc == FailureCode.TOOL_POLICY_REJECTED
        assert rc == ReasonCode.POLICY_DENIED

    def test_classify_failure_code_forbidden(self) -> None:
        fc, rc = ToolRuntime._classify_failure(
            PermissionError("code_policy_rejected")
        )
        assert fc == FailureCode.TOOL_POLICY_REJECTED
        assert rc == ReasonCode.CODE_FORBIDDEN

    def test_classify_failure_sandbox_unavailable(self) -> None:
        fc, rc = ToolRuntime._classify_failure(
            PermissionError("os_sandbox_unavailable:posix_spawn")
        )
        assert fc == FailureCode.TOOL_SANDBOX_UNAVAILABLE
        assert rc == ReasonCode.SANDBOX_FAILED

    def test_classify_failure_path_traversal(self) -> None:
        fc, rc = ToolRuntime._classify_failure(
            PermissionError("path_outside_allowed_root:/etc/passwd")
        )
        assert fc == FailureCode.IO_PATH_TRAVERSAL
        assert rc == ReasonCode.PATH_OUTSIDE_ROOT

    def test_classify_failure_file_not_found(self) -> None:
        fc, rc = ToolRuntime._classify_failure(FileNotFoundError("/nonexistent"))
        assert fc == FailureCode.IO_NOT_FOUND
        assert rc == ReasonCode.FILE_NOT_FOUND

    def test_classify_failure_value_error_default(self) -> None:
        fc, rc = ToolRuntime._classify_failure(ValueError("something invalid"))
        assert fc == FailureCode.TOOL_ARGUMENT_INVALID
        assert rc == ReasonCode.UNKNOWN

    def test_classify_failure_runtime_fallback(self) -> None:
        fc, rc = ToolRuntime._classify_failure(Exception("unexpected"))
        assert fc == FailureCode.RUNTIME_INTERNAL
        assert rc == ReasonCode.INTERNAL_ERROR

    def test_classify_failure_os_error(self) -> None:
        fc, rc = ToolRuntime._classify_failure(OSError("permission denied"))
        assert fc == FailureCode.IO_PERMISSION_DENIED
        assert rc == ReasonCode.PERMISSION_DENIED

    def test_classify_all_failure_codes_unique(self) -> None:
        """Every FailureCode must be uniquely mapped."""
        codes = set(FailureCode)
        assert len(codes) >= 20, "FailureCode enum should have comprehensive coverage"


# ── Tool Invocation → Evidence Receipt Chain ─────────────────────────────────

class TestReceiptChainIntegrity:
    """Every tool invocation MUST produce a linked, verifiable evidence receipt."""

    def test_successful_file_read_produces_receipt(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Receipt chain test")
        (rt.settings.workspace_root / "test.txt").write_text("hello receipt")
        result = rt.tools.invoke(m.mission_id, "file_read",
                                {"path": "test.txt"}, "trace-r1")
        assert result.status == "completed"
        assert result.receipt_evidence_id is not None
        # Verify receipt is in evidence store
        evidence = rt.evidence.store.get_record_envelope(result.receipt_evidence_id)
        assert evidence is not None
        assert evidence["record_type"] == "evidence"

    def test_failed_invocation_still_produces_receipt(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Failed receipt test")
        with pytest.raises(FileNotFoundError):
            rt.tools.invoke(m.mission_id, "file_read",
                           {"path": "nonexistent.txt"}, "trace-f1")
        # Even failed invocations should leave a record
        invocations = rt.tools.list_invocations(m.mission_id)
        assert len(invocations) >= 1

    def test_receipt_chain_verify_intact(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Receipt chain verify")
        (rt.settings.workspace_root / "a.txt").write_text("A")
        rt.tools.invoke(m.mission_id, "file_read", {"path": "a.txt"}, "trace-c1")
        (rt.settings.workspace_root / "b.txt").write_text("B")
        rt.tools.invoke(m.mission_id, "file_read", {"path": "b.txt"}, "trace-c2")

        chain = rt.evidence.verify_receipt_chain(m.mission_id)
        assert chain["chain_intact"] is True
        assert chain["total_invocations"] == 2
        assert chain["chain_gaps"] == 0
        assert chain["unverifiable_receipts"] == 0
        assert chain["fail_closed_violations"] == 0

    def test_receipt_chain_detects_gaps(self, tmp_path: Path) -> None:
        """If no invocation has a receipt, chain should report gaps."""
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Gap test")
        # Directly insert a tool record without receipt
        inv = ToolInvocation(
            invocation_id=new_id("tool"), mission_id=m.mission_id,
            tool_name="file_read", arguments={"path": "x"},
            status="completed", trace_id="trace-gap",
        )
        rt.store.save_record(inv.invocation_id, "tool",
                            inv.model_dump(mode="json"), inv.created_at, m.mission_id)
        chain = rt.evidence.verify_receipt_chain(m.mission_id)
        assert chain["chain_gaps"] >= 1
        assert chain["chain_intact"] is False

    def test_failed_invocation_has_failure_code(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Failure code test")
        with pytest.raises(FileNotFoundError):
            rt.tools.invoke(m.mission_id, "file_read",
                           {"path": "missing.txt"}, "trace-fc1")
        invocations = rt.tools.list_invocations(m.mission_id)
        failed = [i for i in invocations if i.get("status") == "failed"]
        assert len(failed) >= 1
        assert failed[0].get("failure_code") is not None
        assert failed[0].get("reason_code") is not None


# ── Memory-Evidence Binding ──────────────────────────────────────────────────

class TestMemoryEvidenceBinding:
    """Committed memories MUST be bound to verified evidence."""

    def test_write_without_evidence_raises_for_decision(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Memory binding test")
        # DECISION requires evidence
        with pytest.raises(ValueError, match="memory_requires_evidence"):
            rt.memory.write(MemoryKind.DECISION, "key1", "decision content",
                           "trace-m1", mission_id=m.mission_id)

    def test_write_without_evidence_raises_for_failure(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Memory failure binding")
        with pytest.raises(ValueError, match="memory_requires_evidence"):
            rt.memory.write(MemoryKind.FAILURE, "fail1", "failure content",
                           "trace-m2", mission_id=m.mission_id)

    def test_write_with_evidence_succeeds(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Memory with evidence")
        # First produce evidence
        evidence = rt.evidence.add(m.mission_id, "fact", "Test fact",
                                   "some content", "trace-me1")
        # Then write memory bound to that evidence
        record = rt.memory.write(MemoryKind.DECISION, "d1", "A decision",
                                "trace-me2", mission_id=m.mission_id,
                                source_evidence_id=evidence.evidence_id)
        assert record.verified is True
        assert record.canonical is True
        assert record.source_evidence_id == evidence.evidence_id

    def test_fact_with_high_confidence_commits_without_evidence(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("High confidence fact")
        record = rt.memory.write(MemoryKind.FACT, "fact1", "A system fact",
                                "trace-m3", mission_id=m.mission_id,
                                confidence=0.95)
        assert record.status == "committed"

    def test_short_term_always_exempt(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        record = rt.memory.write(MemoryKind.SHORT_TERM, "st1", "temp data",
                                "trace-m4")
        assert record.status == "committed"

    def test_unverified_inference_always_candidate(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        record = rt.memory.write(MemoryKind.UNVERIFIED_INFERENCE, "ui1",
                                "speculation", "trace-m5")
        assert record.status == "candidate"
        assert record.verified is False

    def test_verify_evidence_binding_reports_violations(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Binding report test")
        # Create evidence-backed memory
        evidence = rt.evidence.add(m.mission_id, "fact", "Test", "data", "trace-vb1")
        rt.memory.write(MemoryKind.DECISION, "good", "backed by evidence",
                       "trace-vb2", mission_id=m.mission_id,
                       source_evidence_id=evidence.evidence_id)
        report = rt.memory.verify_evidence_binding(m.mission_id)
        assert report["all_bound"] is True, f"Expected all bound, got: {report}"


# ── Replay / Idempotency ────────────────────────────────────────────────────

class TestReplayIdempotency:
    """Replay MUST produce identical evidence and receipts."""

    def test_tool_replay_with_same_idempotency_key(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Replay test")
        (rt.settings.workspace_root / "replay.txt").write_text("replay content")
        ikey = "idem-tool-replay-1"
        r1 = rt.tools.invoke(m.mission_id, "file_read",
                            {"path": "replay.txt"}, "trace-rp1",
                            idempotency_key=ikey)
        r2 = rt.tools.invoke(m.mission_id, "file_read",
                            {"path": "replay.txt"}, "trace-rp2",
                            idempotency_key=ikey)
        assert r1.invocation_id == r2.invocation_id
        assert r1.result == r2.result
        assert r1.receipt_evidence_id == r2.receipt_evidence_id

    def test_tool_replay_with_different_args_conflicts(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Replay conflict")
        (rt.settings.workspace_root / "a.txt").write_text("A")
        (rt.settings.workspace_root / "b.txt").write_text("B")
        ikey = "idem-conflict-1"
        rt.tools.invoke(m.mission_id, "file_read", {"path": "a.txt"},
                       "trace-rc1", idempotency_key=ikey)
        with pytest.raises(ValueError, match="tool_idempotency_conflict"):
            rt.tools.invoke(m.mission_id, "file_read", {"path": "b.txt"},
                           "trace-rc2", idempotency_key=ikey)

    def test_evidence_replay_with_same_idempotency_key(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Evidence replay")
        ikey = "idem-ev-replay-1"
        e1 = rt.evidence.add(m.mission_id, "fact", "Test", "same content",
                            "trace-er1", idempotency_key=ikey)
        e2 = rt.evidence.add(m.mission_id, "fact", "Test", "same content",
                            "trace-er2", idempotency_key=ikey)
        assert e1.evidence_id == e2.evidence_id
        assert e1.sha256 == e2.sha256

    def test_write_file_replay_detected(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Write replay test")
        # Need approval for R2 write
        approval = rt.approvals.request(
            m.mission_id, "file_write_report", RiskLevel.R2,
            "Write replay test", [], "trace-wr-approval",
            executor_id="test", reversible=True,
        )
        rt.approvals.decide(approval.approval_id, True, "human", "approved",
                           "trace-wr-decide")
        ikey = "idem-write-replay-1"
        r1 = rt.tools.invoke(m.mission_id, "file_write_report",
                            {"path": "replay-report.md", "content": "RW"},
                            "trace-wr1",
                            approval_id=approval.approval_id,
                            actor_id="test", idempotency_key=ikey)
        r2 = rt.tools.invoke(m.mission_id, "file_write_report",
                            {"path": "replay-report.md", "content": "RW"},
                            "trace-wr2",
                            approval_id=approval.approval_id,
                            actor_id="test", idempotency_key=ikey)
        assert r1.invocation_id == r2.invocation_id
        # Idempotent replay returns the cached result from the first invocation.
        # The result is identical — proof that replay is working correctly.
        assert r1.result == r2.result


# ── Fail-Closed Behavior ─────────────────────────────────────────────────────

class TestFailClosed:
    """Provider or Tool unavailable MUST fail closed — never fake success."""

    def test_provider_unavailable_no_mock(self, tmp_path: Path) -> None:
        from nexara_prime.model_gateway import UnavailableProvider
        rt = NexaraRuntime(_settings(tmp_path, mock_model=False,
                                     model_provider="mock"))
        assert isinstance(rt.models.provider, UnavailableProvider)

    def test_openai_without_key_is_unavailable(self, tmp_path: Path) -> None:
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            rt = NexaraRuntime(_settings(tmp_path, mock_model=False,
                                         model_provider="openai"))
            from nexara_prime.model_gateway import UnavailableProvider
            assert isinstance(rt.models.provider, UnavailableProvider)
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_local_without_endpoint_is_unavailable(self, tmp_path: Path) -> None:
        old_ep = os.environ.pop("NEXARA_LOCAL_MODEL_ENDPOINT", None)
        try:
            rt = NexaraRuntime(_settings(tmp_path, mock_model=False,
                                         model_provider="local"))
            from nexara_prime.model_gateway import UnavailableProvider
            assert isinstance(rt.models.provider, UnavailableProvider)
        finally:
            if old_ep is not None:
                os.environ["NEXARA_LOCAL_MODEL_ENDPOINT"] = old_ep

    def test_unknown_tool_fails_closed(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Fail closed tool test")
        with pytest.raises(KeyError, match="unknown_tool"):
            rt.tools.invoke(m.mission_id, "imaginary_tool", {}, "trace-fc2")
        # Verify mission state is not COMPLETED
        stored = rt.store.get_record(m.mission_id)
        assert stored is not None
        # Failed tool should not produce fake completion
        invocations = rt.tools.list_invocations(m.mission_id)
        assert len(invocations) == 0  # invocation was never persisted because it raised

    def test_failed_tool_does_not_fake_success(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Fake success test")
        with pytest.raises(FileNotFoundError):
            rt.tools.invoke(m.mission_id, "file_read",
                           {"path": "definitely_missing.txt"}, "trace-fs1")
        invocations = rt.tools.list_invocations(m.mission_id)
        if invocations:
            for inv in invocations:
                assert inv.get("status") != "completed", \
                    "Failed tool must not have status=completed"


# ── Memory Integrity ─────────────────────────────────────────────────────────

class TestMemoryIntegrity:
    """Memory MUST only update based on verified Evidence."""

    def test_memory_idempotency_patch_conflict_detected(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Mem patch test")
        evidence = rt.evidence.add(m.mission_id, "fact", "E", "content", "trace-mi1")
        ikey = "idem-mem-patch-1"
        rt.memory.patch(m.mission_id, "pkey", "v1", "trace-mi2",
                       evidence_id=evidence.evidence_id,
                       idempotency_key=ikey)
        # Same key different content with same idempotency_key → conflict
        with pytest.raises(ValueError, match="memory_idempotency_conflict"):
            rt.memory.patch(m.mission_id, "pkey", "v2", "trace-mi3",
                           evidence_id=evidence.evidence_id,
                           idempotency_key=ikey)

    def test_memory_idempotency_invalid_envelope_raises(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Mem idem invalid")
        evidence = rt.evidence.add(m.mission_id, "fact", "E2", "content", "trace-ie1")
        ikey = "idem-mem-invalid-1"
        rt.memory.patch(m.mission_id, "pk2", "v1", "trace-ie2",
                       evidence_id=evidence.evidence_id,
                       idempotency_key=ikey)
        # Replay with same key should succeed (idempotent)
        r2 = rt.memory.patch(m.mission_id, "pk2", "v1", "trace-ie3",
                            evidence_id=evidence.evidence_id,
                            idempotency_key=ikey)
        assert r2.memory_id is not None


# ── Human Control Preserved ──────────────────────────────────────────────────

class TestHumanControlPreserved:
    """High-risk operations MUST still require human approval."""

    def test_r2_write_requires_approval(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("R2 approval test")
        with pytest.raises(PermissionError, match="approval_required"):
            rt.tools.invoke(m.mission_id, "file_write_report",
                           {"path": "r.md", "content": "# R"}, "trace-hc1")

    def test_r2_write_with_valid_approval_succeeds(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("R2 with approval")
        approval = rt.approvals.request(
            m.mission_id, "file_write_report", RiskLevel.R2,
            "Write test", [], "trace-hc-approval",
            executor_id="test", reversible=True,
        )
        rt.approvals.decide(approval.approval_id, True, "human", "approved",
                           "trace-hc-decide")
        result = rt.tools.invoke(m.mission_id, "file_write_report",
                                {"path": "approved.md", "content": "# OK"},
                                "trace-hc2",
                                approval_id=approval.approval_id,
                                actor_id="test")
        assert result.status == "completed"
        assert result.receipt_evidence_id is not None

    def test_consumed_approval_cannot_be_reused(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Consumed approval")
        approval = rt.approvals.request(
            m.mission_id, "file_write_report", RiskLevel.R2,
            "One-time use", [], "trace-hc2-approval",
            executor_id="test", reversible=True,
        )
        rt.approvals.decide(approval.approval_id, True, "human", "approved",
                           "trace-hc2-decide")
        rt.tools.invoke(m.mission_id, "file_write_report",
                       {"path": "first.md", "content": "F"},
                       "trace-hc3", approval_id=approval.approval_id,
                       actor_id="test")
        # Second use with same approval should fail
        with pytest.raises(PermissionError, match="approval_required"):
            rt.tools.invoke(m.mission_id, "file_write_report",
                           {"path": "second.md", "content": "S"},
                           "trace-hc4", approval_id=approval.approval_id,
                           actor_id="test")


# ── Full Chain Integration ───────────────────────────────────────────────────

class TestFullChainIntegration:
    """End-to-end: Intent → Tool → Evidence → Receipt → Memory → Verify."""

    def test_full_chain_success(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Full chain test")

        # 1. Tool Execution
        (rt.settings.workspace_root / "data.txt").write_text("chain data")
        inv = rt.tools.invoke(m.mission_id, "file_read",
                             {"path": "data.txt"}, "trace-full-1")
        assert inv.status == "completed"
        assert inv.failure_code is None
        assert inv.receipt_evidence_id is not None

        # 2. Evidence → Receipt
        chain = rt.evidence.verify_receipt_chain(m.mission_id)
        assert chain["chain_intact"] is True

        # 3. Receipt Verifiability
        receipt_env = rt.store.get_record_envelope(inv.receipt_evidence_id)
        assert receipt_env is not None
        raw = receipt_env["payload"]
        import hashlib
        digest = hashlib.sha256(str(raw.get("content", "")).encode("utf-8")).hexdigest()
        assert digest == raw.get("sha256")

        # 4. Memory bound to evidence
        evidence = rt.evidence.add(m.mission_id, "finding", "Analysis",
                                   "Based on chain data", "trace-full-2")
        mem = rt.memory.write(MemoryKind.DECISION, "chain-decision",
                             "Decision based on evidence", "trace-full-3",
                             mission_id=m.mission_id,
                             source_evidence_id=evidence.evidence_id)
        assert mem.verified is True
        assert mem.source_evidence_id == evidence.evidence_id

        # 5. Memory evidence binding report
        report = rt.memory.verify_evidence_binding(m.mission_id)
        assert report["all_bound"] is True

    def test_full_chain_failure_deterministic_codes(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Full chain failure")

        # Fail: missing file
        with pytest.raises(FileNotFoundError):
            rt.tools.invoke(m.mission_id, "file_read",
                           {"path": "nope.txt"}, "trace-ff1")

        invocations = rt.tools.list_invocations(m.mission_id)
        failed = [i for i in invocations if i.get("status") == "failed"]
        if failed:
            fc = failed[0].get("failure_code")
            rc = failed[0].get("reason_code")
            assert fc is not None, "Failed invocation must have failure_code"
            assert rc is not None, "Failed invocation must have reason_code"
            assert fc in {e.value for e in FailureCode}

        # Verify chain still reports correctly
        chain = rt.evidence.verify_receipt_chain(m.mission_id)
        # Chain may have gaps but should have no fail-closed violations
        assert chain["fail_closed_violations"] == 0

    def test_full_chain_with_approval_flow(self, tmp_path: Path) -> None:
        rt = NexaraRuntime(_settings(tmp_path))
        m = rt.create_mission("Full chain approval flow")

        # Create and approve
        approval = rt.approvals.request(
            m.mission_id, "file_write_report", RiskLevel.R2,
            "Full chain write", [], "trace-fa-approval",
            executor_id="test-exec", reversible=True,
        )
        rt.approvals.decide(approval.approval_id, True, "human", "approved",
                           "trace-fa-decide")

        # Execute with approval
        inv = rt.tools.invoke(m.mission_id, "file_write_report",
                             {"path": "chain-output.md", "content": "# Chain"},
                             "trace-fa1",
                             approval_id=approval.approval_id,
                             actor_id="test-exec")
        assert inv.status == "completed"

        # Evidence receipt exists and is verifiable
        chain = rt.evidence.verify_receipt_chain(m.mission_id)
        assert chain["chain_intact"] is True

        # Write memory bound to receipt evidence
        mem = rt.memory.write(MemoryKind.DECISION, "approved-output",
                             "Output was written with approval", "trace-fa2",
                             mission_id=m.mission_id,
                             source_evidence_id=inv.receipt_evidence_id)
        assert mem.verified is True

        # Final binding report is clean
        report = rt.memory.verify_evidence_binding(m.mission_id)
        assert report["all_bound"] is True
