"""Read-only, real repository context for provider-bound missions.

The existing ``ToolRuntime`` intentionally restricts file reads to the mission
workspace.  Repository audits need a different, explicit boundary: an owner
approved Git repository.  This module is that boundary.  It never writes to
the repository, never invokes a shell, and produces a canonical hash that is
persisted with the mission and sent to the provider.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .git_adapter import RealReadOnlyGitDriver
from .model_gateway import redact_secrets


class ContextCollectionError(RuntimeError):
    """The approved repository could not be collected safely."""


_SENSITIVE_NAMES = {".env", ".env.local", ".env.production"}
_SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
_TEXT_SUFFIXES = {
    ".md", ".py", ".pyproject", ".toml", ".yaml", ".yml", ".json",
    ".txt", ".js", ".ts", ".tsx", ".css", ".sh", ".sql",
}
# P1-2: paths excluded from context hash.
# Only genuinely runtime-generated paths are excluded.
# Committed artifacts (reports, evidence, receipts, .nexara) ARE part of
# the immutable context — they are version-controlled source of truth.
# The hash represents task-available context integrity, not a workspace snapshot.
_CONTEXT_HASH_EXCLUDE_PARTS = {"workspace", "runtime", "cache", "__pycache__", ".git"}


def _run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContextCollectionError(f"git_probe_failed:{type(exc).__name__}") from exc
    if result.returncode != 0:
        raise ContextCollectionError(
            f"git_probe_failed:{' '.join(args)}:{result.stderr.strip()[:240]}"
        )
    return result.stdout


def _safe_for_provider(relative: str) -> bool:
    path = Path(relative)
    if any(part in {".git", "__pycache__", ".venv", "node_modules"} for part in path.parts):
        return False
    if path.name in _SENSITIVE_NAMES or path.suffix.lower() in _SENSITIVE_SUFFIXES:
        return False
    return True


def _is_immutable_source(relative: str) -> bool:
    """True if the path is immutable source code, not runtime output."""
    path = Path(relative)
    parts = set(path.parts)
    return not bool(parts & _CONTEXT_HASH_EXCLUDE_PARTS)


@dataclass(frozen=True)
class RepositoryContext:
    repository_root: str
    branch: str
    head_sha: str
    status_porcelain: str
    files: tuple[dict[str, Any], ...]
    excerpts: dict[str, str]
    context_hash: str

    def to_provider_context(self, mission_id: str) -> dict[str, Any]:
        """Return bounded, secret-filtered context for a real provider call.

        Per NSEC P1 review: only immutable identity fields are sent.
        Repository structure, file lists, and excerpts are stripped —
        they belong in the context hash, not the provider payload.
        """
        return {
            "mission_id": mission_id,
            "context_hash": self.context_hash,
        }

    def manifest(self) -> dict[str, Any]:
        """Return metadata suitable for durable evidence without file contents."""
        return {
            "repository_root": self.repository_root,
            "branch": self.branch,
            "head_sha": self.head_sha,
            "status_porcelain": self.status_porcelain,
            "dirty": bool(self.status_porcelain),
            "file_count": len(self.files),
            "context_hash": self.context_hash,
            "files": list(self.files),
        }


class RealRepositoryContext:
    """Collect deterministic Git and file facts from one approved root."""

    def __init__(self, *, max_files: int = 400, max_excerpt_files: int = 24, max_excerpt_bytes: int = 8_000):
        self.max_files = max_files
        self.max_excerpt_files = max_excerpt_files
        self.max_excerpt_bytes = max_excerpt_bytes

    def collect(self, repository_root: str | Path, *, approved_roots: set[str] | None = None) -> RepositoryContext:
        requested = Path(repository_root).expanduser().resolve()
        if not requested.exists() or not requested.is_dir():
            raise ContextCollectionError(f"repository_not_found:{requested}")
        top_level = Path(_run_git(requested, "rev-parse", "--show-toplevel").strip()).resolve()
        if top_level != requested:
            raise ContextCollectionError(f"repository_root_mismatch:{top_level}")
        # P1-1: Validate against approved workspace registry
        if approved_roots is not None:
            top_str = str(top_level)
            top_resolved = str(top_level.resolve())
            if top_str not in approved_roots and top_resolved not in approved_roots:
                raise ContextCollectionError(f"repository_not_approved:{top_level}")
        driver = RealReadOnlyGitDriver(str(requested))
        branch = driver.current_branch
        head_sha = driver.get_head_sha()
        status = driver.status().output.strip()
        relative_paths = driver.list_files()

        files: list[dict[str, Any]] = []
        excerpts: dict[str, str] = {}
        for relative in relative_paths[: self.max_files]:
            path = requested / relative
            if not _safe_for_provider(relative) or not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise ContextCollectionError(f"file_read_failed:{relative}") from exc
            digest = hashlib.sha256(data).hexdigest()
            files.append({"path": relative, "bytes": len(data), "sha256": digest})
            if len(excerpts) < self.max_excerpt_files and Path(relative).suffix.lower() in _TEXT_SUFFIXES:
                text = data[: self.max_excerpt_bytes].decode("utf-8", errors="replace")
                excerpts[relative] = str(redact_secrets(text))

        # P1-2: context hash computed only from immutable source inputs.
        # Exclude runtime outputs: reports, evidence, receipts, cache, .nexara, workspace, runtime.
        immutable_files = [f for f in files if _is_immutable_source(f["path"])]
        canonical = {
            "version": 1,
            "repository_root": str(requested),
            "branch": branch,
            "head_sha": head_sha,
            "files": immutable_files,
        }
        context_hash = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return RepositoryContext(
            repository_root=str(requested),
            branch=branch,
            head_sha=head_sha,
            status_porcelain=status,
            files=tuple(files),
            excerpts=excerpts,
            context_hash=context_hash,
        )
