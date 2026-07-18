#!/usr/bin/env bash
set -euo pipefail
# NEXARA CI Authority — Python check (mirrors ci.yml python job)
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
echo "[check_python] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[check_python] python3: $(python3 --version 2>&1)"
rc=0
echo "[check_python] pytest..." && python3 -m pytest tests/ -q || rc=$?
echo "[check_python] ruff (full src+tests)..." && python3 -m ruff check src tests || rc=$?
echo "[check_python] compileall..." && python3 -m compileall -q src/nexara_prime || rc=$?
echo "[check_python] exit=$rc"
exit $rc
