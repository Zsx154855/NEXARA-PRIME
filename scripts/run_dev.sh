#!/usr/bin/env bash
# NEXARA dev runtime entrypoint.
# Contract: explicit .env loading so NEXARA_MOCK_MODEL / provider settings
# are deterministic from the standard entrypoint (no hidden shell deps).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src"

# Load .env if present (dev mode config: NEXARA_MOCK_MODEL etc).
# set -a exports every assignment; set +a restores.
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PYTHON_BIN="${NEXARA_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="python3.12"; fi
exec "$PYTHON_BIN" -m uvicorn nexara_prime.api:app --host "${NEXARA_API_HOST:-127.0.0.1}" --port "${NEXARA_API_PORT:-8765}" --reload
