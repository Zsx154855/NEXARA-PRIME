"""T1 acceptance: the execution stage produces checkable facts, not a template."""
from __future__ import annotations

import re
from pathlib import Path

from nexara_prime.api import create_app  # noqa: F401  (ensures runtime wiring imports)
from nexara_prime.config import Settings
from nexara_prime.provenance_engine import analyze, verify_citations
from nexara_prime.runtime import NexaraRuntime


def _sample_tree(root: Path) -> None:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "alpha.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (root / "pkg" / "beta.py").write_text("def beta():\n    return 2\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_alpha.py").write_text(
        "def test_alpha():\n    assert True\n\ndef test_beta():\n    assert True\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# sample\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\ndependencies = [\n  "fastapi>=0.110",\n  "pydantic>=2",\n]\n',
        encoding="utf-8",
    )
    (root / "pkg" / "todo.py").write_text("# TODO: later\nx = 1\n", encoding="utf-8")


def test_analysis_cites_existing_lines(tmp_path: Path):
    _sample_tree(tmp_path)
    analysis = analyze(tmp_path)
    assert analysis.files >= 4
    assert len(analysis.assertions) >= 3
    assert any("test function" in a.claim for a in analysis.assertions)
    assert any("TODO/FIXME" in a.claim for a in analysis.assertions)
    assert any("runtime dependency" in a.claim for a in analysis.assertions)
    assert verify_citations(analysis)["ok"] is True


def test_mission_report_contains_resolvable_citations(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    _sample_tree(source)

    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8891,
    )
    settings.ensure_dirs()
    runtime = NexaraRuntime(settings)

    mission = runtime.create_mission("summarise this sample tree", str(source))
    runtime.plan_mission(mission.mission_id)
    runtime.approve_mission(mission.mission_id, actor="human")
    final = runtime.run_mission(mission.mission_id)

    assert final.state.value in {"Completed", "Blocked"}, final.state
    report_path = Path(final.result["report_path"])
    text = report_path.read_text(encoding="utf-8")

    # every `path:line` citation in the report must point at a real line
    citations = re.findall(r"`([^`]+):(\d+)`", text)
    assert citations, "report must cite at least one file:line"
    for rel, line in citations:
        target = source / rel
        assert target.exists(), f"missing citation target {rel}"
        assert 1 <= int(line) <= len(target.read_text(encoding="utf-8").splitlines())

    assert final.result.get("analysis_assertions"), "assertions must be persisted"
