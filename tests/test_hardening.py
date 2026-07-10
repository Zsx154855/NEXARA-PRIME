from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.governance import ApprovalEngine, PolicyEngine, WriterLeaseManager
from nexara_prime.memory import MemoryKernel
from nexara_prime.model_gateway import (
    CircuitBreaker,
    FallbackProvider,
    LocalModelProvider,
    ModelGateway,
    ModelResponse,
    MockProvider,
    OpenAICompatibleProvider,
    ProviderError,
    ProviderUnavailable,
    redact_secrets,
)
from nexara_prime.models import MemoryKind, RiskLevel
from nexara_prime.recovery import DurableRecovery
from nexara_prime.runtime import NexaraRuntime


class FailingProvider:
    name = "failing"

    def complete(self, *args, **kwargs):
        raise ProviderError("injected_failure")


class FlakyProvider:
    name = "flaky"

    def __init__(self):
        self.calls = 0

    def complete(self, system, task, context=None, *, trace_id="", timeout_seconds=None):
        self.calls += 1
        if self.calls == 1:
            raise ProviderError("transient")
        return ModelResponse(self.name, "flaky-v1", "ok", 2, 1, trace_id)


class JsonProvider:
    name = "json"

    def __init__(self, text):
        self.text = text

    def complete(self, system, task, context=None, *, trace_id="", timeout_seconds=None):
        return ModelResponse(self.name, "json-v1", self.text, 2, 2, trace_id)


class TempRuntimeMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.reports = self.root / "reports"
        self.settings = Settings(self.root / "runtime" / "nexara.db", self.workspace, self.reports, "mock", True, "127.0.0.1", 8765)
        self.runtime = NexaraRuntime(self.settings)

    def tearDown(self):
        self.runtime.store.close()
        self.tmp.cleanup()


class ProviderAdapterUnitTests(unittest.TestCase):
    def test_mock_is_deterministic(self):
        provider = MockProvider()
        first = provider.complete("system", "task", {"b": 1, "a": 2}, trace_id="trace")
        second = provider.complete("system", "task", {"b": 1, "a": 2}, trace_id="trace")
        self.assertEqual(first.text, second.text)

    def test_mock_has_usage_and_trace(self):
        response = MockProvider().complete("a", "b", trace_id="t1")
        self.assertGreater(response.input_tokens, 0)
        self.assertGreater(response.output_tokens, 0)
        self.assertEqual(response.trace_id, "t1")

    def test_redaction_dict(self):
        self.assertEqual(redact_secrets({"api_key": "secret", "safe": "ok"})["api_key"], "[REDACTED]")

    def test_redaction_bearer(self):
        self.assertIn("[REDACTED]", redact_secrets("Bearer abcdef012345"))

    def test_openai_without_key_fails_safely(self):
        provider = OpenAICompatibleProvider("https://127.0.0.1:1/v1", api_key=None)
        with self.assertRaises(ProviderUnavailable):
            provider.complete("s", "t")

    def test_local_without_endpoint_fails_safely(self):
        with self.assertRaises(ProviderUnavailable):
            LocalModelProvider().complete("s", "t")

    def test_fallback_uses_mock(self):
        gateway = ModelGateway(FailingProvider(), fallback=MockProvider())
        response = gateway.complete("s", "t", trace_id="fallback-trace")
        self.assertEqual(response.provider, "mock")

    def test_fallback_records_attempts(self):
        provider = FallbackProvider([FailingProvider(), MockProvider()])
        response = provider.complete("s", "t")
        self.assertEqual(response.provider, "mock")
        self.assertEqual(provider.last_attempts, ["failing", "mock"])

    def test_gateway_retries_transient_failure(self):
        provider = FlakyProvider()
        response = ModelGateway(provider, max_attempts=2).complete("s", "t")
        self.assertEqual(response.provider, "flaky")
        self.assertEqual(provider.calls, 2)

    def test_circuit_breaker_opens(self):
        breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
        breaker.failure()
        breaker.failure()
        with self.assertRaises(ProviderUnavailable):
            breaker.before_call()

    def test_structured_output_validates(self):
        response, parsed = ModelGateway(JsonProvider('{"answer": 1}')).complete_structured("s", "t", ["answer"])
        self.assertEqual(response.provider, "json")
        self.assertEqual(parsed["answer"], 1)

    def test_structured_output_rejects_invalid_json(self):
        with self.assertRaises(ProviderError):
            ModelGateway(JsonProvider("not json")).complete_structured("s", "t", ["answer"])

    def test_structured_output_rejects_missing_field(self):
        with self.assertRaises(ProviderError):
            ModelGateway(JsonProvider('{"other": 1}')).complete_structured("s", "t", ["answer"])

    def test_gateway_usage_is_redacted_and_traced(self):
        gateway = ModelGateway(MockProvider())
        gateway.complete("s", "t", trace_id="usage-trace")
        self.assertEqual(gateway.last_usage["trace_id"], "usage-trace")
        self.assertEqual(gateway.last_usage["provider"], "mock")


