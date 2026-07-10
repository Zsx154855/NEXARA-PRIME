#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src"
PYTHON_BIN="${NEXARA_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="python3.12"; fi
exec "$PYTHON_BIN" -m uvicorn nexara_prime.api:app --host "${NEXARA_API_HOST:-127.0.0.1}" --port "${NEXARA_API_PORT:-8765}" --reload
