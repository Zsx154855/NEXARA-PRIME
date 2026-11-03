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
# (name, labels) -> {bucket_upper_bound: cumulative_count}
_BUCKETS = (0.005, 0.025, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_HIST: dict[tuple[str, tuple[tuple[str, str], ...]], dict[float, int]] = defaultdict(
    lambda: {b: 0 for b in _BUCKETS}
)
_HIST_SUM: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_HIST_COUNT: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)


def inc(name: str, **labels: str) -> None:
    key = (name, tuple(sorted(labels.items())))
    with _LOCK:
        _COUNTERS[key] += 1


def observe(name: str, value: float, **labels: str) -> None:
    """Record one observation in a cumulative histogram."""
    key = (name, tuple(sorted(labels.items())))
    with _LOCK:
        for bound in _BUCKETS:
            if value <= bound:
                _HIST[key][bound] += 1
        _HIST_SUM[key] += value
        _HIST_COUNT[key] += 1


def _render_histograms() -> list[str]:
    lines: list[str] = []
    with _LOCK:
        snapshot = {k: dict(v) for k, v in _HIST.items()}
        sums = dict(_HIST_SUM)
        counts = dict(_HIST_COUNT)
    for (name, labels), buckets in sorted(snapshot.items()):
        label_text = ",".join(f'{k}="{v}"' for k, v in labels)
        prefix = f"{label_text}," if label_text else ""
        lines.append(f"# TYPE {name} histogram")
        for bound in _BUCKETS:
            lines.append(f'{name}_bucket{{{prefix}le="{bound}"}} {buckets[bound]}')
        lines.append(f'{name}_bucket{{{prefix}le="+Inf"}} {counts[(name, labels)]}')
        lines.append(f"{name}_sum{{{label_text}}} {round(sums[(name, labels)], 6)}")
        lines.append(f"{name}_count{{{label_text}}} {counts[(name, labels)]}")
    return lines


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
        *_render_histograms(),
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