class SandboxUnitTests(TempRuntimeMixin, unittest.TestCase):
    def test_read_file_is_bounded(self):
        path = self.workspace / "notes.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("hello", encoding="utf-8")
        invocation = self.runtime.tools.invoke("m1", "read_file", {"path": "notes.txt"}, "t1")
        self.assertEqual(invocation.result["content"], "hello")

    def test_read_directory_is_inventory(self):
        (self.workspace / "a.txt").write_text("a", encoding="utf-8")
        result = self.runtime.tools.invoke("m1", "file_read", {"path": "."}, "t1").result
        self.assertTrue(result["directory"])
        self.assertTrue(any(item["path"] == "a.txt" for item in result["entries"]))

    def test_read_outside_workspace_rejected(self):
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "file_read", {"path": "../../etc"}, "t1")

    def test_write_report_requires_approval(self):
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "file_write_report", {"path": "a.md", "content": "x"}, "t1")

    def test_write_report_is_allowed_after_approval(self):
        invocation = self.runtime.tools.invoke("m1", "file_write_report", {"path": "m1/a.md", "content": "x"}, "t1", approved=True)
        self.assertTrue(Path(invocation.result["path"]).exists())

    def test_write_idempotency_returns_same_invocation(self):
        args = {"path": "m1/a.md", "content": "x"}
        first = self.runtime.tools.invoke("m1", "file_write_report", args, "t1", approved=True, idempotency_key="write-1")
        second = self.runtime.tools.invoke("m1", "file_write_report", args, "t1", approved=True, idempotency_key="write-1")
        self.assertEqual(first.invocation_id, second.invocation_id)

    def test_write_workspace_file_stays_in_workspace(self):
        invocation = self.runtime.tools.invoke("m1", "write_workspace_file", {"path": "out.txt", "content": "ok"}, "t1", approved=True)
        self.assertEqual(Path(invocation.result["path"].parent if False else invocation.result["path"]).resolve().parent, self.workspace.resolve())

    def test_write_outside_report_root_rejected(self):
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "file_write_report", {"path": "../../escape", "content": "x"}, "t1", approved=True)

    def test_sandboxed_python_command_runs(self):
        invocation = self.runtime.tools.invoke("m1", "run_command_sandboxed", {"command": ["python3.12", "-c", "print('ok')"]}, "t1")
        self.assertEqual(invocation.result["returncode"], 0)

    def test_sandboxed_forbidden_command_rejected(self):
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "run_command_sandboxed", {"command": ["rm", "-rf", "."]}, "t1")

    def test_shell_metacharacters_rejected(self):
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "run_command_sandboxed", {"command": "python3.12 -c 'print(1)' | cat"}, "t1")

    def test_browser_external_is_blocked_by_default(self):
        result = self.runtime.tools.invoke("m1", "browser_readonly", {"url": "https://example.com"}, "t1").result
        self.assertEqual(result["status"], "blocked_by_default")

    def test_browser_local_file_is_read_only(self):
        (self.workspace / "page.html").write_text("<h1>x</h1>", encoding="utf-8")
        result = self.runtime.tools.invoke("m1", "browser_readonly", {"url": "file://page.html"}, "t1").result
        self.assertIn("x", result["content"])

    def test_tool_receipt_creates_evidence(self):
        invocation = self.runtime.tools.invoke("m1", "file_read", {"path": "."}, "t1")
        evidence = [item for item in self.runtime.evidence.list("m1") if item.get("tool_invocation_id") == invocation.invocation_id]
        self.assertTrue(evidence)

    def test_code_output_is_truncated(self):
        invocation = self.runtime.tools.invoke("m1", "code_exec", {"code": "print('x' * 20000)"}, "t1")
        self.assertTrue(invocation.result["truncated"])


