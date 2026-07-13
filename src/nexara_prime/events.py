from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .db import SQLiteStore
from .models import Event, new_id


class EventBus:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self._subscribers: list[Callable[[Event], None]] = []

    def subscribe(self, callback: Callable[[Event], None]) -> None:
        self._subscribers.append(callback)

    def publish(
        self,
        event_type: str,
        aggregate_id: str,
        aggregate_type: str,
        actor: str,
        trace_id: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Event:
        event = Event(
            event_id=new_id("evt"),
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            actor=actor,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            payload=payload or {},
        )
        persisted = Event.model_validate(
            self.store.save_event(event.model_dump(mode="json"))
        )
        if persisted.event_id == event.event_id:
            for subscriber in list(self._subscribers):
                try:
                    subscriber(persisted)
                except Exception:
                    # A telemetry subscriber must never break the mission path.
                    continue
        return persisted

    def replay(self, aggregate_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(aggregate_id)
