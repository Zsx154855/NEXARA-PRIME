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


def _walk(root: Path, max_files: int) -> list[tuple[Path, int]]:
    found: list[tuple[Path, int]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                continue
            found.append((path, size))
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


def _first_contentful(paths: list[Path]) -> Path | None:
    """A file worth citing: an empty __init__.py makes a useless reference."""
    for path in paths:
        if any(line.strip() for line in _read_lines(path)):
            return path
    return paths[0] if paths else None


def _find_test_functions(paths: list[Path]) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in paths:
        if path.suffix != ".py":
            continue
        for index, text in enumerate(_read_lines(path), start=1):
            if text.lstrip().startswith("def test_"):
                hits.append((path, index, text.strip()))
    return hits



def _top_level_layout(root: Path, files: list[Path]) -> tuple[str, Path, int, str] | None:
    """Largest top-level group, with a citation inside it."""
    groups: dict[str, list[Path]] = {}
    for path in files:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        head = relative.parts[0] if len(relative.parts) > 1 else "(root)"
        groups.setdefault(head, []).append(path)
    if not groups:
        return None
    head, members = max(groups.items(), key=lambda item: (len(item[1]), item[0]))
    ordered = sorted(members)
    first = _first_contentful(ordered) or ordered[0]
    line, excerpt = _first_line(first)
    claim = (f"top-level layout: {len(groups)} group(s); largest is `{head}` "
             f"with {len(members)} text file(s)")
    return claim, first, line, excerpt


def _entry_point(files: list[Path]) -> tuple[str, Path, int, str] | None:
    """First `if __name__ == ...` guard or a [project.scripts] declaration."""
    for path in sorted(files):
        if path.suffix != ".py":
            continue
        for index, text in enumerate(_read_lines(path), start=1):
            if "__name__" in text and "__main__" in text:
                return ("""entry point: `if __name__ == "__main__"` guard""", path, index, text.strip())
    for path in sorted(files):
        if path.name != "pyproject.toml":
            continue
        lines = _read_lines(path)
        for index, text in enumerate(lines, start=1):
            if text.strip().startswith("[project.scripts]"):
                for offset in range(index, min(index + 3, len(lines) + 1)):
                    candidate = lines[offset - 1].strip()
                    if "=" in candidate:
                        return ("entry point: console script declared in pyproject.toml",
                                path, offset, candidate)
    return None


def analyze(root: Path, *, max_files: int = 5000) -> Analysis:
    """Collect three falsifiable facts about the tree, or none if it is empty."""
    root = Path(root)
    analysis = Analysis(root=str(root))
    if not root.exists() or not root.is_dir():
        return analysis

    entries = _walk(root, max_files)
    if not entries:
        return analysis

    files = [path for path, _size in entries]
    sizes = {path: size for path, size in entries}
    analysis.files = len(files)
    analysis.bytes = sum(sizes.values())

    python_files = [p for p in files if p.suffix == ".py"]
    tests = _find_test_functions(files)
    largest = max(files, key=lambda p: (sizes.get(p, 0), str(p)))

    if python_files:
        first = _first_contentful(python_files) or python_files[0]
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
               f"({sizes.get(largest, 0)} bytes, {len(_read_lines(largest))} lines)"),
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
        path = (_first_contentful(python_files) if python_files else None) or files[0]
        line, excerpt = _first_line(path)
        analysis.assertions.append(Assertion(
            claim="no test functions found in the analysed tree",
            path=_rel(path, root), line=line, excerpt=excerpt,
        ))

    layout = _top_level_layout(root, files)
    if layout:
        claim, path, line, excerpt = layout
        analysis.assertions.append(Assertion(
            claim=claim, path=_rel(path, root), line=line, excerpt=excerpt))

    entry = _entry_point(files)
    if entry:
        claim, path, line, excerpt = entry
        analysis.assertions.append(Assertion(
            claim=claim, path=_rel(path, root), line=line, excerpt=excerpt))
    else:
        path = files[0]
        line, excerpt = _first_line(path)
        analysis.assertions.append(Assertion(
            claim="entry point: none declared (no __main__ guard, no console script)",
            path=_rel(path, root), line=line, excerpt=excerpt))

    return analysis


def verify_citations(analysis: Analysis, limit: int = 50) -> dict:
    """Re-open every cited file/line. Returns a small, checkable verdict."""
    root = Path(analysis.root)
    checked, bad = 0, []
    for assertion in analysis.assertions[:limit]:
        target = root / assertion.path
        lines = _read_lines(target) if target.exists() else []
        checked += 1
        empty = not lines
        if not target.exists() or assertion.line < 1 or assertion.line > len(lines):
            # An empty file can still be cited at line 1 (nothing to quote).
            if not (empty and assertion.line == 1 and target.exists()):
                bad.append({"path": assertion.path, "line": assertion.line})
        elif assertion.excerpt and lines[assertion.line - 1].strip() != assertion.excerpt:
            bad.append({"path": assertion.path, "line": assertion.line,
                        "reason": "excerpt_mismatch"})
    return {"checked": checked, "bad": bad, "ok": checked > 0 and not bad}