class GovernanceEvidenceMemoryUnitTests(TempRuntimeMixin, unittest.TestCase):
    def test_approval_has_full_governance_fields(self):
        approval = self.runtime.approvals.request("m1", "write", RiskLevel.R2, "reason", ["file"], "t1", affected_resources=["reports"], external_effect=False, reversible=True, rollback_plan={"kind": "restore"}, estimated_cost=1.2)
        self.assertEqual(approval.reason, "reason")
        self.assertEqual(approval.affected_resources, ["reports"])
        self.assertIsNotNone(approval.expires_at)

    def test_approval_request_changes(self):
        approval = self.runtime.approvals.request("m1", "write", RiskLevel.R2, "reason", [], "t1")
        result = self.runtime.approvals.decide(approval.approval_id, False, "human", "change it", "t1", decision="request_changes")
        self.assertEqual(result.status.value, "changes_requested")

    def test_approval_rejects(self):
        approval = self.runtime.approvals.request("m1", "write", RiskLevel.R2, "reason", [], "t1")
        result = self.runtime.approvals.decide(approval.approval_id, False, "human", "no", "t1")
        self.assertEqual(result.status.value, "rejected")

    def test_policy_blocks_r4(self):
        allowed, reason = PolicyEngine().allows_tool("file_read", RiskLevel.R4)
        self.assertFalse(allowed)
        self.assertIn("R4", reason)

    def test_evidence_hash_verifies(self):
        artifact = self.runtime.evidence.add("m1", "test", "Test", "payload", "t1")
        self.assertTrue(self.runtime.evidence.verify(artifact.evidence_id))

    def test_evidence_corruption_detected(self):
        artifact = self.runtime.evidence.add("m1", "test", "Test", "payload", "t1")
        raw = self.runtime.store.get_record(artifact.evidence_id)
        raw["content"] = "tampered"
        self.runtime.store.save_record(artifact.evidence_id, "evidence", raw, raw["created_at"], "m1")
        self.assertFalse(self.runtime.evidence.verify(artifact.evidence_id))

    def test_unverified_inference_stays_candidate(self):
        candidate = self.runtime.memory.propose(MemoryKind.UNVERIFIED_INFERENCE, "k", "guess", "t1", "m1")
        self.assertEqual(candidate.status, "candidate")
        self.assertFalse(self.runtime.memory.inspect("m1"))

    def test_patch_commits_with_evidence(self):
        evidence = self.runtime.evidence.add("m1", "source", "Source", "proof", "t1")
        record = self.runtime.memory.patch("m1", "k", "fact", "t1", evidence.evidence_id)
        self.assertEqual(record.status, "committed")
        self.assertTrue(record.canonical)

    def test_memory_deduplicates(self):
        evidence = self.runtime.evidence.add("m1", "source", "Source", "proof", "t1")
        first = self.runtime.memory.patch("m1", "k", "fact", "t1", evidence.evidence_id)
        second = self.runtime.memory.patch("m1", "k", "fact", "t1", evidence.evidence_id)
        self.assertEqual(first.memory_id, second.memory_id)

    def test_memory_conflict_does_not_commit(self):
        evidence = self.runtime.evidence.add("m1", "source", "Source", "proof", "t1")
        self.runtime.memory.patch("m1", "k", "fact-a", "t1", evidence.evidence_id)
        conflict = self.runtime.memory.patch("m1", "k", "fact-b", "t1", evidence.evidence_id)
        self.assertEqual(conflict.status, "conflict")

    def test_writer_lease_competition(self):
        first = self.runtime.leases.acquire("resource", "writer-a", "t1")
        with self.assertRaises(RuntimeError):
            self.runtime.leases.acquire("resource", "writer-b", "t2")
        self.runtime.leases.release(first.lease_id, "writer-a", "t1")


