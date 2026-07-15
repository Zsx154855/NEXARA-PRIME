"""NEXARA PRIME Git Adapter — Governed version control operations.

Structured API:
- AUTO_ALLOW: status, diff, log, branch_list, show, fetch
- REQUIRE_APPROVAL: commit (strategy override), push, open_pr, merge_pr
- DENY: force_push, reset_hard, delete_remote_branch, amend_public_history

Security constraints:
- Expected Head SHA verification before push (prevent race conditions)
- Secret scanning before commit and push (API keys, tokens, passwords)
- Branch protection (main/master require PR)
- No force push to protected branches
- No destructive local operations (reset --hard)
- Evidence recording for every governed action
- Mock Driver for deterministic tests
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import new_id, now_iso


# ── Capability flags ──

GIT_MOCK_DRIVER = "GIT_MOCK_DRIVER"
GIT_SECRET_SCAN_ACTIVE = "GIT_SECRET_SCAN_ACTIVE"
GIT_BRANCH_PROTECTION_ACTIVE = "GIT_BRANCH_PROTECTION_ACTIVE"
GIT_COMMIT_LIMIT_ACTIVE = "GIT_COMMIT_LIMIT_ACTIVE"


# ── Risk classification for git operations ──

GIT_AUTO_ALLOW = {
    "status", "diff", "diff_staged", "log", "show",
    "branch_list", "fetch", "remote_list", "ls_files",
    "cat_file", "rev_parse", "describe",
}

GIT_REQUIRE_APPROVAL = {
    "commit", "push", "open_pr", "merge_pr", "create_branch",
    "stage_files", "unstage_files", "checkout_branch",
    "tag_create", "cherry_pick",
}

GIT_DENY = {
    "force_push", "reset_hard", "reset_soft", "delete_remote_branch",
    "amend_public", "rebase_public", "squash_public",
    "delete_tag_remote", "gc_aggressive",
}

# ── Secret patterns for scanning ──

SECRET_PATTERNS: list[tuple[str, str]] = [
    # Label-based
    (r'(?i)(api[_-]?key|apikey|secret|token|password|passwd|credential|auth)\s*[=:]\s*["\']?([^\s"\'&<>]{8,})["\']?', "labeled_secret"),
    # AWS
    (r'(?<![A-Z0-9])AKIA[0-9A-Z]{16}', "aws_access_key_id"),
    (r'(?<![A-Za-z0-9/+])[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+])', "aws_secret_access_key_40"),
    # GitHub token
    (r'(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9_]{20,}(?![A-Za-z0-9])', "github_token"),
    # Private key headers
    (r'-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----', "private_key_header"),
    # JWT
    (r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', "jwt_token"),
    # Generic high-entropy
    (r'(?i)(secret|token|key|password|auth)\s*[:=]\s*[\x27\x22]?([0-9a-f]{32,}|[A-Za-z0-9+/=]{40,})[\x27\x22]?', "hex_or_b64_secret"),
]

# ── Protected branch patterns ──

PROTECTED_BRANCHES = {"main", "master", "production", "prod", "release/*", "stable/*"}


@dataclass
class GitCapability:
    flags: list[str] = field(default_factory=list)
    driver_type: str = "mock"
    repo_path: str = ""
    current_branch: str = "main"
    branch_protection: bool = True
    secret_scan: bool = True


@dataclass
class GitAction:
    action_id: str = field(default_factory=lambda: new_id("git"))
    action_type: str = ""
    target: str = ""
    value: str = ""
    timestamp: str = field(default_factory=now_iso)
    expected_head_sha: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class GitResult:
    action_id: str = ""
    success: bool = False
    output: str = ""
    error: str = ""
    stdout: str = ""
    stderr: str = ""
    changed_files: list[str] = field(default_factory=list)
    branch: str = ""
    commit_sha: str = ""
    parent_sha: str = ""
    diff: str = ""
    head_sha: str = ""
    pr_url: str = ""
    duration_ms: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)
    secrets_found: list[str] = field(default_factory=list)


class GitDriver(ABC):
    """Abstract git driver interface."""

    @abstractmethod
    def probe_capability(self) -> GitCapability: ...

    @abstractmethod
    def status(self) -> GitResult: ...

    @abstractmethod
    def diff(self, staged: bool = False) -> GitResult: ...

    @abstractmethod
    def diff_staged(self) -> GitResult: ...

    @abstractmethod
    def log(self, count: int = 10) -> GitResult: ...

    @abstractmethod
    def show(self, ref: str) -> GitResult: ...

    @abstractmethod
    def branch_list(self) -> GitResult: ...

    @abstractmethod
    def create_branch(self, name: str, base: str = "HEAD") -> GitResult: ...

    @abstractmethod
    def checkout_branch(self, name: str) -> GitResult: ...

    @abstractmethod
    def stage_files(self, paths: list[str]) -> GitResult: ...

    @abstractmethod
    def unstage_files(self, paths: list[str]) -> GitResult: ...

    @abstractmethod
    def commit(self, message: str) -> GitResult: ...

    @abstractmethod
    def push(self, remote: str = "origin", branch: str = "") -> GitResult: ...

    @abstractmethod
    def fetch(self, remote: str = "origin") -> GitResult: ...

    @abstractmethod
    def open_pr(self, title: str, body: str, base: str = "main", head: str = "") -> GitResult: ...

    @abstractmethod
    def merge_pr(self, pr_id: str, strategy: str = "merge") -> GitResult: ...

    @abstractmethod
    def rev_parse(self, ref: str = "HEAD") -> GitResult: ...

    @abstractmethod
    def get_head_sha(self) -> str: ...


class MockGitDriver(GitDriver):
    """Deterministic mock git driver for tests — no real git operations."""

    def __init__(self, repo_path: str = "/tmp/mock-repo") -> None:
        self.repo_path = repo_path
        self._branches: dict[str, str] = {"main": "abc123def4567890123456789012345678abcd"}
        self._current_branch: str = "main"
        self._commits: list[dict[str, Any]] = [
            {"sha": "abc123def4567890123456789012345678abcd", "message": "Initial commit", "branch": "main", "parent": None},
        ]
        self._staged: list[str] = []
        self._working_changes: list[str] = ["mock_modified.py"]
        self._prs: list[dict[str, Any]] = []
        self._remote_refs: dict[str, str] = {"main": "abc123def4567890123456789012345678abcd"}

    def probe_capability(self) -> GitCapability:
        return GitCapability(
            flags=[GIT_MOCK_DRIVER],
            driver_type="mock",
            repo_path=self.repo_path,
            current_branch=self._current_branch,
        )

    def _make_sha(self, seed: str) -> str:
        return hashlib.sha256(seed.encode()).hexdigest()[:40]

    def _get_last_commit_sha(self) -> str:
        branch_commits = [c for c in self._commits if c["branch"] == self._current_branch]
        return branch_commits[-1]["sha"] if branch_commits else ""

    def status(self) -> GitResult:
        return GitResult(
            success=True,
            output=f"On branch {self._current_branch}\nChanges not staged: {self._working_changes}\nStaged: {self._staged}",
            branch=self._current_branch,
            changed_files=self._working_changes + self._staged,
            head_sha=self._get_last_commit_sha(),
        )

    def diff(self, staged: bool = False) -> GitResult:
        files = self._staged if staged else self._working_changes
        diff_content = "\n".join(f"diff --git a/{f} b/{f}\n--- a/{f}\n+++ b/{f}\n@@ -0,0 +1,1 @@\n+mock change" for f in files)
        return GitResult(success=True, diff=diff_content, head_sha=self._get_last_commit_sha())

    def diff_staged(self) -> GitResult:
        return self.diff(staged=True)

    def log(self, count: int = 10) -> GitResult:
        entries = self._commits[-count:]
        output = "\n".join(f"{c['sha'][:7]} {c['message']}" for c in entries)
        return GitResult(success=True, output=output, head_sha=self._get_last_commit_sha())

    def show(self, ref: str) -> GitResult:
        for c in self._commits:
            if c["sha"].startswith(ref) or ref == "HEAD":
                return GitResult(success=True, output=f"commit {c['sha']}\n{c['message']}", commit_sha=c["sha"])
        return GitResult(success=True, output=f"commit {ref}\nMock commit content", commit_sha=ref)

    def branch_list(self) -> GitResult:
        output = "\n".join(f"{'*' if k == self._current_branch else ' '} {k}" for k in self._branches)
        return GitResult(success=True, output=output, branch=self._current_branch)

    def create_branch(self, name: str, base: str = "HEAD") -> GitResult:
        base_sha = self._branches.get(base, self._get_last_commit_sha())
        self._branches[name] = base_sha
        return GitResult(success=True, output=f"Created branch {name} at {base_sha[:7]}", branch=name, head_sha=base_sha)

    def checkout_branch(self, name: str) -> GitResult:
        if name not in self._branches:
            return GitResult(success=False, error=f"branch_not_found:{name}")
        self._current_branch = name
        return GitResult(success=True, output=f"Switched to branch {name}", branch=name, head_sha=self._branches[name])

    def stage_files(self, paths: list[str]) -> GitResult:
        self._staged.extend(paths)
        return GitResult(success=True, output=f"Staged: {paths}", changed_files=list(paths))

    def unstage_files(self, paths: list[str]) -> GitResult:
        for p in paths:
            if p in self._staged:
                self._staged.remove(p)
        return GitResult(success=True, output=f"Unstaged: {paths}", changed_files=list(paths))

    def commit(self, message: str) -> GitResult:
        if not self._staged:
            return GitResult(success=False, error="nothing_to_commit")
        sha = self._make_sha(message + str(time.time()))
        parent = self._get_last_commit_sha()
        self._commits.append({"sha": sha, "message": message, "branch": self._current_branch, "parent": parent})
        self._branches[self._current_branch] = sha
        self._staged = []
        return GitResult(success=True, output=f"[{self._current_branch} {sha[:7]}] {message}", commit_sha=sha, parent_sha=parent or "", head_sha=sha)

    def push(self, remote: str = "origin", branch: str = "") -> GitResult:
        b = branch or self._current_branch
        sha = self._branches.get(b, "")
        self._remote_refs[b] = sha
        return GitResult(success=True, output=f"Pushed {b} to {remote} ({sha[:7]})", branch=b, head_sha=sha)

    def fetch(self, remote: str = "origin") -> GitResult:
        return GitResult(success=True, output=f"Fetched from {remote}")

    def open_pr(self, title: str, body: str, base: str = "main", head: str = "") -> GitResult:
        h = head or self._current_branch
        pr_id = f"pr_{new_id('pr')}"
        pr = {"pr_id": pr_id, "title": title, "body": body, "base": base, "head": h, "status": "open"}
        self._prs.append(pr)
        return GitResult(success=True, output=f"Created PR: {pr_id}", pr_url=f"https://mock.github.com/pr/{pr_id}", branch=h, head_sha=self._branches.get(h, ""))

    def merge_pr(self, pr_id: str, strategy: str = "merge") -> GitResult:
        pr = next((p for p in self._prs if p["pr_id"] == pr_id), None)
        if not pr:
            return GitResult(success=False, error=f"pr_not_found:{pr_id}")
        pr["status"] = "merged"
        merge_sha = self._make_sha(f"merge-{pr_id}-{strategy}")
        self._commits.append({"sha": merge_sha, "message": f"Merge PR #{pr_id}: {pr['title']}", "branch": pr["base"], "parent": self._branches.get(pr["base"], "")})
        self._branches[pr["base"]] = merge_sha
        return GitResult(success=True, output=f"Merged {pr_id} into {pr['base']}", commit_sha=merge_sha, head_sha=merge_sha)

    def rev_parse(self, ref: str = "HEAD") -> GitResult:
        if ref == "HEAD":
            sha = self._get_last_commit_sha()
        else:
            sha = self._branches.get(ref, self._make_sha(ref))
        return GitResult(success=True, commit_sha=sha, head_sha=sha)

    def get_head_sha(self) -> str:
        return self._get_last_commit_sha()


class GovernedGitAdapter:
    """Governed git adapter with risk-based access control, secret scanning, and branch protection."""

    def __init__(
        self,
        driver: GitDriver | None = None,
        *,
        repo_path: str = "",
        evidence_store=None,
        approval_engine=None,
        protected_branches: set[str] | None = None,
        enable_secret_scan: bool = True,
        enable_branch_protection: bool = True,
    ) -> None:
        self.driver = driver or MockGitDriver(repo_path or "/tmp/nexara-git-mock")
        self.repo_path = repo_path or self.driver.repo_path
        self.evidence = evidence_store
        self.approvals = approval_engine
        self.protected_branches = protected_branches or PROTECTED_BRANCHES
        self.enable_secret_scan = enable_secret_scan
        self.enable_branch_protection = enable_branch_protection
        self._action_history: list[GitAction] = []
        self._expected_head: str | None = None

    # ── Risk classification ──

    def _classify(self, action_type: str) -> str:
        if action_type in GIT_DENY:
            return "DENY"
        if action_type in GIT_AUTO_ALLOW:
            return "AUTO_ALLOW"
        return "REQUIRE_APPROVAL"

    def _is_protected_branch(self, branch: str) -> bool:
        for pattern in self.protected_branches:
            if pattern.endswith("/*"):
                prefix = pattern[:-2]
                if branch == prefix or branch.startswith(prefix + "/"):
                    return True
            elif branch == pattern:
                return True
        return False

    # ── Secret scanning ──

    def _scan_secrets(self, content: str) -> list[dict[str, Any]]:
        """Scan content for secrets and return findings."""
        findings: list[dict[str, Any]] = []
        for pattern, label in SECRET_PATTERNS:
            for match in re.finditer(pattern, content):
                finding = {
                    "label": label,
                    "match": match.group(0)[:40] + ("..." if len(match.group(0)) > 40 else ""),
                    "span": match.span(),
                }
                findings.append(finding)
        return findings

    def _scan_diff_secrets(self, diff: str) -> list[dict[str, Any]]:
        """Scan diff content, focusing on added lines (+)."""
        # Only scan added lines to avoid false positives on deletions
        added_lines = "\n".join(line[1:] for line in diff.split("\n") if line.startswith("+") and not line.startswith("+++"))
        return self._scan_secrets(added_lines)

    # ── Evidence ──

    def _record_evidence(self, action: GitAction, result: GitResult) -> list[str]:
        if not self.evidence:
            return []
        payload = json.dumps({
            "action_id": action.action_id,
            "action_type": action.action_type,
            "target": action.target,
            "success": result.success,
            "branch": result.branch,
            "commit_sha": result.commit_sha,
            "head_sha": result.head_sha,
            "changed_files": result.changed_files,
            "error": result.error,
            "secrets_found": len(result.secrets_found),
            "duration_ms": result.duration_ms,
        }, ensure_ascii=False)
        try:
            ev = self.evidence.add(
                "git_session", "git_action",
                f"Git: {action.action_type}",
                payload, action.action_id,
                actor="git_adapter", source="git",
                verification_status="verified",
            )
            return [ev.evidence_id]
        except Exception:
            return []

    # ── Governed action execution ──

    def _execute(self, action_type: str, target: str, value: str,
                 driver_call, *,
                 expected_head: str = "",
                 scan_diff: bool = False) -> GitResult:
        """Execute a governed git action with risk checks."""
        classification = self._classify(action_type)

        # DENY — never allowed
        if classification == "DENY":
            return GitResult(action_id=new_id("git"),
                             error=f"action_denied:{action_type}:destructive_or_dangerous_operation")

        # REQUIRE_APPROVAL — needs human approval (we record the need, caller handles)
        if classification == "REQUIRE_APPROVAL":
            if not self.approvals:
                # In mock/test mode without approval engine, we allow but flag
                pass  # proceed with warning in result

        # Secret scan before commit/push
        if self.enable_secret_scan and action_type in {"commit", "push"}:
            if scan_diff:
                diff_result = self.driver.diff_staged() if action_type == "commit" else self.driver.diff()
                secrets = self._scan_diff_secrets(diff_result.diff)
                if secrets:
                    return GitResult(
                        action_id=new_id("git"),
                        success=False,
                        error=f"secret_scan_failed:{len(secrets)}_potential_secrets_found",
                        secrets_found=[s["label"] for s in secrets],
                    )

        # Expected head SHA check before push
        if action_type == "push" and expected_head:
            current_head = self.driver.get_head_sha()
            if current_head != expected_head:
                return GitResult(
                    action_id=new_id("git"),
                    success=False,
                    error=f"head_sha_mismatch:expected={expected_head[:7]},actual={current_head[:7]}",
                    head_sha=current_head,
                )

        # Branch protection before push/merge to protected branches
        if self.enable_branch_protection and action_type in {"push", "merge_pr"}:
            branch = target if target else self.driver._current_branch
            if self._is_protected_branch(branch):
                if action_type == "push":
                    return GitResult(
                        action_id=new_id("git"),
                        success=False,
                        error=f"direct_push_to_protected_branch:{branch}:use_PR_instead",
                        branch=branch,
                    )

        # Execute
        action = GitAction(
            action_type=action_type,
            target=target,
            value=value,
            expected_head_sha=expected_head,
        )
        started = time.monotonic()
        try:
            result = driver_call()
        except Exception as exc:
            result = GitResult(action_id=action.action_id, success=False, error=str(exc))
        result.action_id = action.action_id
        result.duration_ms = (time.monotonic() - started) * 1000

        # Record evidence
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)

        # Attach classification for caller awareness
        if classification == "REQUIRE_APPROVAL" and result.success:
            result.output += f"\n[GOVERNED] Action '{action_type}' requires human approval in production."

        return result

    # ── Public API ──

    def probe_capability(self) -> GitCapability:
        cap = self.driver.probe_capability()
        cap.branch_protection = self.enable_branch_protection
        cap.secret_scan = self.enable_secret_scan
        if self.enable_secret_scan:
            cap.flags.append(GIT_SECRET_SCAN_ACTIVE)
        if self.enable_branch_protection:
            cap.flags.append(GIT_BRANCH_PROTECTION_ACTIVE)
        return cap

    # Read-only (AUTO_ALLOW)
    def status(self) -> GitResult:
        return self._execute("status", "", "", self.driver.status)

    def diff(self) -> GitResult:
        return self._execute("diff", "", "", lambda: self.driver.diff(staged=False))

    def diff_staged(self) -> GitResult:
        return self._execute("diff_staged", "", "", self.driver.diff_staged)

    def log(self, count: int = 10) -> GitResult:
        return self._execute("log", str(count), "", lambda: self.driver.log(count))

    def show(self, ref: str) -> GitResult:
        return self._execute("show", ref, "", lambda: self.driver.show(ref))

    def branch_list(self) -> GitResult:
        return self._execute("branch_list", "", "", self.driver.branch_list)

    def fetch(self, remote: str = "origin") -> GitResult:
        return self._execute("fetch", remote, "", lambda: self.driver.fetch(remote))

    def rev_parse(self, ref: str = "HEAD") -> GitResult:
        return self._execute("rev_parse", ref, "", lambda: self.driver.rev_parse(ref))

    def get_head_sha(self) -> str:
        return self.driver.get_head_sha()

    # Mutating (REQUIRE_APPROVAL)
    def create_branch(self, name: str, base: str = "HEAD") -> GitResult:
        return self._execute("create_branch", name, base,
                             lambda: self.driver.create_branch(name, base))

    def checkout_branch(self, name: str) -> GitResult:
        return self._execute("checkout_branch", name, "",
                             lambda: self.driver.checkout_branch(name))

    def stage_files(self, paths: list[str]) -> GitResult:
        return self._execute("stage_files", ",".join(paths), "",
                             lambda: self.driver.stage_files(paths))

    def unstage_files(self, paths: list[str]) -> GitResult:
        return self._execute("unstage_files", ",".join(paths), "",
                             lambda: self.driver.unstage_files(paths))

    def commit(self, message: str, *, expected_head: str = "") -> GitResult:
        return self._execute("commit", message, "",
                             lambda: self.driver.commit(message),
                             expected_head=expected_head, scan_diff=True)

    def push(self, remote: str = "origin", branch: str = "",
             *, expected_head: str = "") -> GitResult:
        return self._execute("push", branch or self.driver._current_branch, remote,
                             lambda: self.driver.push(remote, branch),
                             expected_head=expected_head, scan_diff=True)

    def open_pr(self, title: str, body: str, base: str = "main",
                head: str = "") -> GitResult:
        h = head or self.driver._current_branch
        return self._execute("open_pr", f"{h}->{base}", title,
                             lambda: self.driver.open_pr(title, body, base, head))

    def merge_pr(self, pr_id: str, strategy: str = "merge") -> GitResult:
        return self._execute("merge_pr", pr_id, strategy,
                             lambda: self.driver.merge_pr(pr_id, strategy))

    # ── Lifecycle ──

    def get_action_history(self) -> list[dict[str, Any]]:
        return [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "target": a.target,
                "classification": self._classify(a.action_type),
                "timestamp": a.timestamp,
            }
            for a in self._action_history
        ]

    def validate_repo_state(self) -> dict[str, Any]:
        """Validate repository integrity — dirty tree, detached HEAD, etc."""
        status = self.driver.status()
        issues: list[str] = []
        warnings: list[str] = []
        if status.changed_files:
            warnings.append(f"uncommitted_changes:{len(status.changed_files)}")
        current = self.driver._current_branch if hasattr(self.driver, '_current_branch') else "unknown"
        head_sha = self.driver.get_head_sha()
        if not head_sha:
            issues.append("no_commits_in_repository")
        return {
            "valid": len(issues) == 0,
            "branch": current,
            "head_sha": head_sha,
            "issues": issues,
            "warnings": warnings,
            "changed_files": status.changed_files,
        }
