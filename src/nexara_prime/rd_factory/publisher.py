"""Draft PR delivery. Never merges, never targets a protected branch."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class PublishError(RuntimeError):
    """Draft PR delivery failed."""


@dataclass(frozen=True)
class DraftPR:
    url: str
    number: int | None
    branch: str


class GhPublisher:
    def __init__(self, repo: str | Path, base_branch: str = "main"):
        self.repo = Path(repo)
        self.base_branch = base_branch

    def open_draft_pr(self, *, branch: str, title: str, body: str) -> DraftPR:
        proc = subprocess.run(
            ["gh", "pr", "create", "--draft", "--base", self.base_branch,
             "--head", branch, "--title", title, "--body", body],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            raise PublishError(f"gh pr create failed: {proc.stderr.strip()[:400]}")
        url = proc.stdout.strip().splitlines()[-1].strip()
        number = None
        tail = url.rsplit("/", 1)[-1]
        if tail.isdigit():
            number = int(tail)
        return DraftPR(url=url, number=number, branch=branch)
