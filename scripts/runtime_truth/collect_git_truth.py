"""Collect Git truth — full SHAs, branch, HEAD. Never hand-write SHAs."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def collect_git_truth() -> dict:
    """Return canonical Git truth.

    Returns:
        {branch, local_head_sha, remote_head_sha,
         origin_main_sha, is_ancestor_check: {sha, is_ancestor},
         dirty_files, stash_count}
    """
    branch = _git("branch", "--show-current")
    local_head = _git("rev-parse", "HEAD")
    remote_head = ""
    origin_main = ""
    try:
        remote_head = _git("rev-parse", f"origin/{branch}")
        origin_main = _git("rev-parse", "origin/main")
    except RuntimeError:
        pass

    dirty = []
    status = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--short"],
        capture_output=True, text=True, timeout=10,
    )
    if status.returncode == 0:
        dirty = [l for l in status.stdout.splitlines() if l.strip()]

    stash_count = 0
    stash = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "stash", "list"],
        capture_output=True, text=True, timeout=10,
    )
    if stash.returncode == 0:
        stash_count = len([l for l in stash.stdout.splitlines() if l.strip()])

    return {
        "branch": branch,
        "local_head_sha": local_head,
        "remote_head_sha": remote_head if remote_head else None,
        "origin_main_sha": origin_main if origin_main else None,
        "dirty_files": [f.split()[-1] for f in dirty],
        "dirty_count": len(dirty),
        "stash_count": stash_count,
        "readme_status": "PRE_EXISTING_USER_CHANGE" if any("README.md" in f for f in dirty) else "CLEAN",
    }


def verify_sha_full(sha: str) -> bool:
    """Return True if sha is a full 40-character hex string."""
    return len(sha) == 40 and all(c in "0123456789abcdef" for c in sha.lower())


if __name__ == "__main__":
    truth = collect_git_truth()
    json.dump(truth, sys.stdout, indent=2)
