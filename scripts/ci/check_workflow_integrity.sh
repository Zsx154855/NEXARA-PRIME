#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
echo "[workflow_integrity] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
rc=0
python3 -c "import yaml; [yaml.safe_load(open(f'$REPO_ROOT/.github/workflows/{w}')) for w in ['ci.yml','self-hosted-probe.yml']]" || rc=$?
git diff --check || rc=$?
echo "[workflow_integrity] exit=$rc"
exit $rc
