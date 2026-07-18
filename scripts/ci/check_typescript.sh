#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TS_DIR="$REPO_ROOT/platform/sdk/typescript"
echo "[check_typescript] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ ! -f "$TS_DIR/package-lock.json" ]; then
  echo "[check_typescript] NOT_APPLICABLE: no package-lock.json"
  exit 0
fi
cd "$TS_DIR"
echo "[check_typescript] node: $(node --version 2>&1)"
echo "[check_typescript] npm: $(npm --version 2>&1)"
rc=0
echo "[check_typescript] npm ci..." && npm ci || rc=$?
echo "[check_typescript] tsc --noEmit..." && npx tsc --noEmit || rc=$?
echo "[check_typescript] exit=$rc"
exit $rc
