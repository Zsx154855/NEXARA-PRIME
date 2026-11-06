#!/usr/bin/env bash
# Zero-provider-cost PR #53 evidence collector; no network, push or deployment.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)" || exit 2
cd "$ROOT" || exit 2
if [ -n "$(git status --porcelain)" ]; then
  echo "BLOCKED: dirty checkout. Use a clean isolated worktree." >&2
  exit 2
fi
ARTIFACTS="$(mktemp -d /tmp/nexara-pr53.XXXXXXXX)" || exit 2
HEAD_SHA="$(git rev-parse HEAD)"
echo "HEAD=$HEAD_SHA"
echo "ARTIFACTS=$ARTIFACTS"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONPATH="$ROOT/src"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python3 --version > "$ARTIFACTS/python-version.txt" 2>&1
python3 -m pytest --version > "$ARTIFACTS/pytest-version.txt" 2>&1
RESULTS="$ARTIFACTS/exit-codes.tsv"
printf "phase\texit_code\n" > "$RESULTS"
run_phase() {
  name="$1"
  shift
  echo "PHASE=$name"
  "$@" > "$ARTIFACTS/$name.log" 2>&1
  code=$?
  printf "%s\t%s\n" "$name" "$code" >> "$RESULTS"
  tail -n 15 "$ARTIFACTS/$name.log"
  echo "RESULT=$name:$code"
}
run_phase focus python3 -m pytest -q -p no:cacheprovider \
  tests/test_repair_fail_closed.py tests/test_repair_receipt.py \
  tests/test_repair_process_runner.py tests/test_e2e_runtime_closure.py
run_phase full_python python3 -m pytest -q -p no:cacheprovider tests/
if command -v ruff >/dev/null 2>&1; then
  run_phase ruff ruff check src tests platform/sdk/python
else
  printf "ruff\t127\n" >> "$RESULTS"
  echo "NOT_VERIFIED: ruff is not installed" > "$ARTIFACTS/ruff.log"
fi
if [ -f scripts/governance/detect_state_drift.py ]; then
  run_phase state_drift python3 scripts/governance/detect_state_drift.py
fi
if [ -f scripts/security/scan_hardcoded_secrets.py ]; then
  run_phase secret_scan python3 scripts/security/scan_hardcoded_secrets.py
fi
if [ -f scripts/governance/validate_nsec.py ]; then
  run_phase nsec python3 scripts/governance/validate_nsec.py
fi
run_phase diff_check git diff --check
git status --porcelain > "$ARTIFACTS/worktree-after.txt"
python3 - "$ARTIFACTS" "$HEAD_SHA" <<'PY'
import hashlib
import json
import platform
import sys
from pathlib import Path
base, head = Path(sys.argv[1]), sys.argv[2]
checks = {}
for line in (base / "exit-codes.tsv").read_text().splitlines()[1:]:
    phase, code = line.split("\t")
    checks[phase] = {"exit_code": int(code)}
manifest = {
    "repo_head": head,
    "platform": platform.platform(),
    "python": sys.version,
    "checks": checks,
    "logs": {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(base.glob("*.log"))
    },
    "is_macos": platform.system() == "Darwin",
}
(base / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("MANIFEST:", base / "manifest.json")
PY
if awk -F '\t' 'NR>1 && $2!=0 {bad=1} END {exit !bad}' "$RESULTS"; then
  echo "PARTIAL/FAIL: nonzero check results in $RESULTS"
  exit 1
fi
echo "PASS: all invoked checks returned 0; see $ARTIFACTS/manifest.json"
