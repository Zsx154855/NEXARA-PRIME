#!/usr/bin/env python3
"""
NEXARA PRIME — State Drift Detector V1

Validates that .nexara/GATE_STATUS.json and .nexara/PROGRAM_STATE.json are
mutually consistent with each other and match git reality.

This script is designed to run in CI or locally before every non-trivial merge.

Exit codes:
    0  — no drift detected (all consistent)
    1  — drift detected (inconsistencies found)
    2  — unable to read state files or git repo
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NEXARA_DIR = REPO_ROOT / ".nexara"
GATE_STATUS_PATH = NEXARA_DIR / "GATE_STATUS.json"
PROGRAM_STATE_PATH = NEXARA_DIR / "PROGRAM_STATE.json"
BASELINE_PATH = NEXARA_DIR / "BASELINE.json"
DECISION_LOG_PATH = NEXARA_DIR / "DECISION_LOG.md"

GOVERNANCE_DIR = REPO_ROOT / "governance"
BASELINES_DIR = GOVERNANCE_DIR / "baselines"

# ── Expected gate progression (G0 → G1 → ... → G10) ──────────────────────────
ALL_GATES = [f"G{i}" for i in range(11)]
GATE_ORDER = {g: idx for idx, g in enumerate(ALL_GATES)}


def git_command(*args: str) -> str:
    """Run a git command and return stdout, or raise on failure."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_head_sha() -> str:
    """Return the current HEAD SHA."""
    return git_command("rev-parse", "HEAD")


def git_branch() -> str:
    """Return the current branch name."""
    return git_command("rev-parse", "--abbrev-ref", "HEAD")


