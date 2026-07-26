#!/usr/bin/env python3
"""Validate completion receipt V1.2 — no self-reference, binds stable evidence_subject_head."""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
from typing import Any

READY = {"READY_FOR_CODEX_REVIEW","READY_FOR_HUMAN_APPROVAL"}
ALLOWED = READY | {"BLOCKED","WAITING_APPROVAL","BLOCKED_EXTERNAL_ONLY"}
SHA = re.compile(r"^[0-9a-f]{40}$")

def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr); raise SystemExit(1)

def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    if r.returncode != 0: fail(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()

def req(d: dict[str, Any], key: str) -> Any:
    if key not in d: fail(f"missing key: {key}")
    return d[key]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt", type=Path)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    args = ap.parse_args()
    repo = args.repo.resolve()
    if not args.receipt.exists(): fail(f"missing receipt: {args.receipt}")
    data = json.loads(args.receipt.read_text(encoding="utf-8"))

    # Schema version
    sv = req(data,"schema_version")
    if sv not in {"1.1","1.2"}: fail(f"schema_version must be 1.1 or 1.2, got {sv}")

    result = req(data,"final_result")
    if result not in ALLOWED: fail(f"invalid final_result: {result}")

    # Base SHA validation
    base = req(data,"base_sha")
    if not isinstance(base,str) or not SHA.fullmatch(base): fail("base_sha must be 40-char lowercase SHA")

    # evidence_subject_head: the stable code commit being verified
    esh = req(data,"evidence_subject_head")
    if not isinstance(esh,str) or not SHA.fullmatch(esh): fail("evidence_subject_head must be 40-char lowercase SHA")
    # Must be reachable in git
    try:
        obj_type = git(repo, "cat-file", "-t", esh).strip()
        if obj_type != "commit": fail(f"evidence_subject_head {esh[:12]} is not a commit object")
    except SystemExit:
        raise
    except Exception:
        fail(f"evidence_subject_head {esh[:12]} not reachable in git")

    # receipt_commit_head may be null (receipt hasn't been committed yet) or a valid SHA
    rch = data.get("receipt_commit_head")
    if rch is not None:
        if not isinstance(rch,str) or not SHA.fullmatch(rch): fail("receipt_commit_head must be null or 40-char lowercase SHA")

    # Council
    council = req(data,"council")
    mode = council.get("mode","")
    if mode not in {"subagents","role_passes","delegated"}: fail("invalid council mode")
    if mode in {"subagents","role_passes"}:
        if council.get("premortem_members_completed") != 18: fail("premortem_members_completed != 18")
        if council.get("final_members_completed") != 18: fail("final_members_completed != 18")
        if result in READY and council.get("open_vetoes") != 0: fail("Ready requires open_vetoes=0")
    if result in READY and mode == "delegated":
        if council.get("delegated_matrix") is not True: fail("delegated mode requires delegated_matrix=true")
        if council.get("delegated_independent_audit") is not True: fail("delegated mode requires delegated_independent_audit=true")

    # Local checks
    checks = req(data,"local_checks")
    if not isinstance(checks,list) or not checks: fail("local_checks must be non-empty")
    failed = [c.get("command","<unknown>") for c in checks if c.get("exit_code") != 0]
    if result in READY and failed: fail(f"Ready with failed local checks: {failed}")

    # Worktree: clean means no tracked file modifications.
    # The receipt file itself is excluded — it may be dirty from updating head refs.
    status = git(repo, "status", "--porcelain")
    status_lines = [l for l in status.split("\n") if l.strip()]
    # Exclude the receipt file itself from dirty check
    try:
        receipt_rel = str(args.receipt.resolve().relative_to(repo))
    except ValueError:
        receipt_rel = None  # receipt is outside repo (e.g. temp file in tests)
    non_receipt_dirty = status_lines
    if receipt_rel:
        non_receipt_dirty = [l for l in status_lines if receipt_rel not in l]
    if result in READY and non_receipt_dirty:
        fail(f"Ready requires clean worktree (dirty: {non_receipt_dirty})")
    declared_clean = bool(req(data,"worktree_clean"))
    actual_clean = len(non_receipt_dirty) == 0
    if declared_clean != actual_clean:
        fail(f"worktree_clean={declared_clean} but git status shows clean={actual_clean} (excluding receipt)")

    # Remote CI: head_sha must match evidence_subject_head
    ci = req(data,"remote_ci")
    if result in READY:
        ci_head = ci.get("head_sha","")
        if ci_head != esh:
            fail(f"remote_ci.head_sha ({ci_head[:12]}) != evidence_subject_head ({esh[:12]})")
        jobs = ci.get("jobs")
        if not isinstance(jobs,dict) or not jobs: fail("remote_ci.jobs missing")
        bad = [n for n,v in jobs.items() if v != "success"]
        if bad: fail(f"CI jobs not successful: {', '.join(bad)}")

    # Review threads
    threads = req(data,"review_threads")
    if result in READY and threads.get("unresolved_non_outdated") != 0:
        fail("Ready requires unresolved_non_outdated=0")
    expected = threads.get("resolved",0) + threads.get("unresolved",0)
    actual = threads.get("total",0)
    if expected != actual: fail(f"thread counts: resolved+unresolved={expected} != total={actual}")

    # Prohibited actions
    pa = req(data,"prohibited_actions")
    for k in ("merge_performed","tag_performed","deploy_performed"):
        if pa.get(k) is not False: fail(f"{k} must be false")

    if result == "READY_FOR_HUMAN_APPROVAL" and req(data,"human_approval") is not True:
        fail("READY_FOR_HUMAN_APPROVAL requires human_approval=true")

    print(f"PASS: receipt valid (schema={sv}, evidence_head={esh[:12]}, result={result})")

if __name__ == "__main__":
    main()
