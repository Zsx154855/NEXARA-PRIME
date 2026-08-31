#!/bin/bash
# Stability window 监控 (30min, 只读)
DB="file:/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db?mode=ro"
OUT="/Volumes/NEXARA/NEXARA-PRIME/reports/productized-runtime-gap-closure/stability/stability.log"
START=$(date +%s); END=$((START + 1800))
echo "stability_start=$(date '+%Y-%m-%d %H:%M:%S') duration=1800s" > "$OUT"
while [ $(date +%s) -lt $END ]; do
  H=$(curl -s http://127.0.0.1:8765/health 2>/dev/null)
  ST=$(echo "$H" | python3 -c "import json,sys;print(json.load(sys.stdin).get('status','?'))" 2>/dev/null)
  EC=$(sqlite3 -readonly "$DB" "SELECT COUNT(*) FROM events;" 2>/dev/null)
  MC=$(sqlite3 -readonly "$DB" "SELECT COUNT(*) FROM records WHERE record_type='mission';" 2>/dev/null)
  PID=$(launchctl list 2>/dev/null | grep com.nexara.runtime | awk '{print $1}')
  RES=$(ps -p "$PID" -o %cpu=,%mem=,rss= 2>/dev/null | tr -s ' ')
  DBSIZE=$(ls -l /Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db 2>/dev/null | awk '{print $5}')
  echo "$(date '+%H:%M:%S') health=$ST events=$EC missions=$MC pid=$PID cpu_mem_rss=[$RES] dbsize=$DBSIZE" >> "$OUT"
  sleep 30
done
echo "stability_end=$(date '+%Y-%m-%d %H:%M:%S')" >> "$OUT"
echo "DONE" >> "$OUT"
