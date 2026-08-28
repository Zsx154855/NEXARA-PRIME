#!/usr/bin/env bash
# NEXARA pool gateway entrypoint: exposes ProviderPool (anonymous free-tier
# channels) as an OpenAI-compatible service for LiteLLM / other tools.
# Usage: bash scripts/start_pool_gateway.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src"

# Explicit .env loading (same contract as run_dev.sh).
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PORT="${NEXARA_POOL_GATEWAY_PORT:-4001}"
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "pool gateway already running on :$PORT"
  exit 0
fi

PYTHON_BIN="${NEXARA_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="python3.12"; fi
exec "$PYTHON_BIN" -m uvicorn nexara_prime.pool_gateway:app --host 127.0.0.1 --port "$PORT"
