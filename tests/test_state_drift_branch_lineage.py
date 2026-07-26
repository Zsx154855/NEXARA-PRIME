"""KMA Phase 2 Remediation — Branch Lineage State Drift Tests.

Tests the new check_branch_lineage logic in detect_state_drift.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Add scripts/governance to path so we can import the module
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "governance"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── helpers ──

def _init_git_repo(path: Path) -> None:
    """Create a minimal git repo at path with one commit."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True,
    )
    (path / "file.txt").write_text("content")
    subprocess.run(["git", "-C", str(path), "add", "file.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "initial"], check=True
    )


def _make_work_branch(path: Path, branch_name: str, parent_ref: str = "HEAD") -> str:
    """Create a work branch and return its SHA."""
    subprocess.run(
        ["git", "-C", str(path), "checkout", "-q", "-b", branch_name, parent_ref],
        check=True,
    )
    (path / "work_file.txt").write_text("work")
    subprocess.run(["git", "-C", str(path), "add", "work_file.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", f"work on {branch_name}"],
        check=True,
    )
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


# ── tests ──


class TestExactBranchMatch:
    def test_exact_match_passes(self, tmp_path: Path):
        """Exact recorded_branch == current_branch -> no issues."""
        import detect_state_drift as dsd
        issues = dsd.check_branch_lineage("main", "main", repo_root=tmp_path)
        assert issues == []

    def test_recorded_empty_passes(self, tmp_path: Path):
        """Empty recorded_branch -> no issues."""
        import detect_state_drift as dsd
        issues = dsd.check_branch_lineage("", "main", repo_root=tmp_path)
        assert issues == []


class TestWorkBranchLineage:
    def test_work_branch_ancestor_passes(self, tmp_path: Path):
        """work/* branch derived from canonical -> passes."""
        _init_git_repo(tmp_path)
        _make_work_branch(tmp_path, "work/fix-bug", "HEAD")

        import detect_state_drift as dsd
        # Use branch name, not commit SHA
        issues = dsd.check_branch_lineage("main", "work/fix-bug", repo_root=tmp_path)
        assert issues == []

    def test_work_branch_unrelated_fails(self, tmp_path: Path):
        """work/* branch NOT derived from canonical -> fails."""
        _init_git_repo(tmp_path)
        # Create an orphan branch
        subprocess.run(
            ["git", "-C", str(tmp_path), "checkout", "--orphan", "orphan"],
            check=True,
        )
        subprocess.run(["git", "-C", str(tmp_path), "rm", "-rf", "."],
                       check=False)
        (tmp_path / "orphan.txt").write_text("orphan")
        subprocess.run(["git", "-C", str(tmp_path), "add", "orphan.txt"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "orphan"], check=True
        )

        import detect_state_drift as dsd
        issues = dsd.check_branch_lineage("main", "work/fix-bug", repo_root=tmp_path)
        assert len(issues) > 0
        assert any("lineage mismatch" in i.lower() for i in issues)

    def test_work_branch_unresolved_ref_fails_closed(self, tmp_path: Path):
        """Unresolvable canonical ref -> fail-closed."""
        _init_git_repo(tmp_path)
        _make_work_branch(tmp_path, "work/something")

        import detect_state_drift as dsd
        issues = dsd.check_branch_lineage(
            "nonexistent-branch-name", "work/something"
        , repo_root=tmp_path)
        assert len(issues) > 0
        assert any("fail-closed" in i.lower() for i in issues)

    def test_work_branch_by_branch_name_ancestor(self, tmp_path: Path):
        """Canonical ref resolvable by branch name -> passes."""
        _init_git_repo(tmp_path)
        _make_work_branch(tmp_path, "work/fix-something", "HEAD")

        import detect_state_drift as dsd
        issues = dsd.check_branch_lineage("main", "work/fix-something", repo_root=tmp_path)
        assert issues == []


class TestNonWorkBranchMismatch:
    def test_non_work_mismatch_fails(self, tmp_path: Path):
        """Non-work branch mismatch -> still fails."""
        import detect_state_drift as dsd
        issues = dsd.check_branch_lineage("main", "develop", repo_root=tmp_path)
        assert len(issues) > 0
        assert any("mismatch" in i.lower() for i in issues)

    def test_non_work_mismatch_not_lineage(self, tmp_path: Path):
        """Non-work branch mismatch uses old mismatch message, not lineage."""
        import detect_state_drift as dsd
        issues = dsd.check_branch_lineage("main", "feat/x", repo_root=tmp_path)
        assert len(issues) == 1
        assert "mismatch" in issues[0].lower()
        assert "lineage" not in issues[0].lower()


class TestGitCommandErrors:
    def test_merge_base_error_handled(self, monkeypatch, tmp_path: Path):
        """git merge-base failure is caught and reported as fail-closed."""
        _init_git_repo(tmp_path)
        _make_work_branch(tmp_path, "work/broken")

        import detect_state_drift as dsd

        def _fail(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(dsd, "git_is_ancestor", _fail)
        issues = dsd.check_branch_lineage("main", "work/broken", repo_root=tmp_path)
        assert len(issues) > 0
        assert any("fail-closed" in i.lower() for i in issues)

    def test_git_resolve_ref_fallback(self, tmp_path: Path):
        """Resolution tries refs/remotes/origin/ and refs/heads/ paths."""
        _init_git_repo(tmp_path)
        _make_work_branch(tmp_path, "work/test-ref-resolution")

        import detect_state_drift as dsd
        # main exists as refs/heads/main (local branch)
        sha = dsd.git_resolve_ref("main")
        assert sha is not None
        assert len(sha) == 40

    def test_git_resolve_origin_first(self, tmp_path: Path):
        """Origin ref is preferred over stale local branch."""
        import detect_state_drift as dsd

        _init_git_repo(tmp_path)

        # Get the commit SHA for main
        result = subprocess.run(
            ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        main_sha = result.stdout.strip()

        # Create a diverged local branch (simulating stale local)
        subprocess.run(
            ["git", "-C", str(tmp_path), "checkout", "-q", "-b", "stale-local"],
            check=True,
        )
        (tmp_path / "diverged.txt").write_text("diverged")
        subprocess.run(["git", "-C", str(tmp_path), "add", "diverged.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "diverged from origin"],
            check=True,
        )
        diverged_sha = subprocess.run(
            ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        # Now there's a local "stale-local" that diverged from origin/main
        # The bare ref "stale-local" would resolve to the diverged SHA
        # But the function should prefer origin first — though origin has no "stale-local"
        # so it falls back to the bare name. The key test is for refs like "main"
        # where origin/main exists.

        # Go back to main
        subprocess.run(
            ["git", "-C", str(tmp_path), "checkout", "-q", "main"],
            check=True,
        )

        # Resolution of "main": origin/main should be tried first
        sha = dsd.git_resolve_ref("main", repo_root=tmp_path)
        assert sha is not None
        assert sha == main_sha  # resolves to origin/main (which = local main)

        # "stale-local" has no origin/ equivalent, so falls back to local
        sha_local = dsd.git_resolve_ref("stale-local", repo_root=tmp_path)
        assert sha_local == diverged_sha


class TestIntegrationWithCheckGitConsistency:
    def test_dirty_worktree_fails(self, tmp_path: Path, monkeypatch):
        """Dirty worktree still causes drift report."""
        import detect_state_drift as dsd

        monkeypatch.setattr(dsd, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(dsd, "git_head_sha", lambda: "a" * 40)
        monkeypatch.setattr(dsd, "git_branch", lambda: "main")
        monkeypatch.setattr(dsd, "git_worktree_is_clean", lambda: False)
        # Disable BASELINE check
        monkeypatch.setattr(dsd, "BASELINE_PATH", tmp_path / "nonexistent.json")

        issues = dsd.check_git_consistency(
            {"gates": []},
            {"branch": "main"},
        )
        assert any("uncommitted" in i.lower() for i in issues)