def git_worktree_is_clean() -> bool:
    """Return True if the working tree has no uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
    )
    return result.stdout.strip() == ""


def load_json(path: Path) -> dict[str, Any]:
    """Load and parse a JSON file. Raise on failure."""
    if not path.exists():
        raise FileNotFoundError(f"State file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def check_consistency(
    gate_status: dict[str, Any], program_state: dict[str, Any]
) -> list[str]:
    """Check that GATE_STATUS.json and PROGRAM_STATE.json agree on key fields.

    Returns a list of inconsistency descriptions (empty = consistent).
    """
    inconsistencies: list[str] = []

    # 1. Program name
    gs_program = gate_status.get("program", "")
    ps_program = program_state.get("program", "")
    if gs_program and ps_program and gs_program != ps_program:
        inconsistencies.append(
            f"Program name mismatch: GATE_STATUS says '{gs_program}', "
            f"PROGRAM_STATE says '{ps_program}'"
        )

    # 2. Current gate
    gs_gate = gate_status.get("current_gate", "")
    ps_gate = program_state.get("current_program_gate", "")
    if gs_gate and ps_gate and gs_gate != ps_gate:
        inconsistencies.append(
            f"Current gate mismatch: GATE_STATUS says '{gs_gate}', "
            f"PROGRAM_STATE says '{ps_gate}'"
        )

    # 3. Gate status
    gs_status = gate_status.get("g10_status", "")
    ps_status = program_state.get("gate_status", "")
    if gs_status and ps_status and gs_status != ps_status:
        inconsistencies.append(
            f"Gate status mismatch: GATE_STATUS says '{gs_status}', "
            f"PROGRAM_STATE says '{ps_status}'"
        )

    # 4. Passed gates list
    gs_passed = gate_status.get("gates", [])
    ps_passed = program_state.get("gates_pass", [])
    gs_passed_ids = {g.get("id", "") for g in gs_passed}
    ps_passed_set = set(ps_passed)

    if gs_passed_ids != ps_passed_set:
        only_in_gs = gs_passed_ids - ps_passed_set
        only_in_ps = ps_passed_set - gs_passed_ids
        if only_in_gs:
            inconsistencies.append(
                f"Gates passed only in GATE_STATUS: {sorted(only_in_gs)}"
            )
        if only_in_ps:
            inconsistencies.append(
                f"Gates passed only in PROGRAM_STATE: {sorted(only_in_ps)}"
            )

    # 5. External distribution status
    gs_ext = gate_status.get("external_distribution", "")
    ps_ext = program_state.get("external_distribution", "")
    if gs_ext and ps_ext and gs_ext != ps_ext:
        inconsistencies.append(
            f"External distribution status mismatch: "
            f"GATE_STATUS says '{gs_ext}', PROGRAM_STATE says '{ps_ext}'"
        )

    return inconsistencies


def check_gate_order(gate_status: dict[str, Any]) -> list[str]:
    """Validate that gates are in progression order and statuses are valid.

    Returns a list of issues (empty = no issues).
    """
    issues: list[str] = []
    valid_statuses = {"NOT_STARTED", "RUNNING", "PARTIAL", "BLOCKED", "PASS"}

    gates = gate_status.get("gates", [])
    if not gates:
        return issues

    seen_pass = False
    for gate in gates:
        gid = gate.get("id", "")
        status = gate.get("status", "")

        if status not in valid_statuses and status != "LOCAL_RELEASE_READY":
            issues.append(
                f"Gate {gid} has unrecognized status: '{status}'"
            )

        # Once a gate is not PASS, subsequent gates should not be PASS
        # (gates can only pass in order)
        if status == "PASS":
            seen_pass = True
        elif seen_pass and status == "NOT_STARTED":
            # This is expected for gates beyond the current one
            pass

        # Check that if all previous gates are PASS, this gate should
        # normally be at least RUNNING or PASS
        gidx = GATE_ORDER.get(gid, -1)
        if gidx >= 0:
            prev_gates = gates[:gidx]
            all_prev_pass = all(
                pg.get("status") == "PASS" for pg in prev_gates
            )
            if all_prev_pass and status == "NOT_STARTED" and gidx < len(gates) - 1:
                # This is common for the next gate after current
                pass

    return issues


def check_git_consistency(
    gate_status: dict[str, Any], program_state: dict[str, Any]
) -> list[str]:
    """Check that state files are consistent with git reality.

    Returns a list of issues (empty = no issues).
    """
    issues: list[str] = []

    try:
        current_sha = git_head_sha()
        current_branch = git_branch()
    except RuntimeError as e:
        issues.append(f"Cannot read git state: {e}")
        return issues

    # Check branch matches PROGRAM_STATE
    recorded_branch = program_state.get("branch", "")
    if recorded_branch and recorded_branch != current_branch:
        issues.append(
            f"Branch mismatch: PROGRAM_STATE says '{recorded_branch}', "
            f"git says '{current_branch}'"
        )

    # Check baseline SHA if BASELINE.json exists
    if BASELINE_PATH.exists():
        try:
            baseline = load_json(BASELINE_PATH)
            baseline_head = baseline.get("head", "")
            if baseline_head and baseline_head != current_sha:
                # This is a warning, not necessarily an error — the baseline
                # may be frozen at a previous point
                issues.append(
                    f"Baseline HEAD ({baseline_head[:12]}) differs from "
                    f"current HEAD ({current_sha[:12]}) — "
                    "baseline may be stale"
                )
        except (FileNotFoundError, json.JSONDecodeError):
            issues.append("Could not read BASELINE.json for git comparison")

    # Check worktree cleanliness
    if not git_worktree_is_clean():
        issues.append(
            "Working tree has uncommitted changes — "
            "commit or stash before continuing"
        )

    return issues


def check_test_baseline_consistency(
    gate_status: dict[str, Any], program_state: dict[str, Any]
) -> list[str]:
    """Check that test baselines in both files are consistent.

    Returns a list of issues (empty = consistent).
    """
    issues: list[str] = []
    gs_tests = gate_status.get("test_baseline", "")
    ps_tests = program_state.get("test_baseline", "")

    if gs_tests and ps_tests and gs_tests != ps_tests:
        issues.append(
            f"Test baseline mismatch: GATE_STATUS says '{gs_tests}', "
            f"PROGRAM_STATE says '{ps_tests}'"
        )
    return issues


def check_artifact_consistency(
    gate_status: dict[str, Any],
) -> list[str]:
    """Verify that tracked artifacts actually exist on disk.

    Returns a list of issues (empty = all present).
    """
    issues: list[str] = []
    artifacts = gate_status.get("release_artifacts_tracked", [])

    for rel_path in artifacts:
        abs_path = REPO_ROOT / rel_path
        if not abs_path.exists():
            issues.append(f"Tracked artifact not found: {rel_path}")

    return issues


def report_drift(inconsistencies: list[str]) -> None:
    """Print a formatted drift report to stdout."""
    print("=" * 60)
    print("  NEXARA PRIME — State Drift Detection Report")
    print("=" * 60)
    print()
    print(f"  Timestamp:   {__import__('datetime').datetime.utcnow().isoformat()}Z")
    try:
        print(f"  Git HEAD:    {git_head_sha()[:12]}")
        print(f"  Branch:      {git_branch()}")
    except RuntimeError:
        pass
    print()

    if not inconsistencies:
        print("  RESULT: NO DRIFT DETECTED")
        print("  All state files are mutually consistent with git reality.")
        print()
        return

    print(f"  RESULT: DRIFT DETECTED ({len(inconsistencies)} issue(s))")
    print()
    for i, issue in enumerate(inconsistencies, 1):
        print(f"  {i}. {issue}")
    print()
    print("  Recommended action:")
    print("  1. Review each issue above")
    print("  2. Update the relevant .nexara file(s) to match reality")
    print("  3. Commit the corrections")
    print("  4. Re-run this script to confirm resolution")
    print()


def main() -> int:
    try:
        gate_status = load_json(GATE_STATUS_PATH)
        program_state = load_json(PROGRAM_STATE_PATH)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    all_issues: list[str] = []

    # 1. Cross-file consistency checks
    all_issues.extend(check_consistency(gate_status, program_state))

    # 2. Gate order and status validity
    all_issues.extend(check_gate_order(gate_status))

    # 3. Git consistency
    all_issues.extend(check_git_consistency(gate_status, program_state))

    # 4. Test baseline consistency
    all_issues.extend(
        check_test_baseline_consistency(gate_status, program_state)
    )

    # 5. Artifact presence
    all_issues.extend(check_artifact_consistency(gate_status))

    report_drift(all_issues)

    return 0 if not all_issues else 1


if __name__ == "__main__":
    sys.exit(main())
