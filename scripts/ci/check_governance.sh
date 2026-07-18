#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
echo "[check_governance] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 scripts/governance/detect_state_drift.py
echo "[check_governance] exit=$?"
