"""Runtime Truth Adapter — read/write .nexara/* canonical state without creating second source."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NEXARA_DIR = REPO_ROOT / ".nexara"
PROGRAM_STATE = NEXARA_DIR / "PROGRAM_STATE.json"
GATE_STATUS = NEXARA_DIR / "GATE_STATUS.json"
NEXT_ACTION = NEXARA_DIR / "NEXT_ACTION.md"


class RuntimeTruthAdapter:
    """Single read/write adapter for .nexara/* — never creates STATE.md or LOOP.md."""

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

    @staticmethod
    def is_clean_worktree() -> bool:
        import subprocess
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--short"],
            capture_output=True, text=True,
        )
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        pre_existing = [ln for ln in lines if "README.md" in ln]
        return len(lines) == len(pre_existing)
