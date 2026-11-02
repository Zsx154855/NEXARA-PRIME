"""Minimal Prometheus text exposition (no third-party dependency).

Counters live in this process; mission counts are read from the store on scrape
so they cannot drift from the database.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

_STARTED = time.time()
_LOCK = threading.Lock()
_COUNTERS: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)


def inc(name: str, **labels: str) -> None:
    key = (name, tuple(sorted(labels.items())))
    with _LOCK:
        _COUNTERS[key] += 1


def _render_counters() -> list[str]:
    lines: list[str] = []
    grouped: dict[str, list[tuple[tuple[tuple[str, str], ...], int]]] = defaultdict(list)
    with _LOCK:
        for (name, labels), value in _COUNTERS.items():
            grouped[name].append((labels, value))
    for name, entries in sorted(grouped.items()):
        lines.append(f"# TYPE {name} counter")
        for labels, value in sorted(entries):
            label_text = ",".join(f'{k}="{v}"' for k, v in labels)
            lines.append(f"{name}{{{label_text}}} {value}" if label_text else f"{name} {value}")
    return lines


def render(store=None) -> str:
    lines = [
        "# HELP nexara_uptime_seconds Seconds since process start",
        "# TYPE nexara_uptime_seconds gauge",
        f"nexara_uptime_seconds {time.time() - _STARTED:.1f}",
        *_render_counters(),
    ]
    if store is not None:
        try:
            rows = store._conn.execute(
                "SELECT payload FROM records WHERE record_type='mission'"
            ).fetchall()
        except Exception:  # noqa: BLE001 - metrics must never take down the app
            rows = []
        counts: dict[str, int] = defaultdict(int)
        import json

        for row in rows:
            try:
                counts[str(json.loads(row["payload"]).get("state", "Unknown"))] += 1
            except (ValueError, TypeError):
                continue
        lines.append("# HELP nexara_missions Missions by state")
        lines.append("# TYPE nexara_missions gauge")
        for state, value in sorted(counts.items()):
            lines.append(f'nexara_missions{{state="{state}"}} {value}')
    return "\n".join(lines) + "\n"
