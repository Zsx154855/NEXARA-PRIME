"""Preflight checks: environment and repository readiness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


class PreflightRunner:
    """Runs environment and repository preflight checks before gate execution."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = Path(repo_root).resolve()

    def check_environment(self) -> tuple[bool, list[str]]:
        """Verify Python, venv, and essential packages."""
        errors: list[str] = []

        # Python version
        if sys.version_info < (3, 9):
            errors.append(f"python_version<3.9: {sys.version}")

        # pydantic
        try:
            import pydantic  # noqa: F401
        except ImportError:
            errors.append("pydantic_not_importable")

        # pytest
        try:
            import pytest  # noqa: F401
        except ImportError:
            errors.append("pytest_not_importable")

        return len(errors) == 0, errors

    def check_repository(self) -> tuple[bool, list[str]]:
        """Verify git repo, clean worktree, and PROJECT_STATE.json."""
        errors: list[str] = []

        # Is git repo
        if not (self.repo_root / ".git").exists():
            errors.append("not_a_git_repo")
            return False, errors

        # Clean worktree
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=str(self.repo_root), timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                dirty_count = len(r.stdout.strip().split("\n"))
                errors.append(f"dirty_worktree:{dirty_count}_files")
        except Exception as e:
            errors.append(f"git_status_failed:{e}")

        # PROJECT_STATE.json
        state_path = self.repo_root / ".nexara" / "PROJECT_STATE.json"
        if not state_path.exists():
            errors.append("missing_project_state_json")
        else:
            try:
                json.loads(state_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                errors.append(f"invalid_project_state_json:{e}")

        return len(errors) == 0, errors