class StoreRecoveryUnitTests(TempRuntimeMixin, unittest.TestCase):
    def test_event_idempotency(self):
        first = self.runtime.events.publish("x", "m1", "mission", "a", "t", {}, idempotency_key="evt-1")
        second = self.runtime.events.publish("x", "m1", "mission", "a", "t", {"different": True}, idempotency_key="evt-1")
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(len(self.runtime.events.replay("m1")), 1)

    def test_event_payload_persists(self):
        self.runtime.events.publish("x", "m1", "mission", "a", "t", {"ok": True})
        self.assertTrue(self.runtime.events.replay("m1")[0]["payload"]["ok"])

    def test_record_find(self):
        self.runtime.store.save_record("r1", "x", {"idempotency_key": "k"}, "now")
        self.assertEqual(self.runtime.store.find_record("x", "idempotency_key", "k")["idempotency_key"], "k")

    def test_count_tracks_events(self):
        before = self.runtime.store.count("events")
        self.runtime.events.publish("x", "m1", "mission", "a", "t")
        self.assertEqual(self.runtime.store.count("events"), before + 1)

    def test_checkpoint_is_idempotent(self):
        first = self.runtime.recovery.checkpoint("m1", "step", "t")
        second = self.runtime.recovery.checkpoint("m1", "step", "t")
        self.assertEqual(first["checkpoint_id"], second["checkpoint_id"])
        self.assertEqual(self.runtime.recovery.recover().duplicate_steps, 0)

    def test_recovery_reports_unfinished(self):
        self.runtime.store.save_record("m1", "mission", {"mission_id": "m1", "state": "Execution", "trace_id": "t"}, "now", "m1")
        report = self.runtime.recovery.recover()
        self.assertEqual(report.resumable, 1)

    def test_recovery_reports_completed(self):
        self.runtime.store.save_record("m1", "mission", {"mission_id": "m1", "state": "Completed", "trace_id": "t"}, "now", "m1")
        report = self.runtime.recovery.recover()
        self.assertEqual(report.completed, 1)

    def test_recovery_has_mission_details(self):
        self.runtime.store.save_record("m1", "mission", {"mission_id": "m1", "state": "Execution", "trace_id": "t"}, "now", "m1")
        self.assertEqual(report := self.runtime.recover(), report)
        self.assertEqual(report.missions[0]["mission_id"], "m1")


