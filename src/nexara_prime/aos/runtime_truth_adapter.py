"""Runtime Truth Adapter — read/write .nexara/* canonical state without creating second source."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NEXARA_DIR = REPO_ROOT / ".nexara"
PROGRAM_STATE = NEXARA_DIR / "PROGRAM_STATE.json"
GATE_STATUS = NEXARA_DIR / "GATE_STATUS.json"
NEXT_ACTION = NEXARA_DIR / "NEXT_ACTION.md"
BASELINE_FILE = NEXARA_DIR / "DIRTY_BASELINE.json"


class RuntimeTruthAdapter:
    """Single read/write adapter for .nexara/* — never creates STATE.md or LOOP.md.

    Uses a baseline of pre-existing dirty entries to distinguish known
    pre-existing changes from new drift. Only entries registered at startup
    with exact path + SHA256 are exempted.
    """

    @staticmethod
    def read_program_state() -> dict[str, Any]:
        if PROGRAM_STATE.exists():
            return json.loads(PROGRAM_STATE.read_text("utf-8"))
        return {}

    @staticmethod
    def read_gate_status() -> dict[str, Any]:
        if GATE_STATUS.exists():
            return json.loads(GATE_STATUS.read_text("utf-8"))
        return {}

    @staticmethod
    def read_next_action() -> str:
        if NEXT_ACTION.exists():
            return NEXT_ACTION.read_text("utf-8")
        return ""

    @staticmethod
    def write_program_state(data: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["updated_at"] = now
        tmp = PROGRAM_STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
        tmp.replace(PROGRAM_STATE)

    @staticmethod
    def write_next_action(content: str) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        full = f"<!-- updated: {now} -->\n\n{content}\n"
        tmp = NEXT_ACTION.with_suffix(".tmp")
        tmp.write_text(full, "utf-8")
        tmp.replace(NEXT_ACTION)

    @staticmethod
    def current_branch() -> str:
        return os.environ.get("NEXARA_BRANCH", "main")

    # ── baseline management ──

    @classmethod
    def load_baseline(cls) -> dict[str, str]:
        """Load the pre-existing dirty-entry baseline.

        Returns a mapping of file_path → sha256 that were dirty at
        startup and explicitly registered as known-safe.
        """
        if BASELINE_FILE.exists():
            try:
                return json.loads(BASELINE_FILE.read_text("utf-8"))
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}

    @classmethod
    def save_baseline(cls, baseline: dict[str, str]) -> None:
        """Persist a baseline of currently-dirty entries."""
        BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = BASELINE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", "utf-8")
        tmp.replace(BASELINE_FILE)

    @classmethod
    def snapshot_current_dirty(cls) -> dict[str, str]:
        """Take a snapshot of all currently dirty files with their SHA256 hashes.

        Use this at startup to establish the baseline of known pre-existing dirt.
        """
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--short"],
            capture_output=True, text=True,
        )
        dirty: dict[str, str] = {}
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # git status --short: first two chars are status flags, rest is path
            path = stripped[3:] if len(stripped) > 3 else stripped
            file_path = REPO_ROOT / path
            if file_path.is_file():
                try:
                    file_hash = hashlib.sha256(
                        file_path.read_bytes()
                    ).hexdigest()
                    dirty[path] = file_hash
                except (OSError, PermissionError):
                    dirty[path] = "unreadable"
            else:
                dirty[path] = "non_file"
        return dirty

    # ── worktree status ──

    @classmethod
    def is_clean_worktree(cls) -> bool:
        """Check if worktree is clean, accounting for registered baseline entries.

        Only entries that match both the exact path AND the exact SHA256
        from the baseline are exempted. New or modified README changes
        after startup are correctly flagged as drift.
        """
        baseline = cls.load_baseline()
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--short"],
            capture_output=True, text=True,
        )
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]

        unknown_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            path = stripped[3:] if len(stripped) > 3 else stripped

            # Check if this exact path + content hash is in the baseline
            if path in baseline:
                file_path = REPO_ROOT / path
                current_hash = ""
                if file_path.is_file():
                    try:
                        current_hash = hashlib.sha256(
                            file_path.read_bytes()
                        ).hexdigest()
                    except (OSError, PermissionError):
                        pass
                if current_hash and current_hash == baseline[path]:
                    continue  # Exact match — exempted

            unknown_lines.append(line)

        return len(unknown_lines) == 0
