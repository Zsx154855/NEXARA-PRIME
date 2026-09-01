#!/usr/bin/env bash
# Gracefully stop the NEXARA runtime (SIGTERM → uvicorn graceful shutdown).
set -euo pipefail
PORT="${NEXARA_API_PORT:-8765}"

PID="$(lsof -ti :"$PORT" 2>/dev/null | head -1 || true)"
if [[ -z "$PID" ]]; then
  echo "No NEXARA runtime listening on port $PORT"
  exit 0
fi

echo "Stopping NEXARA runtime (PID $PID) on port $PORT ..."
kill -TERM "$PID"

for _ in {1..10}; do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "Runtime stopped gracefully."
    exit 0
  fi
  sleep 1
done

echo "Runtime did not exit within 10s — still shutting down (do NOT use -9)."
exit 0
