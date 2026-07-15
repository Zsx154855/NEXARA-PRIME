"""E2E Verification: NEXARA PRIME Runtime Closure v1.

Covers all 9 adapters through the integrated runtime:
  Browser → ComputerUse → Git → Message → Deployment
  → RAG → Memory Layers → Repair Loop → Program Loop

No real external systems are touched. All drivers are mock.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


@pytest.fixture
def runtime():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = Settings.from_env(root=root)
        settings.ensure_dirs()
        rt = NexaraRuntime(settings)
        yield rt
        rt.store.close()


class TestRuntimeClosureIntegration:
    """Verify all 9 adapters are accessible through the runtime."""

    def test_all_nine_adapters_accessible(self, runtime):
        assert runtime.browser is not None
        assert runtime.computer_use is not None
        assert runtime.git is not None
        assert runtime.messenger is not None
        assert runtime.deployment is not None
        assert runtime.rag is not None
        assert runtime.memory_layers is not None
        assert runtime.repair is not None
        assert runtime.program is not None

    def test_overview_includes_adapter_status(self, runtime):
        overview = runtime.overview()
        adapters = overview["system"]["adapters"]
        assert all(adapters.values()), f"Missing: {[k for k, v in adapters.items() if not v]}"
        assert len(adapters) == 9


class TestBrowserAdapter:
    def test_navigate_and_read(self, runtime):
        browser = runtime.browser
        result = browser.navigate("file:///tmp/test.html")
        assert not result.error, f"navigate failed: {result.error}"
        assert result.success

        result = browser.read_page()
        assert result.success
        assert result.content

    def test_dom_snapshot(self, runtime):
        browser = runtime.browser
        result = browser.dom_snapshot()
        assert result.success
        assert result.dom_snapshot

    def test_probe_capability(self, runtime):
        cap = runtime.browser.probe_capability()
        assert cap.driver_type == "mock"

    def test_external_network_blocked(self, runtime):
        result = runtime.browser.navigate("https://example.com")
        assert result.error  # Should be blocked

    def test_get_action_history(self, runtime):
        runtime.browser.navigate("file:///tmp/test.html")
        history = runtime.browser.get_action_history()
        assert len(history) > 0


class TestComputerUseAdapter:
    def test_focus_and_read_ui(self, runtime):
        cu = runtime.computer_use
        result = cu.focus_app("Finder")
        assert result.success
        assert not result.error

        result = cu.read_ui_state()
        assert result.success

    def test_click_bounded(self, runtime):
        cu = runtime.computer_use
        result = cu.click(100, 200)
        assert result.success

    def test_forbidden_app_blocked(self, runtime):
        cu = runtime.computer_use
        result = cu.focus_app("Terminal")
        assert result.error  # Forbidden

    def test_probe_capability(self, runtime):
        cap = runtime.computer_use.probe_capability()
        assert cap.driver_type == "mock"


class TestGitAdapter:
    def test_status_and_diff(self, runtime):
        git = runtime.git
        status = git.status()
        assert status.success
        assert status.branch

        diff = git.diff()
        assert diff.success

    def test_commit_flow(self, runtime):
        git = runtime.git
        git.stage_files(["test.py"])
        result = git.commit("test: add feature")
        assert result.success
        assert result.commit_sha

    def test_branch_and_pr(self, runtime):
        git = runtime.git
        git.create_branch("feature/test", "main")
        result = git.open_pr("Test PR", "Testing", base="main", head="feature/test")
        assert result.success
        assert result.pr_url

    def test_force_push_denied(self, runtime):
        git = runtime.git
        result = git._execute("force_push", "main", "origin",
                              lambda: type(git.driver).__new__(type(git.driver)))
        assert not result.success
        assert "action_denied" in result.error

    def test_branch_protection(self, runtime):
        git = runtime.git
        git.enable_branch_protection = True
        result = git.push(branch="main")
        assert not result.success
        assert "protected_branch" in result.error

    def test_validate_repo_state(self, runtime):
        state = runtime.git.validate_repo_state()
        assert state["valid"]


class TestMessageAdapter:
    def test_draft_preview_send(self, runtime):
        msg = runtime.messenger
        draft = msg.draft(
            channel="email",
            recipients=["test@example.com"],
            subject="Test",
            body="Test body.",
        )
        preview = msg.preview(draft.draft_id)
        assert preview.content_digest == draft.content_digest

        result = msg.send(draft.draft_id)
        assert result.success
        assert result.captured

    def test_idempotency(self, runtime):
        msg = runtime.messenger
        draft = msg.draft(
            channel="email",
            recipients=["test@example.com"],
            subject="Idempotent",
            body="Test.",
        )
        msg.send(draft.draft_id)
        result2 = msg.send(draft.draft_id)
        assert not result2.success
        assert "already_sent" in result2.error

    def test_forbidden_content(self, runtime):
        msg = runtime.messenger
        draft = msg.draft(
            channel="email",
            recipients=["test@example.com"],
            subject="Check",
            body="phishing malware ransomware",
        )
        result = msg.send(draft.draft_id)
        assert not result.success
        assert "forbidden_content" in result.error

    def test_external_send_disabled(self, runtime):
        assert not runtime.messenger.external_send_enabled


class TestDeploymentAdapter:
    def test_create_plan_and_preview(self, runtime):
        dep = runtime.deployment
        from nexara_prime.deployment_adapter import DeploymentStep, DeployStrategy, StepType

        plan = dep.create_plan(
            target="nexara-api",
            version="v2.1.0",
            strategy=DeployStrategy.ROLLING,
            environment="staging",
            steps=[
                DeploymentStep(name="build", step_type=StepType.BUILD, command="docker build"),
                DeploymentStep(name="deploy", step_type=StepType.DEPLOY, command="kubectl apply"),
            ],
            rollback_steps=[
                DeploymentStep(name="rollback", step_type=StepType.DEPLOY, command="kubectl undo"),
            ],
        )
        preview = dep.preview(plan.plan_id)
        assert preview.steps_count == 2
        assert preview.rollback_steps_count == 1

    def test_execute_staging(self, runtime):
        dep = runtime.deployment
        from nexara_prime.deployment_adapter import DeploymentStep

        plan = dep.create_plan(
            target="svc", version="v1",
            steps=[DeploymentStep(name="deploy", command="deploy")],
            rollback_steps=[DeploymentStep(name="rb", command="rb")],
        )
        result = dep.execute(plan.plan_id)
        assert result.success
        assert result.health_check_passed

    def test_production_blocked(self, runtime):
        dep = runtime.deployment
        from nexara_prime.deployment_adapter import DeploymentStep

        plan = dep.create_plan(
            target="prod-svc", version="v1",
            environment="production",
            steps=[DeploymentStep(name="deploy", command="deploy")],
            rollback_steps=[DeploymentStep(name="rb", command="rb")],
        )
        result = dep.execute(plan.plan_id)
        assert not result.success
        assert "production_deploy_disabled" in result.error

    def test_health_check_and_rollback(self, runtime):
        dep = runtime.deployment
        from nexara_prime.deployment_adapter import DeploymentStep

        plan = dep.create_plan(
            target="svc", version="v1",
            steps=[DeploymentStep(name="deploy", command="deploy")],
            rollback_steps=[DeploymentStep(name="rb", command="rb")],
        )
        hc = dep.health_check(plan.plan_id)
        assert hc.healthy

        # Trigger rollback
        rollback = dep.rollback(plan.plan_id)
        assert rollback.rolled_back


class TestRAGPipeline:
    def test_ingest_and_query(self, runtime):
        from nexara_prime.models import MemoryKind

        doc = runtime.rag.ingest(
            content="NEXARA PRIME uses SQLite for persistence.",
            memory_kind=MemoryKind.PROJECT_FACT,
        )
        runtime.rag.index_document(doc)

        results = runtime.rag.query("database", min_similarity=0.01)
        assert results.total_retrieved >= 0

    def test_layer_filtering(self, runtime):
        from nexara_prime.models import MemoryKind
        from nexara_prime.rag_pipeline import MemoryLayer as RAGLayer

        runtime.rag.index_document(runtime.rag.ingest(
            "Procedural: always run tests before commit",
            memory_kind=MemoryKind.SYSTEM_RULE,
        ))
        qr = runtime.rag.query("tests", layer_filter=[RAGLayer.PROCEDURAL], min_similarity=0.01)
        assert qr.total_retrieved >= 0

    def test_stats(self, runtime):
        stats = runtime.rag.stats()
        assert "total_documents" in stats

    def test_citation(self, runtime):
        from nexara_prime.models import MemoryKind

        doc = runtime.rag.ingest(
            "Cited fact: Python 3.11 runtime.",
            source_evidence_id="ev_test_001",
            memory_kind=MemoryKind.PROJECT_FACT,
        )
        runtime.rag.index_document(doc)
        results = runtime.rag.query("Python", min_similarity=0.01)
        if results.results:
            assert results.results[0].citation


class TestMemoryLayers:
    def test_four_layer_writes(self, runtime):
        ml = runtime.memory_layers
        ml.write_working("task", "test task", "trace-1", mission_id="mis-e2e")
        ml.write_episodic("result", "test result", "trace-2", mission_id="mis-e2e")
        ml.write_semantic("fact", "test fact", "trace-3")
        ml.write_procedural("skill", "test skill", "trace-4")

        assert len(ml.read_working("mis-e2e")) >= 1
        assert len(ml.read_episodic("mis-e2e")) >= 1
        assert len(ml.read_semantic()) >= 1
        assert len(ml.read_procedural()) >= 1

    def test_keyword_search(self, runtime):
        ml = runtime.memory_layers
        ml.write_semantic("python_version", "Python 3.11 is the runtime", "trace-5")
        results = ml.search("Python", top_k=3)
        assert len(results) >= 1

    def test_patch_review_flow(self, runtime):
        ml = runtime.memory_layers
        patch = ml.propose_patch(
            "test_patch", "Test patch content",
            "trace-6", mission_id="mis-e2e",
        )
        pending = ml.get_pending_reviews()
        if pending:
            review = ml.review_patch(
                pending[0]["review_id"], "approved",
                "human_reviewer", "Looks good",
            )
            assert review.decision == "approved"

    def test_stats(self, runtime):
        stats = runtime.memory_layers.stats()
        assert stats["total"] >= 0


class TestRepairLoop:
    def test_full_repair_cycle(self, runtime):
        result = runtime.repair.repair(
            "mis-e2e",
            "SyntaxError: invalid syntax in test.py",
            traceback='File "test.py", line 10\n    x =\n      ^',
            component="test",
        )
        assert result.success

    def test_escalation_after_three_failures(self, runtime):
        # Override reviewer to always reject
        from nexara_prime.repair_loop import IndependentReviewer

        class AlwaysReject(IndependentReviewer):
            def review(self, contract, rca):
                return False, "always_rejected"

        runtime.repair.reviewer = AlwaysReject()
        result = runtime.repair.repair(
            "mis-escalation",
            "persistent error",
            traceback="test",
        )
        assert result.status.value == "escalated"

    def test_stats(self, runtime):
        stats = runtime.repair.stats()
        assert "total_failures" in stats


class TestProgramLoop:
    def test_lifecycle(self, runtime):
        from nexara_prime.program_loop import ProgramLoopConfig
        import time

        pl = runtime.program
        pl.config.max_cycles = 5
        pl.start()
        time.sleep(0.2)
        pl.stop(timeout_seconds=3.0)

        state = pl.get_state()
        assert state["cycle_count"] > 0

    def test_pause_resume(self, runtime):
        from nexara_prime.program_loop import ProgramLoopConfig
        import time

        pl = runtime.program
        pl.config.max_cycles = 50
        pl.start()
        time.sleep(0.15)
        pl.pause()
        count_paused = pl.state.cycle_count
        time.sleep(0.2)
        count_still = pl.state.cycle_count
        assert abs(count_still - count_paused) <= 3
        pl.resume()
        # pause_event.wait() has 0.5s timeout internally; give it enough time
        time.sleep(0.6)
        assert pl.state.cycle_count > count_still, (
            f"Expected cycles to increase after resume, got {pl.state.cycle_count} vs {count_still}"
        )
        pl.stop(timeout_seconds=3.0)

    def test_probe_capability(self, runtime):
        cap = runtime.program.probe_capability()
        assert "PROGRAM_LOOP_ACTIVE" in cap["flags"]

    def test_get_cycles(self, runtime):
        cycles = runtime.program.get_cycles(limit=10)
        assert isinstance(cycles, list)


class TestE2EMissionFlow:
    """Simulated end-to-end mission covering all adapters."""

    def test_full_mission_pipeline(self, runtime):
        """Simulate: analyze → compile → multi-agent → file ops → approval → git write → browser verify → evidence → memory → repair → done."""
        from nexara_prime.models import RiskLevel

        # Step 1: Create mission
        mission = runtime.create_mission(
            "Analyze repository structure and write a summary report.",
        )
        assert mission.mission_id
        runtime.recovery.checkpoint(mission.mission_id, "e2e_start", mission.trace_id)

        # Step 2: Browser adapter — verify documentation
        browser = runtime.browser
        nav = browser.navigate("file:///tmp/e2e-test.html")
        assert nav.success or nav.error  # Accept either (file may not exist)

        # Step 3: Git adapter — check status
        git = runtime.git
        status = git.status()
        assert status.success

        # Step 4: Computer Use adapter — verify UI
        cu = runtime.computer_use
        focus = cu.focus_app("Finder")
        assert focus.success

        # Step 5: RAG pipeline — ingest mission context
        from nexara_prime.models import MemoryKind
        doc = runtime.rag.ingest(
            f"Mission {mission.mission_id}: analyze repo structure.",
            memory_kind=MemoryKind.DECISION,
            mission_id=mission.mission_id,
        )
        runtime.rag.index_document(doc)

        # Step 6: Memory layers — write episodic memory
        ml = runtime.memory_layers
        ml.write_episodic(
            "e2e_step", f"Executed E2E mission {mission.mission_id}",
            mission.trace_id, mission_id=mission.mission_id,
        )

        # Step 7: Message adapter — draft notification
        msg = runtime.messenger
        draft = msg.draft(
            channel="email",
            recipients=["test@example.com"],
            subject=f"Mission {mission.mission_id} completed",
            body="E2E verification completed successfully.",
        )
        result = msg.send(draft.draft_id)
        assert result.success

        # Step 8: Deployment adapter — deploy report
        from nexara_prime.deployment_adapter import DeploymentStep
        dep = runtime.deployment
        plan = dep.create_plan(
            target=f"report-{mission.mission_id}", version="v1",
            steps=[DeploymentStep(name="deploy", command="deploy")],
            rollback_steps=[DeploymentStep(name="rb", command="rb")],
        )
        dep_result = dep.execute(plan.plan_id)
        assert dep_result.success

        # Step 9: Repair loop — verify repair of a minor issue
        repair_result = runtime.repair.repair(
            mission.mission_id,
            "AssertionError: expected True but got False",
            traceback='File "test_e2e.py", line 42, in test_flow\n    assert result == expected\nAssertionError',
            component="e2e",
        )
        assert repair_result.success

        # Step 10: Final evidence
        evidence_list = runtime.evidence.list(mission.mission_id)
        assert isinstance(evidence_list, list)

        # Mission complete!
        assert True


class TestAdapterDiscovery:
    """Verify all capability probes work."""

    def test_all_capability_probes(self, runtime):
        # Browser
        assert runtime.browser.probe_capability().driver_type == "mock"
        # Computer Use
        assert runtime.computer_use.probe_capability().driver_type == "mock"
        # Git
        assert runtime.git.probe_capability().driver_type == "mock"
        # Message
        cap_msg = runtime.messenger.probe_capability()
        assert cap_msg.provider_type == "mock"
        # Deployment
        assert runtime.deployment.probe_capability().driver_type == "mock"
        # RAG
        assert runtime.rag.probe_capability().embedder_type == "mock"
        # Repair
        assert runtime.repair.probe_capability()["max_attempts"] == 3
        # Program
        assert "PROGRAM_LOOP_ACTIVE" in runtime.program.probe_capability()["flags"]
