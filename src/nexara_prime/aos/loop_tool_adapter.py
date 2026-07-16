"""Loop Engineering Tool Adapter — wraps loop-* tools for TOOL_ONLY integration."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class LoopAuditResult:
    score: int
    level: str
    raw_json: dict[str, Any]
    derived: bool = True  # always DERIVED_NON_CANONICAL


class LoopToolAdapter:
    """Wraps Loop Engineering tools for read-only use.

    All outputs are marked DERIVED_NON_CANONICAL — .nexara/* remains
    the single authoritative truth source.
    """

    DERIVED_MARKER = "DERIVED_NON_CANONICAL"

    def __init__(self) -> None:
        self._available: dict[str, bool] = {}

    def is_available(self, tool: str) -> bool:
        if tool not in self._available:
            result = subprocess.run(["which", tool], capture_output=True, text=True)
            self._available[tool] = result.returncode == 0
        return self._available[tool]

    def run_audit(self, repo_path: str) -> LoopAuditResult | None:
        if not self.is_available("loop-audit"):
            return None
        result = subprocess.run(
            ["loop-audit", repo_path, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return LoopAuditResult(
            score=data.get("score", 0),
            level=data.get("level", "L0"),
            raw_json=data,
        )

    def run_cost(self, pattern: str = "daily-triage", level: str = "L1",
                 cadence: str = "1d") -> str:
        if not self.is_available("loop-cost"):
            return ""
        result = subprocess.run(
            ["loop-cost", "--pattern", pattern, "--level", level, "--cadence", cadence],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout

    def run_worktree(self, command: str, *args: str) -> subprocess.CompletedProcess:
        if not self.is_available("loop-worktree"):
            return subprocess.CompletedProcess(["loop-worktree"], 1, "", "loop-worktree not found")
        return subprocess.run(
            ["loop-worktree", command, *args],
            capture_output=True, text=True, timeout=60,
        )

    def run_context(self, action: str, *args: str) -> subprocess.CompletedProcess:
        if not self.is_available("loop-context"):
            return subprocess.CompletedProcess(["loop-context"], 1, "", "loop-context not found")
        return subprocess.run(
            ["loop-context", action, *args],
            capture_output=True, text=True, timeout=30,
        )

    def to_evidence(self) -> dict[str, Any]:
        return {
            "tools_available": self._available,
            "marker": self.DERIVED_MARKER,
            "canonical_source": ".nexara/*",
        }
