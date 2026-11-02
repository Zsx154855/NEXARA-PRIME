"""Deterministic, provenance-carrying analysis of a source directory.

The MVP execution stage used to write a template where the "findings" were the
task text echoed back. This module replaces that with facts that can be checked:
every assertion cites a file and a 1-based line that exists.

Deliberately not an LLM call: the point is to make the report falsifiable first.
A provider can be layered on top later without changing the shape.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".sh", ".ts", ".tsx", ".js", ".jsx", ".sql", ".html", ".css", ".rs", ".go",
}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".mypy_cache", ".pytest_cache", ".ruff_cache", "runtime",
    "reports", "evidence", "coverage", ".idea", ".vscode",
}
MAX_FILE_BYTES = 2_000_000


@dataclass(frozen=True)
class Assertion:
    claim: str
    path: str
    line: int
    excerpt: str


@dataclass
class Analysis:
    root: str
    files: int = 0
    bytes: int = 0
    assertions: list[Assertion] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "root": self.root,
            "files": self.files,
            "bytes": self.bytes,
            "assertions": [
                {"claim": a.claim, "path": a.path, "line": a.line, "excerpt": a.excerpt}
                for a in self.assertions
            ],
        }


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _walk(root: Path, max_files: int) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            found.append(path)
            if len(found) >= max_files:
                return found
    return found


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _first_line(path: Path) -> tuple[int, str]:
    for index, text in enumerate(_read_lines(path), start=1):
        if text.strip():
            return index, text.strip()
    return 1, ""


def _find_markers(paths: list[Path], markers: tuple[str, ...] = ("TODO", "FIXME")) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in paths:
        for index, text in enumerate(_read_lines(path), start=1):
            if any(marker in text for marker in markers):
                hits.append((path, index, text.strip()))
    return hits


def _project_dependencies(root: Path) -> tuple[int, tuple[str, int, str] | None]:
    """Count declared runtime deps and cite the first one, without a TOML parser."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return 0, None
    lines = _read_lines(pyproject)
    in_deps = False
    count = 0
    first: tuple[str, int, str] | None = None
    for index, text in enumerate(lines, start=1):
        stripped = text.strip()
        if stripped.startswith("dependencies") and "[" in stripped:
            in_deps = True
            continue
        if in_deps and stripped.startswith("]"):
            break
        if in_deps and stripped.startswith('"'):
            count += 1
            if first is None:
                first = ("pyproject.toml", index, stripped)
    return count, first


def _find_test_functions(paths: list[Path]) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in paths:
        if path.suffix != ".py":
            continue
        for index, text in enumerate(_read_lines(path), start=1):
            if text.lstrip().startswith("def test_"):
                hits.append((path, index, text.strip()))
    return hits


def analyze(root: Path, *, max_files: int = 5000) -> Analysis:
    """Collect three falsifiable facts about the tree, or none if it is empty."""
    root = Path(root)
    analysis = Analysis(root=str(root))
    if not root.exists() or not root.is_dir():
        return analysis

    files = _walk(root, max_files)
    if not files:
        return analysis

    analysis.files = len(files)
    analysis.bytes = sum(p.stat().st_size for p in files if p.exists())

    python_files = [p for p in files if p.suffix == ".py"]
    tests = _find_test_functions(files)
    largest = max(files, key=lambda p: (p.stat().st_size, str(p)))

    if python_files:
        first = python_files[0]
        line, excerpt = _first_line(first)
        analysis.assertions.append(Assertion(
            claim=f"{len(python_files)} Python module(s); first is {_rel(first, root)}",
            path=_rel(first, root), line=line, excerpt=excerpt,
        ))
    else:
        first = files[0]
        line, excerpt = _first_line(first)
        analysis.assertions.append(Assertion(
            claim=f"no Python modules; {len(files)} text file(s), first is {_rel(first, root)}",
            path=_rel(first, root), line=line, excerpt=excerpt,
        ))

    line, excerpt = _first_line(largest)
    analysis.assertions.append(Assertion(
        claim=(f"largest text file is {_rel(largest, root)} "
               f"({largest.stat().st_size} bytes, {len(_read_lines(largest))} lines)"),
        path=_rel(largest, root), line=line, excerpt=excerpt,
    ))

    markers = _find_markers(files)
    if markers:
        path, line, excerpt = markers[0]
        analysis.assertions.append(Assertion(
            claim=(f"{len(markers)} TODO/FIXME marker(s); first is "
                   f"{_rel(path, root)}:{line}"),
            path=_rel(path, root), line=line, excerpt=excerpt,
        ))

    dep_count, dep_first = _project_dependencies(root)
    if dep_count:
        path, line, excerpt = dep_first
        analysis.assertions.append(Assertion(
            claim=f"pyproject.toml declares {dep_count} runtime dependency(ies); first is {excerpt[:60]}",
            path=path, line=line, excerpt=excerpt,
        ))

    if tests:
        path, line, excerpt = tests[0]
        analysis.assertions.append(Assertion(
            claim=(f"{len(tests)} test function(s) across "
                   f"{len({p for p, _, _ in tests})} file(s); first is {_rel(path, root)}:{line}"),
            path=_rel(path, root), line=line, excerpt=excerpt,
        ))
    else:
        path = python_files[0] if python_files else files[0]
        line, excerpt = _first_line(path)
        analysis.assertions.append(Assertion(
            claim="no test functions found in the analysed tree",
            path=_rel(path, root), line=line, excerpt=excerpt,
        ))

    return analysis


def verify_citations(analysis: Analysis, limit: int = 50) -> dict:
    """Re-open every cited file/line. Returns a small, checkable verdict."""
    root = Path(analysis.root)
    checked, bad = 0, []
    for assertion in analysis.assertions[:limit]:
        target = root / assertion.path
        lines = _read_lines(target) if target.exists() else []
        checked += 1
        if not target.exists() or assertion.line < 1 or assertion.line > len(lines):
            bad.append({"path": assertion.path, "line": assertion.line})
    return {"checked": checked, "bad": bad, "ok": checked > 0 and not bad}
