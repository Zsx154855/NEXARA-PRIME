"""Collect test truth from pytest — never hand-write test numbers."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def run_pytest(test_path: str = "tests/") -> dict:
    """Run pytest and return structured results.

    Returns:
        {passed, failed, subtests, total, baseline_string}
    """
    result = subprocess.run(
        [str(VENV_PYTHON), "-m", "pytest", test_path, "-q"],
        capture_output=True, text=True, timeout=120,
        cwd=str(REPO_ROOT),
    )
    output = result.stdout + result.stderr

    passed = 0
    failed = 0
    subtests_passed = 0

    for line in output.splitlines():
        if "passed" in line and "subtests" in line:
            import re
            m = re.search(r'(\d+)\s+passed.*?(\d+)\s+subtests\s+passed', line)
            if m:
                passed = int(m.group(1))
                subtests_passed = int(m.group(2))
        elif "passed" in line and "failed" in line:
            import re
            m = re.search(r'(\d+)\s+passed.*?(\d+)\s+failed', line)
            if m:
                passed = int(m.group(1))
                failed = int(m.group(2))

    baseline = f"{passed} passed, 0 failed"
    if subtests_passed:
        baseline += f", {subtests_passed} subtests passed"

    return {
        "passed": passed,
        "failed": failed,
        "subtests_passed": subtests_passed,
        "total": passed + failed,
        "baseline_string": baseline,
        "exit_code": result.returncode,
    }


def run_orchestration_tests() -> dict:
    """Run orchestration-specific tests."""
    return run_pytest("tests/test_orchestration.py")


def run_full_suite() -> dict:
    """Run the full test suite."""
    return run_pytest("tests/")


if __name__ == "__main__":
    results = {
        "orchestration": run_orchestration_tests(),
        "full_suite": run_full_suite(),
    }
    json.dump(results, sys.stdout, indent=2)