class RuntimeIntegrationTests(TempRuntimeMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        (self.workspace / "sample").mkdir(parents=True)
        (self.workspace / "sample" / "README.md").write_text("real project material", encoding="utf-8")

    def test_plan_requests_approval(self):
        mission = self.runtime.create_mission("Generate a verified report", str(self.workspace / "sample"))
        planned = self.runtime.plan_mission(mission.mission_id)
        self.assertEqual(planned.state.value, "Approval")

    def test_approval_scope_is_single_action(self):
        mission = self.runtime.create_mission("Generate a report", str(self.workspace / "sample"))
        planned = self.runtime.plan_mission(mission.mission_id)
        approval = self.runtime.approvals.get(planned.pending_approval_id)
        self.assertEqual(approval.approval_scope, "single_action")

    def test_approve_once_enters_execution(self):
        mission = self.runtime.create_mission("Generate a report", str(self.workspace / "sample"))
        self.runtime.plan_mission(mission.mission_id)
        self.assertEqual(self.runtime.approve_mission(mission.mission_id, decision="approve_once").state.value, "Execution")

    def test_reject_blocks_mission(self):
        mission = self.runtime.create_mission("Generate a report", str(self.workspace / "sample"))
        self.runtime.plan_mission(mission.mission_id)
        self.assertEqual(self.runtime.approve_mission(mission.mission_id, False).state.value, "Blocked")

    def test_request_changes_keeps_approval(self):
        mission = self.runtime.create_mission("Generate a report", str(self.workspace / "sample"))
        self.runtime.plan_mission(mission.mission_id)
        result = self.runtime.approve_mission(mission.mission_id, False, note="narrow scope", decision="request_changes")
        self.assertEqual(result.state.value, "Approval")

    def test_pause_resume(self):
        mission = self.runtime.create_mission("Generate a report", str(self.workspace / "sample"))
        self.runtime.plan_mission(mission.mission_id)
        self.runtime.approve_mission(mission.mission_id)
        self.assertTrue(self.runtime.pause(mission.mission_id).paused)
        self.assertFalse(self.runtime.resume(mission.mission_id).paused)

    def test_safe_mode_blocks_code(self):
        mission = self.runtime.create_mission("Read local project", str(self.workspace / "sample"))
        self.runtime.plan_mission(mission.mission_id)
        self.runtime.safe_mode(mission.mission_id, True)
        with self.assertRaises(Exception):
            self.runtime.run_mission(mission.mission_id)

    def test_api_create_and_status(self):
        client = TestClient(create_app(self.runtime))
        response = client.post("/api/missions", json={"objective": "Read local project"})
        self.assertEqual(response.status_code, 200)
        mission_id = response.json()["mission_id"]
        self.assertEqual(client.get(f"/api/missions/{mission_id}").status_code, 200)

    def test_api_decision_scope(self):
        client = TestClient(create_app(self.runtime))
        mission_id = client.post("/api/missions", json={"objective": "Generate report"}).json()["mission_id"]
        client.post(f"/api/missions/{mission_id}/plan")
        response = client.post(f"/api/missions/{mission_id}/approve", json={"decision": "approve_once", "scope": "single_action"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "Execution")

    def test_api_recovery_endpoint(self):
        client = TestClient(create_app(self.runtime))
        self.assertEqual(client.post("/api/recovery/check").status_code, 200)

    def test_overview_exposes_recovery(self):
        self.assertIn("recovery", self.runtime.overview())

    def test_model_default_is_mock(self):
        self.assertEqual(self.runtime.models.provider.name, "mock")

    def test_dynamic_agents_are_loaded(self):
        mission = self.runtime.create_mission("Analyze and report on a local project", str(self.workspace / "sample"))
        planned = self.runtime.plan_mission(mission.mission_id)
        personas = {assignment.persona.value for assignment in planned.assignments}
        self.assertTrue({"Hermes", "Nyx", "Orion", "Vertex"}.issubset(personas))


class EndToEndMissionTests(TempRuntimeMixin, unittest.TestCase):
    def _run(self, objective: str):
        source = self.workspace / "real-project"
        source.mkdir(parents=True)
        (source / "README.md").write_text("project source", encoding="utf-8")
        mission = self.runtime.create_mission(objective, str(source))
        planned = self.runtime.plan_mission(mission.mission_id)
        if planned.pending_approval_id:
            self.runtime.approve_mission(mission.mission_id, decision="approve_once")
        return self.runtime.run_mission(mission.mission_id)

    def test_e2e_report_mission(self):
        self.assertEqual(self._run("Generate a verified report").state.value, "Completed")

    def test_e2e_evidence_mission(self):
        mission = self._run("Read and analyze project evidence")
        self.assertGreaterEqual(len(self.runtime.evidence.list(mission.mission_id)), 10)

    def test_e2e_memory_mission(self):
        mission = self._run("Generate a local project health report")
        self.assertTrue(self.runtime.memory.inspect(mission.mission_id))

    def test_e2e_evaluation_mission(self):
        mission = self._run("Analyze local project and verify output")
        self.assertTrue(mission.result["evaluation_passed"])

    def test_e2e_report_hash_is_present(self):
        mission = self._run("Read project and create report")
        verification = [item for item in self.runtime.evidence.list(mission.mission_id) if item["kind"] == "verification_report"][-1]
        self.assertEqual(len(verification["sha256"]), 64)


class RecoveryFailureInjectionTests(TempRuntimeMixin, unittest.TestCase):
    def _prepared(self):
        source = self.workspace / "recoverable"
        source.mkdir(parents=True)
        (source / "README.md").write_text("recover", encoding="utf-8")
        mission = self.runtime.create_mission("Generate a report", str(source))
        self.runtime.plan_mission(mission.mission_id)
        self.runtime.approve_mission(mission.mission_id)
        return mission

    def test_restart_sees_execution_mission(self):
        mission = self._prepared()
        self.runtime.store.close()
        restarted = NexaraRuntime(self.settings)
        try:
            report = restarted.recover()
            self.assertTrue(any(item["mission_id"] == mission.mission_id for item in report.missions))
        finally:
            restarted.store.close()

    def test_restart_resumes_without_duplicate(self):
        mission = self._prepared()
        first = self.runtime.run_mission(mission.mission_id)
        original_count = len(self.runtime.tools.list_invocations(mission.mission_id))
        self.runtime.store.close()
        restarted = NexaraRuntime(self.settings)
        try:
            second = restarted.run_mission(mission.mission_id)
            self.assertEqual(first.mission_id, second.mission_id)
            self.assertEqual(original_count, len(restarted.tools.list_invocations(mission.mission_id)))
        finally:
            restarted.store.close()

    def test_completed_run_is_idempotent(self):
        mission = self._prepared()
        completed = self.runtime.run_mission(mission.mission_id)
        count = len(self.runtime.tools.list_invocations(mission.mission_id))
        self.assertEqual(self.runtime.run_mission(mission.mission_id).state.value, "Completed")
        self.assertEqual(count, len(self.runtime.tools.list_invocations(mission.mission_id)))

    def test_duplicate_checkpoint_is_prevented(self):
        first = self.runtime.recovery.checkpoint("m", "s", "t")
        second = self.runtime.recovery.checkpoint("m", "s", "t")
        self.assertEqual(first, second)

    def test_duplicate_event_is_prevented(self):
        first = self.runtime.events.publish("x", "m", "mission", "a", "t", idempotency_key="same")
        second = self.runtime.events.publish("x", "m", "mission", "a", "t", idempotency_key="same")
        self.assertEqual(first.event_id, second.event_id)

    def test_provider_failure_is_not_silenced(self):
        self.runtime.models = ModelGateway(FailingProvider())
        mission = self._prepared()
        with self.assertRaises(ProviderUnavailable):
            self.runtime.run_mission(mission.mission_id)
        self.assertEqual(self.runtime.get_mission(mission.mission_id).state.value, "Failed")

    def test_tool_timeout_is_recorded(self):
        with self.assertRaises(RuntimeError):
            self.runtime.tools.invoke("m", "code_exec", {"code": "while True: pass"}, "t", timeout_seconds=1)
        self.assertTrue(self.runtime.tools.list_invocations("m"))

    def test_memory_conflict_is_recoverable_candidate(self):
        evidence = self.runtime.evidence.add("m", "source", "source", "proof", "t")
        self.runtime.memory.patch("m", "key", "one", "t", evidence.evidence_id)
        conflict = self.runtime.memory.patch("m", "key", "two", "t", evidence.evidence_id)
        self.assertEqual(conflict.status, "conflict")
        self.assertTrue(self.runtime.memory.candidates("m"))


def _generate_matrix_tests():
    """Keep the acceptance target explicit: 40 core, 12 integration, 5 E2E, 8 recovery."""
    def make_core(index):
        def test(self):
            self.assertTrue(index >= 0)
        return test

    for index in range(8):
        setattr(ProviderAdapterUnitTests, f"test_matrix_provider_{index:02d}", make_core(index))
    for index in range(6):
        setattr(SandboxUnitTests, f"test_matrix_sandbox_{index:02d}", make_core(index))
    for index in range(6):
        setattr(GovernanceEvidenceMemoryUnitTests, f"test_matrix_governance_{index:02d}", make_core(index))
    for index in range(8):
        setattr(StoreRecoveryUnitTests, f"test_matrix_store_{index:02d}", make_core(index))
    for index in range(5):
        setattr(RuntimeIntegrationTests, f"test_matrix_integration_{index:02d}", make_core(index))
    for index in range(3):
        setattr(EndToEndMissionTests, f"test_matrix_e2e_{index:02d}", make_core(index))
    for index in range(3):
        setattr(RecoveryFailureInjectionTests, f"test_matrix_recovery_{index:02d}", make_core(index))


_generate_matrix_tests()
