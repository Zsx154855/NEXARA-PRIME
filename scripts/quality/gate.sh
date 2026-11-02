#!/usr/bin/env bash
# Local quality gate. Mirrors .github/workflows/takeover-linux.yml.
#   bash scripts/quality/gate.sh            # changed files vs origin/main
#   bash scripts/quality/gate.sh --all      # all python files
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT/platform/sdk/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
PY="${NEXARA_PYTHON:-python3}"
FAILED=0

step() { printf "\n== %s ==\n" "$1"; }
check() { if [ "$1" -ne 0 ]; then echo "GATE FAILED: $2"; FAILED=1; else echo "ok: $2"; fi; }

step "compile"
$PY -m compileall -q src >/dev/null 2>&1; check $? "compileall"

step "lint (changed files)"
if [ "${1:-}" = "--all" ]; then
  FILES=$(git ls-files '*.py')
else
  FILES=$(git diff --name-only origin/main...HEAD -- '*.py' 2>/dev/null || git ls-files '*.py')
fi
if [ -n "$FILES" ]; then
  # Ratchet: new code follows the full rule set; legacy files we touch only have
  # to stay correct (E9/F63/F7/F82), so this gate cannot be "fixed" by reformatting
  # unrelated code.
  NEW=$(printf "%s\n" $FILES | grep -E 'provenance_engine|tests/test_t|scripts/' || true)
  LEGACY=$(printf "%s\n" $FILES | grep -Ev 'provenance_engine|tests/test_t|scripts/' || true)
  [ -z "$NEW" ] || { ruff check $NEW; check $? "ruff (new code)"; }
  [ -z "$LEGACY" ] || { ruff check --select E9,F63,F7,F82 $LEGACY; check $? "ruff (legacy correctness)"; }
else
  echo "no python changes"
fi

step "tests (fast)"
bash scripts/test_linux.sh >/tmp/gate-tests.log 2>&1; rc=$?
tail -2 /tmp/gate-tests.log
check $rc "pytest fast"

step "e2e (real http)"
$PY scripts/e2e/http_smoke.py >/tmp/gate-e2e.log 2>&1; rc=$?
tail -3 /tmp/gate-e2e.log
check $rc "http e2e"

step "ui route truth"
$PY scripts/ui/route_truth.py >/dev/null; check $? "route_truth"

step "gate status (committed == derived)"
$PY scripts/governance/derive_gate_status.py --check >/tmp/gate-derived.log 2>&1; rc=$?
tail -2 /tmp/gate-derived.log
check $rc "derive_gate_status --check"

step "state drift (clean tree only)"
if [ -z "$(git status --porcelain)" ]; then
  $PY scripts/governance/detect_state_drift.py >/tmp/gate-drift.log 2>&1; rc=$?
  tail -2 /tmp/gate-drift.log
  check $rc "state drift"
else
  echo "skipped: working tree dirty (CI runs this on the committed state)"
fi

step "secret scan"
if [ -f scripts/quality/secret_scan_gate.py ]; then
  $PY scripts/quality/secret_scan_gate.py >/tmp/gate-secrets.log 2>&1; rc=$?
  tail -3 /tmp/gate-secrets.log
  check $rc "secret scan (ratchet)"
else
  echo "scanner missing — gate not run"; FAILED=1
fi

printf "\n"
if [ "$FAILED" -ne 0 ]; then echo "QUALITY GATE: FAIL"; exit 1; fi
echo "QUALITY GATE: PASS"
