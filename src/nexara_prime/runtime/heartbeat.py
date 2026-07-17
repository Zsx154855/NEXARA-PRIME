"""Heartbeat — agent, portfolio, worker, and daemon health pulses."""
from __future__ import annotations

import threading
from dataclasses import dataclass

from nexara_prime.events import EventBus
from nexara_prime.models import now_iso


@dataclass
class HeartbeatRecord:
    component: str = ""
    last_beat: str = ""
    beat_count: int = 0
    healthy: bool = True
    missed_beats: int = 0
    max_missed_beats: int = 3


class Heartbeat:
    """Multi-component heartbeat system.

    Tracks:
    - Agent heartbeat (NexaraPrime identity alive)
    - Portfolio heartbeat (PortfolioDirector active)
    - Worker heartbeats (registered workers alive)
    - Program health (stale program detection)
    - Daemon health (main loop running)
    - EventBus health
    - Database health
    """

    INTERVAL_SECONDS: float = 5.0

    def __init__(self, events: EventBus) -> None:
        self._events = events
        self._records: dict[str, HeartbeatRecord] = {}
        self._active = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_stale_callbacks: list = []

        # Initialize core components
        for comp in ("agent", "portfolio", "daemon", "eventbus", "database"):
            self._records[comp] = HeartbeatRecord(
                component=comp, healthy=True,
            )

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="nexara-heartbeat"
        )
        self._thread.start()

    def stop(self) -> None:
        self._active = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def _run(self) -> None:
        while self._active and not self._stop_event.is_set():
            self.pulse()
            self._stop_event.wait(timeout=self.INTERVAL_SECONDS)

    def pulse(self) -> None:
        """Emit a heartbeat pulse and check for stale components."""
        now = now_iso()
        for comp, rec in self._records.items():
            rec.beat_count += 1
            rec.last_beat = now

        self._events.publish(
            "heartbeat.pulse", "nexara_prime", "heartbeat", "system", "pulse",
            {
                "timestamp": now,
                "components": {
                    comp: {"beats": rec.beat_count, "healthy": rec.healthy}
                    for comp, rec in self._records.items()
                },
            },
        )

    def register_worker(self, worker_id: str) -> None:
        self._records[f"worker:{worker_id}"] = HeartbeatRecord(
            component=f"worker:{worker_id}",
            healthy=True,
        )

    def worker_beat(self, worker_id: str) -> None:
        key = f"worker:{worker_id}"
        if key in self._records:
            self._records[key].last_beat = now_iso()
            self._records[key].missed_beats = 0
            self._records[key].healthy = True

    def check_stale(self, max_missed: int = 3) -> list[str]:
        """Check for stale components. Returns list of stale component IDs."""
        stale = []
        for comp, rec in self._records.items():
            if rec.missed_beats >= max_missed:
                rec.healthy = False
                stale.append(comp)
                for cb in self._on_stale_callbacks:
                    try:
                        cb(comp, rec.missed_beats)
                    except Exception:
                        pass
        return stale

    def on_stale(self, callback) -> None:
        self._on_stale_callbacks.append(callback)

    def is_healthy(self, component: str = "") -> bool:
        if component:
            rec = self._records.get(component)
            return rec.healthy if rec else False
        return all(rec.healthy for rec in self._records.values())

    def status(self) -> dict:
        return {
            comp: {
                "healthy": rec.healthy,
                "beats": rec.beat_count,
                "last_beat": rec.last_beat,
                "missed": rec.missed_beats,
            }
            for comp, rec in self._records.items()
        }
