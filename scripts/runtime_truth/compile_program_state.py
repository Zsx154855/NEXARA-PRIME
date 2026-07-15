"""Canonical PROGRAM_STATE.json compiler.

Reads collected truth and existing state, produces a validated
canonical PROGRAM_STATE.json. Never inserts hand-written values.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = REPO_ROOT / ".nexara"
PROGRAM_STATE_PATH = STATE_DIR / "PROGRAM_STATE.json"
GATE_STATUS_PATH = STATE_DIR / "GATE_STATUS.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    """Atomically write content to path via tmp file + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def load_existing_state() -> dict[str, Any]:
    """Load the existing PROGRAM_STATE.json as a base to preserve non-volatile fields."""
    if PROGRAM_STATE_PATH.exists():
        return json.loads(PROGRAM_STATE_PATH.read_text(encoding="utf-8"))
    return {}


def compile_program_state(
    git_truth: dict[str, Any],
    github_truth: dict[str, Any],
    test_truth: dict[str, Any],
    *,
    previous_state: dict[str, Any] | None = None,
    compiler_version: str = "1.0.0",
) -> dict[str, Any]:
    """Compile canonical PROGRAM_STATE.json from collected truth."""
    if previous_state is None:
        previous_state = load_existing_state()

    now = _utc_now()
    base = dict(previous_state)  # Preserve user-maintained fields

    # ── Volatile fields — ALWAYS from collectors ──
    base["branch"] = git_truth["branch"]
    base["test_baseline"] = test_truth["full_suite"]["baseline_string"]

    # ── PR #8 truth ──
    pr8 = github_truth.get("8", {})
    if pr8:
        pr8_block = base.setdefault("pr8_orchestration", {})
        if pr8.get("merged_at_utc"):
            pr8_block["merged_at"] = pr8["merged_at_utc"]
        if pr8.get("merge_commit"):
            pr8_block["squash_merge_commit"] = pr8["merge_commit"]
        if pr8.get("head_sha"):
            pr8_block["commit"] = pr8["head_sha"]
        pr8_block["status"] = pr8.get("state", pr8_block.get("status", "MERGED"))

    # ── PR #10 truth ──
    pr10 = github_truth.get("10", {})
    if pr10:
        pr10_block = base.setdefault("pr10_state_sync", {})
        if pr10.get("merged_at_utc"):
            pr10_block["merged_at"] = pr10["merged_at_utc"]
        if pr10.get("head_sha"):
            pr10_block["head"] = pr10["head_sha"]
        pr10_block["status"] = pr10.get("state", pr10_block.get("status", "MERGED"))

    # ── Timestamp ──
    base["updated_at"] = now
    base["updated_by"] = f"Runtime Truth Compiler v{compiler_version}"

    return base


def compile_gate_status(
    test_truth: dict[str, Any],
    *,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile canonical GATE_STATUS.json."""
    if previous_state is None:
        if GATE_STATUS_PATH.exists():
            previous_state = json.loads(GATE_STATUS_PATH.read_text(encoding="utf-8"))
        else:
            previous_state = {}

    now = _utc_now()
    base = dict(previous_state)

    base["test_baseline"] = test_truth["full_suite"]["baseline_string"]
    base["updated_at"] = now

    return base


def compile_and_write(
    git_truth: dict[str, Any],
    github_truth: dict[str, Any],
    test_truth: dict[str, Any],
) -> dict[str, Any]:
    """Compile and atomically write both state files. Returns compilation metadata."""
    # Load existing
    prev_ps = json.loads(PROGRAM_STATE_PATH.read_text("utf-8")) if PROGRAM_STATE_PATH.exists() else {}
    prev_gs = json.loads(GATE_STATUS_PATH.read_text("utf-8")) if GATE_STATUS_PATH.exists() else {}

    # Compute input hash
    input_data = json.dumps({
        "git": git_truth,
        "github": github_truth,
        "test": test_truth,
    }, sort_keys=True, default=str)
    input_hash = hashlib.sha256(input_data.encode()).hexdigest()

    # Compile
    new_ps = compile_program_state(git_truth, github_truth, test_truth, previous_state=prev_ps)
    new_gs = compile_gate_status(test_truth, previous_state=prev_gs)

    # Serialize
    ps_json = json.dumps(new_ps, indent=2, ensure_ascii=False) + "\n"
    gs_json = json.dumps(new_gs, indent=2, ensure_ascii=False) + "\n"

    # Validate JSON syntax
    json.loads(ps_json)
    json.loads(gs_json)

    # Compute output hash
    output_data = json.dumps({"ps": ps_json, "gs": gs_json}, sort_keys=True)
    output_hash = hashlib.sha256(output_data.encode()).hexdigest()

    # Atomic write
    _atomic_write(PROGRAM_STATE_PATH, ps_json)
    _atomic_write(GATE_STATUS_PATH, gs_json)

    return {
        "input_hash": input_hash,
        "output_hash": output_hash,
        "compiler_version": "1.0.0",
        "compiled_at": _utc_now(),
    }


if __name__ == "__main__":
    from collect_git_truth import collect_git_truth
    from collect_test_truth import run_full_suite, run_orchestration_tests
    from collect_github_truth import collect_all_pr_truth

    git = collect_git_truth()
    github = collect_all_pr_truth([8, 10])
    tests = {
        "orchestration": run_orchestration_tests(),
        "full_suite": run_full_suite(),
    }

    meta = compile_and_write(git, github, tests)
    print(json.dumps(meta, indent=2))
    print("PROGRAM_STATE.json and GATE_STATUS.json compiled successfully.")
