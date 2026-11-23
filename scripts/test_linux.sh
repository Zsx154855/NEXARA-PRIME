#!/usr/bin/env bash
# Reproducible test entry point for Linux/macOS.
#
#   ./scripts/test_linux.sh            # fast subset (≈1 min)
#   ./scripts/test_linux.sh --full     # whole suite (≈14 min on this host)
#   ./scripts/test_linux.sh --one tests/test_t3_api_auth.py
#
# Exit code 0 only if every selected test passed. Environment failures are not
# silently waived: they are listed by name in the output.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# two roots are required: the package and the SDK copy used by contract tests
export PYTHONPATH="$ROOT/src:$ROOT/platform/sdk/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

PYTHON_BIN="${NEXARA_PYTHON:-python3}"
FAST_TESTS=(
  tests/test_t1_deterministic_report.py
  tests/test_t2_sandbox_selection.py
  tests/test_t3_api_auth.py
  tests/test_t4_wal_concurrency.py
  tests/test_t5_gate_single_source.py
  tests/test_t6_idempotency.py
  tests/test_t7_rollback_scope.py
  tests/test_t8_ui_route_truth.py
  tests/test_conversations_api.py
  tests/test_evaluation.py
  tests/test_runtime_v2_stage_recovery.py
)

case "${1:-}" in
  --full)
    shift
    exec "$PYTHON_BIN" -m pytest -q tests -p no:cacheprovider "$@"
    ;;
  --one)
    shift
    exec "$PYTHON_BIN" -m pytest -q "$@" -p no:cacheprovider
    ;;
  *)
    exec "$PYTHON_BIN" -m pytest -q "${FAST_TESTS[@]}" -p no:cacheprovider "$@"
    ;;
esac
