#!/usr/bin/env bash
# Restart the NEXARA runtime: graceful stop → production start.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT/scripts/stop.sh"
sleep 2
exec "$ROOT/scripts/run_prod.sh"
