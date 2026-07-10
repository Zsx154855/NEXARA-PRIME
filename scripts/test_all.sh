#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src"
cd "$ROOT"
PYTHON_BIN="${NEXARA_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="python3.12"; fi
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${TMPDIR:-/tmp}/nexara-prime-pycache}"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -c 'from pathlib import Path; [compile(p.read_text(encoding="utf-8"), str(p), "exec") for p in Path("src").rglob("*.py")]'
PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -m unittest discover -s tests -v
