#!/usr/bin/env python3
"""Coverage ratchet: fail when coverage drops below the recorded baseline.

    python3 scripts/quality/coverage_gate.py            # measure and compare
    python3 scripts/quality/coverage_gate.py --update   # accept current number

Baseline lives in `.coverage-baseline.json` and may only move up.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / ".coverage-baseline.json"
TARGETS = ["tests/test_t1_deterministic_report.py", "tests/test_t2_sandbox_selection.py",
           "tests/test_t3_api_auth.py", "tests/test_t4_wal_concurrency.py",
           "tests/test_t5_gate_single_source.py", "tests/test_t6_idempotency.py",
           "tests/test_t7_rollback_scope.py", "tests/test_t8_ui_route_truth.py"]


def measure() -> float:
    run = subprocess.run([sys.executable, "-m", "coverage", "run",
                          "--source=src/nexara_prime", "-m", "pytest", "-q", *TARGETS,
                          "-p", "no:cacheprovider"], cwd=ROOT, check=False)
    if run.returncode != 0:
        raise SystemExit("tests failed during coverage run")
    report = subprocess.run([sys.executable, "-m", "coverage", "report", "--format=total"],
                            cwd=ROOT, capture_output=True, text=True, check=False)
    try:
        return float((report.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"cannot parse coverage: {report.stdout!r}") from exc


def main() -> int:
    value = measure()
    if "--update" in sys.argv or not BASELINE.exists():
        BASELINE.write_text(json.dumps({"minimum": round(value, 2)}) + "\n")
        print(f"coverage baseline set: {value:.2f}%")
        return 0
    minimum = float(json.loads(BASELINE.read_text())["minimum"])
    print(f"coverage {value:.2f}% (minimum {minimum:.2f}%)")
    if value + 0.01 < minimum:
        print("COVERAGE GATE: FAIL")
        return 1
    print("COVERAGE GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
