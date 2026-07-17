#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NC_DIR="$REPO_ROOT/experience/NexaraCore"
echo "[check_swift_macos] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ ! -f "$NC_DIR/Package.swift" ]; then
  echo "[check_swift_macos] NOT_APPLICABLE: no Package.swift"
  exit 0
fi
cd "$NC_DIR"
echo "[check_swift_macos] swift: $(swift --version 2>&1 | head -1)"
CODE_SIGNING_ALLOWED=NO swift build
echo "[check_swift_macos] exit=0"
