#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IOS_DIR="$REPO_ROOT/experience/ios"
echo "[check_swift_ios] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ ! -d "$IOS_DIR" ]; then
  echo "[check_swift_ios] NOT_APPLICABLE: no experience/ios directory"
  exit 0
fi
cd "$IOS_DIR"
HAS_XCODEPROJ=$(ls *.xcodeproj 2>/dev/null | head -1 || echo "")
if [ -n "$HAS_XCODEPROJ" ]; then
  SCHEME=$(echo "$HAS_XCODEPROJ" | sed 's/.xcodeproj//')
  echo "[check_swift_ios] Building with xcodebuild scheme=$SCHEME"
  xcodebuild -scheme "$SCHEME" -sdk iphonesimulator \
    -destination 'platform=iOS Simulator,name=iPhone 16' \
    CODE_SIGNING_ALLOWED=NO build 2>&1 || {
      echo "[check_swift_ios] xcodebuild failed (may need scheme configuration)"
      exit 1
    }
else
  echo "[check_swift_ios] NOT_APPLICABLE_WITH_EVIDENCE: SPM-only (no .xcodeproj)"
  echo "[check_swift_ios] xcodebuild CI cannot run without .xcodeproj"
fi
echo "[check_swift_ios] exit=0"
