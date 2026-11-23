"""T9: the report must carry structure and entry points, not just counts."""
from __future__ import annotations

from pathlib import Path

from nexara_prime.provenance_engine import analyze, verify_citations


def _tree(root: Path) -> None:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "cli.py").write_text(
        'def main():\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_cli.py").write_text("def test_main():\n    assert True\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["fastapi>=0.110"]\n\n'
        '[project.scripts]\nx = "pkg.cli:main"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# x\n", encoding="utf-8")


def test_reports_layout_and_entry_points(tmp_path: Path):
    _tree(tmp_path)
    result = analyze(tmp_path)
    claims = " | ".join(a.claim for a in result.assertions)
    assert "entry point" in claims, claims
    assert "top-level" in claims, claims
    assert all(verify_citations(result)["ok"] for _ in [0])


def test_entry_point_citation_points_at_the_guard(tmp_path: Path):
    _tree(tmp_path)
    result = analyze(tmp_path)
    entry = next(a for a in result.assertions if "entry point" in a.claim)
    lines = (tmp_path / entry.path).read_text(encoding="utf-8").splitlines()
    assert 1 <= entry.line <= len(lines)
    assert "__main__" in lines[entry.line - 1]
