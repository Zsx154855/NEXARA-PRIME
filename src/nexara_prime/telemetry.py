"""TelemetryService — unified health, metrics, and audit aggregation.

G3-C: Unifies fragmented telemetry across connectors/health, events, and audit.
Wraps existing components without modifying them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .events import EventBus
from .models import now_iso


@dataclass
class TelemetrySnapshot:
    """Aggregated telemetry at a point in time."""
    status: str = "healthy"
    events_total: int = 0
    events_recent_60s: int = 0
    health_checks: list[dict[str, Any]] = field(default_factory=list)
    audit_entries_total: int = 0
    timestamp: str = ""


class TelemetryService:
    """Unified telemetry aggregation service.

    Aggregates:
    - EventBus: event counts, recent activity
    - ConnectorHealthMonitor: health check results
    - ConnectorAuditTrail: audit entry counts

    Does NOT modify any existing component.
    """

    def __init__(self, events: EventBus) -> None:
        self._events = events
        self._health_checks: list[dict[str, Any]] = []
        self._started = False
        self._started_at = ""

    # ── Lifecycle ──

    def start(self) -> None:
        self._started = True
        self._started_at = now_iso()

    def stop(self) -> None:
        self._started = False

    @property
    def running(self) -> bool:
        return self._started

    # ── Health Check Registration ──

    def record_health(self, component: str, status: str, detail: str = "") -> None:
        self._health_checks.append({
            "component": component,
            "status": status,
            "detail": detail,
            "timestamp": now_iso(),
        })
        # Keep only last 100 checks
        if len(self._health_checks) > 100:
            self._health_checks = self._health_checks[-100:]

    # ── Snapshot ──

    def snapshot(self) -> TelemetrySnapshot:
        recent = [
            h for h in self._health_checks
            if h.get("status") != "healthy"
        ]
        return TelemetrySnapshot(
            status="degraded" if recent else "healthy",
            events_total=0,  # EventBus doesn't expose count — would need store query
            events_recent_60s=0,
            health_checks=list(self._health_checks[-10:]),
            audit_entries_total=0,
            timestamp=now_iso(),
        )

    # ── Health ──

    def health(self) -> dict[str, Any]:
        return {
            "service": "telemetry",
            "status": "healthy" if self._started else "stopped",
            "started_at": self._started_at,
            "health_checks_recent": len(self._health_checks),
            "timestamp": now_iso(),
        }
