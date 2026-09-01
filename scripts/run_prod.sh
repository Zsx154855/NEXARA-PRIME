#!/usr/bin/env bash
# NEXARA production runtime entrypoint — no --reload, deterministic env loading.
# Contract: explicit .env loading so provider / mock settings are deterministic.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src"

# Load .env if present (provider / DB path / workspace / report config).
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

# Production semantics: real provider by default (deepseek, key from Keychain),
# never the dev .env mock. Override via NEXARA_PROD_* variables.
export NEXARA_MODEL_PROVIDER="${NEXARA_PROD_PROVIDER:-deepseek}"
export NEXARA_MOCK_MODEL="${NEXARA_PROD_MOCK:-false}"
export NEXARA_MODEL_ENDPOINT="${NEXARA_PROD_ENDPOINT:-https://api.deepseek.com/v1}"
export NEXARA_MODEL_NAME="${NEXARA_PROD_MODEL:-deepseek-v4-pro}"
export NEXARA_MODEL_TIMEOUT="${NEXARA_PROD_TIMEOUT:-120}"
export NEXARA_MAX_OUTPUT_TOKENS="${NEXARA_PROD_MAX_TOKENS:-4096}"

PYTHON_BIN="${NEXARA_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="python3.12"; fi

exec "$PYTHON_BIN" -m uvicorn nexara_prime.api:app \
  --host "${NEXARA_API_HOST:-127.0.0.1}" \
  --port "${NEXARA_API_PORT:-8765}"
