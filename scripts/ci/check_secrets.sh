#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
echo "[check_secrets] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 scripts/security/scan_hardcoded_secrets.py
echo "[check_secrets] exit=$?"
