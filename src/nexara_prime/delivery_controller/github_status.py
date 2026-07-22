"""GitHub Commit Status publisher for sovereign CI authority bridge.

Uses `gh api` for status publication. Never prints tokens.
Reads GITHUB_TOKEN from environment only (never from files).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


# ── Constants ──

SOVEREIGN_CONTEXT = "nexara/sovereign-delivery"
STATUS_STATES = {"pending", "success", "failure", "error"}


@dataclass
class StatusPublication:
    """Result of a status publication attempt."""

    context: str
    state: str
    target_sha: str
    target_url: str | None
    description: str
    published: bool
    error: str | None = None
    response: dict[str, Any] | None = None


class GitHubStatusPublisher:
    """Publishes commit statuses via GitHub API using gh CLI."""

    def __init__(self, repo: str = "Zsx154855/NEXARA-PRIME") -> None:
        self.repo = repo

    def publish(
        self,
        sha: str,
        state: str,
        description: str = "",
        target_url: str | None = None,
    ) -> StatusPublication:
        """Publish a commit status. Returns StatusPublication with result."""
        if state not in STATUS_STATES:
            return StatusPublication(
                context=SOVEREIGN_CONTEXT, state=state, target_sha=sha,
                target_url=target_url, description=description,
                published=False, error=f"invalid_state:{state}",
            )

        try:
            payload = {
                "state": state,
                "context": SOVEREIGN_CONTEXT,
                "description": description[:140],
            }
            if target_url:
                payload["target_url"] = target_url

            r = subprocess.run(
                [
                    "gh", "api",
                    f"/repos/{self.repo}/statuses/{sha}",
                    "--method", "POST",
                    "--input", "-",
                ],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True, text=True, timeout=30,
            )

            if r.returncode == 0:
                response_data = json.loads(r.stdout) if r.stdout.strip() else {}
                return StatusPublication(
                    context=SOVEREIGN_CONTEXT, state=state, target_sha=sha,
                    target_url=target_url, description=description,
                    published=True, response=response_data,
                )
            else:
                return StatusPublication(
                    context=SOVEREIGN_CONTEXT, state=state, target_sha=sha,
                    target_url=target_url, description=description,
                    published=False, error=f"gh_api_error:{r.returncode}:{r.stderr[:200]}",
                )
        except subprocess.TimeoutExpired:
            return StatusPublication(
                context=SOVEREIGN_CONTEXT, state=state, target_sha=sha,
                target_url=target_url, description=description,
                published=False, error="timeout",
            )
        except Exception as e:
            return StatusPublication(
                context=SOVEREIGN_CONTEXT, state=state, target_sha=sha,
                target_url=target_url, description=description,
                published=False, error=f"{type(e).__name__}:{e}",
            )

    def get_statuses(self, sha: str) -> list[dict[str, Any]]:
        """Read all commit statuses for a given SHA."""
        try:
            r = subprocess.run(
                ["gh", "api", f"/repos/{self.repo}/commits/{sha}/statuses"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                return json.loads(r.stdout) if r.stdout.strip() else []
            return []
        except Exception:
            return []

    def get_sovereign_status(self, sha: str) -> dict[str, Any] | None:
        """Get the current sovereign status for a SHA."""
        statuses = self.get_statuses(sha)
        for s in statuses:
            if s.get("context") == SOVEREIGN_CONTEXT:
                return s
        return None

    def verify_publication(self, sha: str, expected_state: str) -> bool:
        """Verify that a status publication matches expected state."""
        status = self.get_sovereign_status(sha)
        if not status:
            return False
        return status.get("state") == expected_state
