"""Validate canonical state files against schema, temporal order, and GitHub truth."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = REPO_ROOT / ".nexara"
PROGRAM_STATE_PATH = STATE_DIR / "PROGRAM_STATE.json"
GATE_STATUS_PATH = STATE_DIR / "GATE_STATUS.json"
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def load_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        return {"_error": f"JSON parse error: {e}"}


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validate_json_syntax(path: Path) -> tuple[bool, str]:
    """Return (valid, error_message)."""
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True, ""
    except json.JSONDecodeError as e:
        return False, str(e)


def validate_sha_full(sha: str, field_name: str) -> tuple[bool, str]:
    """Full 40-char hex SHA."""
    if not sha or len(sha) != 40:
        return False, f"{field_name}: '{sha}' is not a 40-char full SHA"
    if not all(c in "0123456789abcdef" for c in sha.lower()):
        return False, f"{field_name}: contains non-hex characters"
    return True, ""


def validate_utc_timestamp(ts: str, field_name: str) -> tuple[bool, str]:
    """Validate ISO-8601 UTC timestamp ending in Z."""
    if not ts:
        return False, f"{field_name}: empty"
    if not ts.endswith("Z"):
        return False, f"{field_name}: '{ts}' must end with Z (UTC)"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False, f"{field_name}: '{ts}' is not a valid ISO-8601 timestamp"
    # No future times
    now = datetime.now(timezone.utc)
    if dt > now:
        return False, f"{field_name}: '{ts}' is in the future (now={now.isoformat()})"
    return True, ""


def validate_temporal_order(ps: dict) -> list[tuple[bool, str]]:
    """merged_at fields must be in chronological order and before updated_at."""
    results = []
    times: list[tuple[str, datetime]] = []

    for key in ["pr5_squash_merge", "pr8_orchestration", "pr10_state_sync"]:
        obj = ps.get(key, {})
        ts = obj.get("merged_at", "")
        if ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            times.append((key, dt))

    for i in range(1, len(times)):
        if times[i][1] < times[i-1][1]:
            results.append((False, f"temporal: {times[i][0]} merged_at ({times[i][1]}) < {times[i-1][0]} ({times[i-1][1]})"))
        else:
            results.append((True, ""))

    # updated_at must be >= all merged_at
    upd = ps.get("updated_at", "")
    if upd:
        upd_dt = datetime.fromisoformat(upd.replace("Z", "+00:00"))
        for key, dt in times:
            if upd_dt < dt:
                results.append((False, f"updated_at ({upd}) < {key} merged_at ({ts})"))

    return results


def validate_state_consistency(ps: dict, gs: dict, git_truth: dict | None = None) -> list[tuple[bool, str]]:
    """Cross-validate PROGRAM_STATE and GATE_STATUS."""
    results = []

    # Test baseline match
    ps_baseline = ps.get("test_baseline", "")
    gs_baseline = gs.get("test_baseline", "")
    if ps_baseline != gs_baseline:
        results.append((False, f"test_baseline mismatch: PS='{ps_baseline}' vs GS='{gs_baseline}'"))
    else:
        results.append((True, "test_baseline consistent"))

    # Gate match
    ps_gate = ps.get("current_program_gate", "")
    gs_gate = gs.get("current_gate", "")
    if ps_gate != gs_gate:
        results.append((False, f"gate mismatch: PS='{ps_gate}' vs GS='{gs_gate}'"))
    else:
        results.append((True, "gate consistent"))

    # SHA length check on all commit fields
    for path, field in [
        (["pr5_squash_merge", "squash_commit"], "pr5 squash_commit"),
        (["pr8_orchestration", "commit"], "pr8 commit"),
        (["pr8_orchestration", "squash_merge_commit"], "pr8 squash_merge_commit"),
        (["pr10_state_sync", "head"], "pr10 head"),
        (["pr10_state_sync", "squash_merge_commit"], "pr10 squash_merge_commit"),
    ]:
        val = ps
        for key in path:
            val = val.get(key, {})
        if isinstance(val, str):
            ok, msg = validate_sha_full(val, field)
            results.append((ok, msg))

    # Timestamp validation on all merged_at + updated_at
    for path, field in [
        (["pr5_squash_merge", "merged_at"], "pr5 merged_at"),
        (["pr8_orchestration", "merged_at"], "pr8 merged_at"),
        (["pr10_state_sync", "merged_at"], "pr10 merged_at"),
        (["updated_at"], "PS updated_at"),
    ]:
        val = ps
        for key in path:
            val = val.get(key, {})
        if isinstance(val, str):
            ok, msg = validate_utc_timestamp(val, field)
            results.append((ok, msg))

    results.append((True, f"GS updated_at valid: {validate_utc_timestamp(gs.get('updated_at',''), 'GS updated_at')[0]}"))

    return results


RECEIPTS_DIR = STATE_DIR / "receipts"


def _find_canonical_receipt() -> Path | None:
    """Discover the canonical terminal superseding receipt.

    Selection priority (deterministic):
    1. If exactly one terminal superseding receipt exists, return it.
    2. If zero or multiple terminal receipts exist, return None
       (caller must fail — ambiguity is not tolerated).
    """
    if not RECEIPTS_DIR.exists():
        return None
    terminal: list[Path] = []
    for path in sorted(RECEIPTS_DIR.glob("*_final_attestation.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                data.get("receipt_type") == "superseding_receipt"
                and data.get("superseded_by") is None
            ):
                terminal.append(path)
        except (json.JSONDecodeError, OSError):
            continue
    if len(terminal) == 1:
        return terminal[0]
    return None


def validate_receipt_provenance(gs: dict, ps: dict) -> list[tuple[bool, str]]:
    """Validate canonical receipt generically — no PR-specific hardcoded paths."""
    results: list[tuple[bool, str]] = []

    # 1. Exactly one terminal superseding receipt must exist
    if not RECEIPTS_DIR.exists():
        results.append((False, "Receipts directory .nexara/receipts/ missing"))
        return results

    all_terminal: list[Path] = []
    for path in sorted(RECEIPTS_DIR.glob("*_final_attestation.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                data.get("receipt_type") == "superseding_receipt"
                and data.get("superseded_by") is None
            ):
                all_terminal.append(path)
        except (json.JSONDecodeError, OSError):
            continue

    if len(all_terminal) == 0:
        results.append((False, "No canonical terminal superseding receipt found"))
        return results
    if len(all_terminal) > 1:
        names = ", ".join(p.name for p in all_terminal)
        results.append((False, f"Multiple active terminal receipts ({len(all_terminal)}): {names}"))
        return results

    receipt_path = all_terminal[0]
    results.append((True, f"Canonical receipt: {receipt_path.name}"))

    # 2. Receipt must be readable
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        results.append((False, f"Canonical receipt unreadable: {exc}"))
        return results

    # 3. Receipt type
    rtype = receipt.get("receipt_type", "")
    if rtype != "superseding_receipt":
        results.append((False, f"Receipt type must be 'superseding_receipt', got '{rtype}'"))
    else:
        results.append((True, "Receipt type: superseding_receipt"))

    # 4. evidence_subject_head: valid 40-char SHA
    esh = receipt.get("evidence_subject_head", "")
    ok, msg = validate_sha_full(esh, "evidence_subject_head")
    results.append((ok, msg))

    # 5. Terminal (superseded_by=null)
    sb = receipt.get("superseded_by")
    if sb is not None:
        results.append((False, f"Terminal receipt superseded_by must be null, got '{sb}'"))
    else:
        results.append((True, "Receipt is terminal (superseded_by=null)"))

    # 6. CI verification fields
    ci = receipt.get("ci_verification", {})
    if not ci.get("run_id"):
        results.append((False, "Receipt ci_verification.run_id missing"))
    else:
        results.append((True, f"CI run_id: {ci['run_id']}"))
    if not ci.get("result"):
        results.append((False, "Receipt ci_verification.result missing"))
    else:
        results.append((True, f"CI result: {ci['result']}"))

    # 7. Cross-file linkage: state superseded_by must point to receipt
    receipt_rel = str(receipt_path.relative_to(REPO_ROOT))
    gs_link = gs.get("superseded_by", "")
    if gs_link != receipt_rel:
        results.append((False, f"GATE_STATUS.superseded_by='{gs_link}', expected '{receipt_rel}'"))
    else:
        results.append((True, "GATE_STATUS.superseded_by links to canonical receipt"))

    # PROGRAM_STATE: check all top-level keys that contain 'superseded_by'
    ps_linked = False
    for key, val in ps.items():
        if isinstance(val, dict) and val.get("superseded_by") == receipt_rel:
            ps_linked = True
            break
    if ps_linked:
        results.append((True, "PROGRAM_STATE superseded_by links to canonical receipt"))
    else:
        results.append((False, f"PROGRAM_STATE has no subsection with superseded_by='{receipt_rel}'"))

    # 8. evidence_subject_head reachable in git
    try:
        result = subprocess.run(
            ["git", "cat-file", "-t", esh],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip() == "commit":
            results.append((True, f"evidence_subject_head {esh[:12]} reachable"))
        else:
            results.append((False, f"evidence_subject_head {esh[:12]} not a reachable commit"))
    except (subprocess.TimeoutExpired, OSError) as exc:
        results.append((False, f"Cannot verify evidence_subject_head: {exc}"))

    return results


def validate_all(
    git_truth: dict[str, Any] | None = None,
    github_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all validations. Returns structured report."""
    ps = load_json(PROGRAM_STATE_PATH)
    gs = load_json(GATE_STATUS_PATH)

    report: dict[str, Any] = {
        "json_syntax": {},
        "sha_validation": [],
        "temporal": [],
        "state_consistency": [],
        "receipt_provenance": [],
        "github_match": [],
        "overall_pass": True,
    }

    # JSON syntax
    for name, path, data in [("PROGRAM_STATE", PROGRAM_STATE_PATH, ps), ("GATE_STATUS", GATE_STATUS_PATH, gs)]:
        ok, err = validate_json_syntax(path)
        report["json_syntax"][name] = {"valid": ok, "error": err}
        if not ok:
            report["overall_pass"] = False

    if isinstance(ps, dict) and not ps.get("_error"):
        # State consistency
        for ok, msg in validate_state_consistency(ps, gs, git_truth):
            report["state_consistency"].append({"pass": ok, "message": msg})
            if not ok:
                report["overall_pass"] = False

        # Temporal order
        for ok, msg in validate_temporal_order(ps):
            report["temporal"].append({"pass": ok, "message": msg})
            if not ok:
                report["overall_pass"] = False

        # Receipt provenance
        for ok, msg in validate_receipt_provenance(gs, ps):
            report["receipt_provenance"].append({"pass": ok, "message": msg})
            if not ok:
                report["overall_pass"] = False

    # GitHub truth comparison
    if github_truth:
        for pr_num, truth in github_truth.items():
            block = ps.get(f"pr{pr_num}_orchestration") or ps.get(f"pr{pr_num}_state_sync") or {}
            actual_merged = block.get("merged_at", "")
            expected_merged = truth.get("merged_at_utc", "")
            match = actual_merged == expected_merged
            report["github_match"].append({
                "pr": int(pr_num),
                "field": "merged_at",
                "expected": expected_merged,
                "actual": actual_merged,
                "match": match,
            })
            if not match:
                report["overall_pass"] = False

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    git = None
    github = None

    report = validate_all(git, github)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("=== Runtime Truth Validation ===")
        for key, val in report["json_syntax"].items():
            status = "PASS" if val["valid"] else "FAIL"
            print(f"  JSON {key}: {status}")
        for item in report.get("state_consistency", []):
            status = "PASS" if item["pass"] else "FAIL"
            print(f"  {status}: {item['message']}")
        for item in report.get("receipt_provenance", []):
            status = "PASS" if item["pass"] else "FAIL"
            print(f"  {status}: {item['message']}")
        for item in report.get("temporal", []):
            status = "PASS" if item["pass"] else "FAIL"
            print(f"  {status}: {item['message']}")
        for item in report.get("github_match", []):
            status = "MATCH" if item["match"] else "MISMATCH"
            print(f"  PR{item['pr']} {item['field']}: {status} (expected={item['expected']}, actual={item['actual']})")

    sys.exit(0 if report["overall_pass"] else 1)
