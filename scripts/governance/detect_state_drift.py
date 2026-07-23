#!/usr/bin/env python3
"""NEXARA PRIME — authoritative state drift detector.

Validates that ``.nexara/GATE_STATUS.json`` and
``.nexara/PROGRAM_STATE.json`` agree with each other and with repository
reality. Missing governance state is treated as drift: the detector is
fail-closed rather than silently accepting partially migrated schemas.

Exit codes:
    0 — no drift detected
    1 — drift detected
    2 — state or repository could not be read
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NEXARA_DIR = REPO_ROOT / ".nexara"
GATE_STATUS_PATH = NEXARA_DIR / "GATE_STATUS.json"
PROGRAM_STATE_PATH = NEXARA_DIR / "PROGRAM_STATE.json"
BASELINE_PATH = NEXARA_DIR / "BASELINE.json"

ALL_GATES = [f"G{i}" for i in range(11)]
GATE_ORDER = {gate: index for index, gate in enumerate(ALL_GATES)}
VALID_GATE_STATUSES = {
    "NOT_STARTED",
    "RUNNING",
    "PARTIAL",
    "BLOCKED",
    "PASS",
    "LOCAL_RELEASE_READY",
}
G10_FIELDS = (
    "local_release",
    "external_distribution",
    "git_push_tag",
    "product_brand_name",
)


def git_command(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_head_sha() -> str:
    return git_command("rev-parse", "HEAD")


def git_branch() -> str:
    return git_command("rev-parse", "--abbrev-ref", "HEAD")


def git_worktree_is_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return not result.stdout.strip()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"State file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"State file root must be an object: {path}")
    return data


def _validate_composite(
    owner: str,
    value: Any,
    inconsistencies: list[str],
) -> dict[str, Any] | None:
    if value is None:
        inconsistencies.append(
            f"{owner} is missing 'g10_composite_status' — schema is incomplete"
        )
        return None
    if not isinstance(value, dict):
        inconsistencies.append(
            f"{owner}.g10_composite_status must be an object, "
            f"got {type(value).__name__}"
        )
        return None

    for field in G10_FIELDS:
        if field not in value:
            inconsistencies.append(
                f"{owner}.g10_composite_status is missing required field '{field}'"
            )
            continue
        field_value = value[field]
        if not isinstance(field_value, str) or not field_value.strip():
            inconsistencies.append(
                f"{owner}.g10_composite_status.{field} must be a non-empty string"
            )
    return value


def check_consistency(
    gate_status: dict[str, Any],
    program_state: dict[str, Any],
) -> list[str]:
    """Return cross-file state inconsistencies."""

    inconsistencies: list[str] = []

    gs_program = gate_status.get("program", "")
    ps_program = program_state.get("program", "")
    if gs_program and ps_program and gs_program != ps_program:
        inconsistencies.append(
            f"Program name mismatch: GATE_STATUS says '{gs_program}', "
            f"PROGRAM_STATE says '{ps_program}'"
        )

    gs_gate = gate_status.get("current_gate", "")
    ps_gate = program_state.get("current_program_gate", "")
    if gs_gate and ps_gate and gs_gate != ps_gate:
        inconsistencies.append(
            f"Current gate mismatch: GATE_STATUS says '{gs_gate}', "
            f"PROGRAM_STATE says '{ps_gate}'"
        )

    gs_composite = _validate_composite(
        "GATE_STATUS",
        gate_status.get("g10_composite_status"),
        inconsistencies,
    )
    ps_composite = _validate_composite(
        "PROGRAM_STATE",
        program_state.get("g10_composite_status"),
        inconsistencies,
    )

    if gs_composite is not None and ps_composite is not None:
        for field in G10_FIELDS:
            gs_value = gs_composite.get(field)
            ps_value = ps_composite.get(field)
            if (
                isinstance(gs_value, str)
                and gs_value.strip()
                and isinstance(ps_value, str)
                and ps_value.strip()
                and gs_value != ps_value
            ):
                inconsistencies.append(
                    f"G10 composite status mismatch for '{field}': "
                    f"GATE_STATUS says '{gs_value}', "
                    f"PROGRAM_STATE says '{ps_value}'"
                )

    if "external_distribution" in gate_status:
        inconsistencies.append(
            "GATE_STATUS has legacy top-level 'external_distribution' — "
            "it must be nested inside 'g10_composite_status'"
        )
    if "external_distribution" in program_state:
        inconsistencies.append(
            "PROGRAM_STATE has legacy top-level 'external_distribution' — "
            "it must be nested inside 'g10_composite_status'"
        )

    gate_entries = gate_status.get("gates", [])
    if not isinstance(gate_entries, list):
        inconsistencies.append("GATE_STATUS.gates must be an array")
        gate_entries = []
    program_passed = program_state.get("gates_pass", [])
    if not isinstance(program_passed, list):
        inconsistencies.append("PROGRAM_STATE.gates_pass must be an array")
        program_passed = []

    gs_passed_ids = {
        entry.get("id", "")
        for entry in gate_entries
        if isinstance(entry, dict) and entry.get("id")
    }
    ps_passed_ids = {str(gate) for gate in program_passed}
    ps_blocked_ids = {str(gate) for gate in program_state.get("gates_blocked", [])}
    ps_all_ids = ps_passed_ids | ps_blocked_ids
    if gs_passed_ids != ps_all_ids:
        only_in_gate_status = gs_passed_ids - ps_passed_ids
        only_in_program_state = ps_passed_ids - gs_passed_ids
        if only_in_gate_status:
            inconsistencies.append(
                "Gates present only in GATE_STATUS: "
                f"{sorted(only_in_gate_status)}"
            )
        if only_in_program_state:
            inconsistencies.append(
                "Gates present only in PROGRAM_STATE.gates_pass: "
                f"{sorted(only_in_program_state)}"
            )

    # Top-level gates_pass validation (GATE_STATUS)
    gs_gates_pass = gate_status.get("gates_pass")
    if gs_gates_pass is not None:
        if not isinstance(gs_gates_pass, list):
            inconsistencies.append("GATE_STATUS.gates_pass must be an array")
        else:
            gs_top_level_ids = {str(g) for g in gs_gates_pass}
            if gs_top_level_ids != gs_passed_ids:
                extra = gs_top_level_ids - gs_passed_ids
                missing = gs_passed_ids - gs_top_level_ids
                if extra:
                    inconsistencies.append(
                        "GATE_STATUS.gates_pass contains gates not present in gates array: "
                        f"{sorted(extra)}"
                    )
                if missing:
                    inconsistencies.append(
                        "GATE_STATUS.gates_pass is missing gates from the gates array: "
                        f"{sorted(missing)}"
                    )

    # PROGRAM_STATE.gate_status vs g10_composite_status.local_release
    ps_gate_status = program_state.get("gate_status", "")
    if ps_composite is not None and ps_gate_status:
        local_release = ps_composite.get("local_release", "")
        if local_release and ps_gate_status != local_release:
            inconsistencies.append(
                f"PROGRAM_STATE.gate_status ('{ps_gate_status}') "
                f"does not match g10_composite_status.local_release ('{local_release}')"
            )

    return inconsistencies


def check_gate_order(gate_status: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    gates = gate_status.get("gates", [])
    if not isinstance(gates, list):
        return ["GATE_STATUS.gates must be an array"]

    seen_non_pass = False
    for position, gate in enumerate(gates):
        if not isinstance(gate, dict):
            issues.append(f"Gate entry {position} must be an object")
            continue
        gate_id = gate.get("id", "")
        status = gate.get("status", "")
        if gate_id not in GATE_ORDER:
            issues.append(f"Unknown gate id: '{gate_id}'")
        if status not in VALID_GATE_STATUSES:
            issues.append(f"Gate {gate_id} has unrecognized status: '{status}'")

        is_pass = status == "PASS"
        if seen_non_pass and is_pass:
            issues.append(
                f"Gate {gate_id} is PASS after an earlier gate is incomplete"
            )
        if not is_pass:
            seen_non_pass = True

    ids = [gate.get("id") for gate in gates if isinstance(gate, dict)]
    known_ids = [gate_id for gate_id in ids if gate_id in GATE_ORDER]
    if known_ids != sorted(known_ids, key=GATE_ORDER.get):
        issues.append("Gate entries are not ordered G0 through G10")
    return issues


def check_git_consistency(
    gate_status: dict[str, Any],
    program_state: dict[str, Any],
) -> list[str]:
    del gate_status  # kept for stable public function signature
    issues: list[str] = []
    try:
        current_sha = git_head_sha()
        current_branch = git_branch()
    except RuntimeError as exc:
        return [f"Cannot read git state: {exc}"]

    # Skip branch check only on pull_request CI events (detached merge ref).
    # Push-to-main and local runs MUST still validate branch consistency.
    in_pr_ci = (
        os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
        and os.environ.get("GITHUB_EVENT_NAME", "") == "pull_request"
    )
    recorded_branch = program_state.get("branch", "")
    if recorded_branch and recorded_branch != current_branch and not in_pr_ci:
        issues.append(
            f"Branch mismatch: PROGRAM_STATE says '{recorded_branch}', "
            f"git says '{current_branch}'"
        )

    if BASELINE_PATH.exists():
        try:
            baseline = load_json(BASELINE_PATH)
            # Validate new commit fields (post-baseline schema)
            commit_fields = (
                "product_source_commit",
                "baseline_declaration_commit",
                "governance_validation_commit",
                "remote_main_commit",
            )
            for field in commit_fields:
                value = baseline.get(field, "")
                if not value:
                    issues.append(f"BASELINE.{field} is missing or empty")
                elif not (isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())):
                    issues.append(f"BASELINE.{field} is not a valid 40-char SHA: '{str(value)[:20]}'")
            # Legacy head fallback — only if new fields absent
            if not any(baseline.get(f) for f in commit_fields):
                baseline_head = baseline.get("head", "")
                if baseline_head and baseline_head != current_sha:
                    issues.append(
                        f"Baseline HEAD ({str(baseline_head)[:12]}) differs from "
                        f"current HEAD ({current_sha[:12]}) — baseline may be stale"
                    )
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"Could not read BASELINE.json: {exc}")

    try:
        if not git_worktree_is_clean():
            issues.append(
                "Working tree has uncommitted changes — commit or stash before continuing"
            )
    except RuntimeError as exc:
        issues.append(f"Cannot inspect worktree: {exc}")
    return issues


def check_test_baseline_consistency(
    gate_status: dict[str, Any],
    program_state: dict[str, Any],
) -> list[str]:
    gs_tests = gate_status.get("test_baseline", "")
    ps_tests = program_state.get("test_baseline", "")
    if gs_tests and ps_tests and gs_tests != ps_tests:
        return [
            f"Test baseline mismatch: GATE_STATUS says '{gs_tests}', "
            f"PROGRAM_STATE says '{ps_tests}'"
        ]
    return []


def check_artifact_consistency(gate_status: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    artifacts = gate_status.get("release_artifacts_tracked", [])
    if artifacts is None:
        return issues
    if not isinstance(artifacts, list):
        return ["GATE_STATUS.release_artifacts_tracked must be an array"]
    for relative_path in artifacts:
        if not isinstance(relative_path, str) or not relative_path:
            issues.append("Release artifact path must be a non-empty string")
            continue
        if not (REPO_ROOT / relative_path).exists():
            issues.append(f"Tracked artifact not found: {relative_path}")
    return issues


def report_drift(inconsistencies: list[str]) -> None:
    print("=" * 60)
    print("  NEXARA PRIME — State Drift Detection Report")
    print("=" * 60)
    print()
    try:
        print(f"  Git HEAD:    {git_head_sha()[:12]}")
        print(f"  Branch:      {git_branch()}")
    except RuntimeError:
        pass
    print()

    if not inconsistencies:
        print("  RESULT: NO DRIFT DETECTED")
        print("  State files are mutually consistent with repository reality.")
        print()
        return

    print(f"  RESULT: DRIFT DETECTED ({len(inconsistencies)} issue(s))")
    print()
    for index, issue in enumerate(inconsistencies, 1):
        print(f"  {index}. {issue}")
    print()


def main() -> int:
    try:
        gate_status = load_json(GATE_STATUS_PATH)
        program_state = load_json(PROGRAM_STATE_PATH)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    issues: list[str] = []
    issues.extend(check_consistency(gate_status, program_state))
    issues.extend(check_gate_order(gate_status))
    issues.extend(check_git_consistency(gate_status, program_state))
    issues.extend(check_test_baseline_consistency(gate_status, program_state))
    issues.extend(check_artifact_consistency(gate_status))

    report_drift(issues)
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
