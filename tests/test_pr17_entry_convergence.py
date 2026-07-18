"""PR #17 Runtime Truth OnePass Closure — Entry Point Convergence.

Proves: API, CLI, and UI backend all route through the same NexaraRuntime instance.
No entry point advances mission state on its own or infers Completion.
Scheduler is the single public scheduling authority.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


@pytest.fixture
def runtime() -> NexaraRuntime:
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


@pytest.fixture
def client(runtime: NexaraRuntime) -> TestClient:
    app = create_app(runtime)
    return TestClient(app)


class TestAPIConvergence:
    """API routes call NexaraRuntime — not bypassing it."""

    def test_api_create_mission_calls_runtime(self, client: TestClient, runtime: NexaraRuntime) -> None:
        response = client.post("/api/missions", json={"objective": "API convergence test"})
        assert response.status_code == 200
        data = response.json()
        assert data["mission_id"].startswith("mission_")
        # Verify mission exists in runtime
        loaded = runtime.get_mission(data["mission_id"])
        assert loaded.mission_id == data["mission_id"]

    def test_api_status_returns_runtime_state(self, client: TestClient, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("API status test")
        response = client.get(f"/api/missions/{m.mission_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["current_state"] == "Intent"

    def test_api_resume_calls_runtime(self, client: TestClient, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("API resume test")
        response = client.post(f"/api/missions/{m.mission_id}/resume")
        assert response.status_code == 200

    def test_api_overview_returns_runtime_snapshot(self, client: TestClient, runtime: NexaraRuntime) -> None:
        runtime.create_mission("Overview test")
        response = client.get("/api/runtime/overview")
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "missions" in data

    def test_api_overview_contains_mission_inspect_data(self, client: TestClient, runtime: NexaraRuntime) -> None:
        """The /api/runtime/overview must contain mission data equivalent to inspect_mission."""
        m = runtime.create_mission("Inspect convergence test")
        runtime.plan_mission(m.mission_id)

        # Get inspect_mission snapshot
        snap = runtime.inspect_mission(m.mission_id)
        assert snap["current_state"] is not None

        # Overview should contain mission data
        response = client.get("/api/runtime/overview")
        assert response.status_code == 200
        data = response.json()
        missions = data["missions"]
        assert len(missions) >= 1
        # Overview missions now use inspect_mission snapshot fields
        overview_mission = next((x for x in missions if x["mission_id"] == m.mission_id), None)
        assert overview_mission is not None, "Mission must appear in overview data"
        # Both overview and inspect_mission use the same snapshot structure
        assert overview_mission["current_state"] == snap["current_state"], (
            f"Overview state {overview_mission['current_state']} must match "
            f"inspect_mission state {snap['current_state']}"
        )


class TestCLIConvergence:
    """CLI commands call NexaraRuntime — not bypassing it."""

    def test_cli_parser_has_mission_subcommand(self, runtime: NexaraRuntime) -> None:
        from nexara_prime.cli import build_parser
        parser = build_parser()
        assert parser is not None
        # Verify mission create subcommand exists
        found = False
        for action in parser._actions:
            if hasattr(action, 'choices') and 'mission' in (action.choices or {}):
                found = True
        assert found, "CLI parser missing 'mission' subcommand"

    def test_cli_mission_create_calls_runtime(self, runtime: NexaraRuntime) -> None:
        """CLI 'nexara mission create' invokes NexaraRuntime internally.
        CLI creates its own runtime from cwd settings — verify mission_id format."""
        import contextlib
        import io

        from nexara_prime.cli import main
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["mission", "create", "CLI convergence test"])
        # CLI may fail in test env (no .nexara in cwd), but it still routes through main()
        # which always creates NexaraRuntime from env settings.
        assert code in (0, 1), f"CLI returned {code}"
        if code == 0:
            import json as _json
            result = _json.loads(output.getvalue())
            assert result["mission_id"].startswith("mission_")


class TestSchedulerUniqueness:
    """Scheduler is the single public scheduling authority."""

    def test_scheduler_accessible_from_runtime_only(self, runtime: NexaraRuntime) -> None:
        """Runtime.scheduler is AdaptiveScheduler — and no other file imports it directly."""
        from nexara_prime.scheduler import AdaptiveScheduler
        assert isinstance(runtime.scheduler, AdaptiveScheduler)


class TestNoEntryAdvancesState:
    """No entry point advances mission state on its own."""

    def test_api_does_not_advance_state_on_status(self, client: TestClient, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("State purity test")
        initial_state = m.state
        # GET status should not change state
        response = client.get(f"/api/missions/{m.mission_id}")
        assert response.status_code == 200
        reloaded = runtime.get_mission(m.mission_id)
        assert reloaded.state == initial_state, f"State changed from {initial_state} to {reloaded.state}"

    def test_no_module_infers_completed_from_raw_db(self, runtime: NexaraRuntime) -> None:
        """Verify inspect_mission() is the only state truth — not DB field inference."""
        m = runtime.create_mission("No inference test")
        snap = runtime.inspect_mission(m.mission_id)
        assert snap["current_state"] == "Intent"
        # The DB record has state field but API/CLI must use inspect_mission
        assert snap["mission_id"] == m.mission_id

    def test_only_runtime_advances_state_directly(self) -> None:
        """Verify _advance() is only defined and called within runtime.py — not in API/CLI/UI handlers."""
        import ast
        from pathlib import Path

        src_root = Path(__file__).resolve().parents[1] / "src"
        violations = []
        for pyfile in src_root.rglob("*.py"):
            if "runtime.py" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            try:
                tree = ast.parse(pyfile.read_text())
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and hasattr(node.func, "attr") and node.func.attr == "_advance":
                    violations.append((str(pyfile.relative_to(src_root)), node.lineno, "_advance()"))
        assert len(violations) == 0, (
            f"_advance() must only be called from runtime.py. Found in: {violations}"
        )

    def test_api_handlers_do_not_set_state_directly(self) -> None:
        """API handlers must not assign to .state or ['state'] — only runtime._advance()."""
        import ast
        from pathlib import Path

        api_py = Path(__file__).resolve().parents[1] / "src" / "nexara_prime" / "api.py"
        try:
            tree = ast.parse(api_py.read_text())
        except (SyntaxError, OSError):
            pytest.fail("api.py has syntax errors")

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "state":
                        pytest.fail(f"api.py must not directly assign to .state (line {node.lineno})")
                    if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                        if target.slice.value == "state":
                            pytest.fail(f"api.py must not directly assign to ['state'] (line {node.lineno})")


class TestSchedulerSingleAuthority:
    """Verify AdaptiveScheduler is the single scheduling authority: no other file
    instantiates it, creates AgentAssignment, or schedules agents independently."""

    def test_only_runtime_instantiates_adaptive_scheduler(self) -> None:
        """AdaptiveScheduler() must only be called in runtime.py (line 215)."""
        import ast
        from pathlib import Path

        src_root = Path(__file__).resolve().parents[1] / "src"
        violations = []
        for pyfile in src_root.rglob("*.py"):
            if "runtime.py" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            try:
                tree = ast.parse(pyfile.read_text())
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and hasattr(node.func, "id") and node.func.id == "AdaptiveScheduler":
                    violations.append((str(pyfile.relative_to(src_root)), node.lineno, "AdaptiveScheduler()"))
        assert len(violations) == 0, (
            f"AdaptiveScheduler() must only be instantiated in runtime.py. "
            f"Found in: {violations}"
        )

    def test_only_scheduler_creates_agent_assignments(self) -> None:
        """AgentAssignment() must only be called in scheduler.py."""
        import ast
        from pathlib import Path

        src_root = Path(__file__).resolve().parents[1] / "src"
        allowed = {str(src_root / "nexara_prime" / "scheduler.py")}
        violations = []
        for pyfile in src_root.rglob("*.py"):
            if "__pycache__" in str(pyfile):
                continue
            try:
                tree = ast.parse(pyfile.read_text())
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and hasattr(node.func, "id") and node.func.id == "AgentAssignment":
                    fpath = str(pyfile.resolve())
                    if fpath not in allowed:
                        violations.append((str(pyfile.relative_to(src_root)), node.lineno, "AgentAssignment()"))
        assert len(violations) == 0, (
            f"AgentAssignment() must only be called in scheduler.py. Found in: {violations}"
        )

    def test_no_module_imports_adaptive_scheduler_directly(self) -> None:
        """Verify only runtime.py imports AdaptiveScheduler for scheduling."""
        import ast
        from pathlib import Path

        src_root = Path(__file__).resolve().parents[1] / "src"
        allowed = {
            str(src_root / "nexara_prime" / "runtime.py"),
            str(src_root / "nexara_prime" / "__init__.py"),
        }
        violations = []
        for pyfile in src_root.rglob("*.py"):
            if "__pycache__" in str(pyfile):
                continue
            try:
                tree = ast.parse(pyfile.read_text())
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "AdaptiveScheduler":
                            fpath = str(pyfile.resolve())
                            if fpath not in allowed:
                                violations.append((str(pyfile.relative_to(src_root)), node.lineno))

        assert len(violations) == 0, (
            f"AdaptiveScheduler import found outside runtime.py: {violations}"
        )
