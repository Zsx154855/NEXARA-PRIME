#!/bin/bash
# V1.2.1 24H stability monitor (no_agent watchdog). Appends one line per tick.
OUT="/Volumes/NEXARA/NEXARA-PRIME/reports/v1.2.1/stability_monitor.log"
DB="/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db"
TS=$(date '+%Y-%m-%d %H:%M:%S')
H=$(curl -s --max-time 5 http://127.0.0.1:8765/health | python3 -c "import json,sys;print(json.load(sys.stdin).get('status'))" 2>/dev/null || echo "unreachable")
DBSZ=$(stat -f%z "$DB" 2>/dev/null || echo 0)
MISSIONS=$(sqlite3 -readonly "file:$DB?mode=ro" "SELECT COUNT(*) FROM records WHERE record_type='mission';" 2>/dev/null)
EVENTS=$(sqlite3 -readonly "file:$DB?mode=ro" "SELECT COUNT(*) FROM events;" 2>/dev/null)
RSS=$(ps -p $(launchctl list 2>/dev/null | awk '/com.nexara.runtime/{print $1}') -o rss= 2>/dev/null | tr -d ' ')
echo "$TS health=$H dbsize=$DBSZ missions=$MISSIONS events=$EVENTS rss=$RSS" >> "$OUT"
