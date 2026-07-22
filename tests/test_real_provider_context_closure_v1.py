"""Focused tests for the real provider/context closure."""

from __future__ import annotations

import subprocess
from pathlib import Path

from nexara_prime.config import Settings
from nexara_prime.independent_review import IndependentReview
from nexara_prime.real_context import RealRepositoryContext
from nexara_prime.runtime import NexaraRuntime


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "README.md").write_text("real repository\n", encoding="utf-8")
    (repo / ".env").write_text("API_KEY=must-not-be-collected\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@nexara.local")
    _git(repo, "config", "user.name", "NEXARA Test")
    _git(repo, "add", "README.md", ".env")
    _git(repo, "commit", "-qm", "initial")
    return repo


def test_real_context_hash_binds_git_and_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    collector = RealRepositoryContext()
    first = collector.collect(repo)
    assert first.branch
    assert len(first.head_sha) == 40
    assert first.context_hash
    assert all(item["path"] != ".env" for item in first.files)
    assert ".env" not in first.excerpts

    (repo / "README.md").write_text("changed repository\n", encoding="utf-8")
    second = collector.collect(repo)
    assert second.status_porcelain == "M README.md"
    assert second.context_hash != first.context_hash


def test_independent_reviewer_requires_bound_context(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    context = RealRepositoryContext().collect(repo)
    report = tmp_path / "report.md"
    report.write_text(
        f"Provider: deepseek\nRepository Branch: `{context.branch}`\n"
        f"Repository HEAD: `{context.head_sha}`\n"
        f"Context Hash: `{context.context_hash}`\n",
        encoding="utf-8",
    )
    verdict = IndependentReview.reviewer_verdict("mission-1", str(report), context)
    assert verdict["actor"] == "reviewer"
    assert verdict["passed"] is True

    report.write_text("Provider: deepseek\nContext Hash: `wrong`\n", encoding="utf-8")
    assert IndependentReview.reviewer_verdict("mission-1", str(report), context)["passed"] is False


def test_plan_persists_real_context_and_assignment_lifecycle(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo = _repo(workspace)
    settings = Settings(
        db_path=tmp_path / "runtime" / "nexara.db",
        workspace_root=workspace,
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    runtime = NexaraRuntime(settings)
    mission = runtime.create_mission("Read-only repository audit", source_dir=str(repo))
    planned = runtime.plan_mission(mission.mission_id)

    assert planned.result["context_hash"]
    assert planned.result["context_manifest"]["head_sha"]
    assert any(item["kind"] == "repository_context" for item in runtime.evidence.list(planned.mission_id))
    assert planned.agent_lifecycle
    assert {item["status"] for item in planned.agent_lifecycle} == {"assigned"}
    assert all("model.mock" in assignment.loaded_capabilities for assignment in planned.assignments)


def test_plan_does_not_collect_repository_context_outside_workspace(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "outside")
    workspace = tmp_path / "workspace"
    settings = Settings(
        db_path=tmp_path / "runtime" / "nexara.db",
        workspace_root=workspace,
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    runtime = NexaraRuntime(settings)
    mission = runtime.create_mission("Read-only repository audit", source_dir=str(repo))
    planned = runtime.plan_mission(mission.mission_id)

    assert "context_hash" not in planned.result
    assert not any(item["kind"] == "repository_context" for item in runtime.evidence.list(planned.mission_id))
