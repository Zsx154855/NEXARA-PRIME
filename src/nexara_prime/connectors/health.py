"""ConnectorHealthMonitor — circuit breaker and health tracking."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout: float = 60.0
    half_open_max: int = 1
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed | open | half_open
    half_open_attempts: int = 0

    def record_success(self) -> None:
        if self.state == "half_open":
            self.state = "closed"
            self.failure_count = 0
            self.half_open_attempts = 0
        elif self.state == "closed":
            self.failure_count = 0

    def record_failure(self) -> str:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == "half_open":
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_max:
                self.state = "open"
        elif self.failure_count >= self.failure_threshold:
            self.state = "open"
        return self.state

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half_open"
                self.half_open_attempts = 0
                return True
            return False
        return self.state == "half_open"


class ConnectorHealthMonitor:
    def __init__(self):
        self._circuits: dict[str, CircuitBreaker] = {}

    def get_circuit(self, connector_id: str, threshold: int = 3, recovery: float = 60.0) -> CircuitBreaker:
        if connector_id not in self._circuits:
            self._circuits[connector_id] = CircuitBreaker(
                failure_threshold=threshold, recovery_timeout=recovery)
        return self._circuits[connector_id]

    def circuit_state(self, connector_id: str) -> str:
        cb = self._circuits.get(connector_id)
        return cb.state if cb else "closed"

    def is_circuit_open(self, connector_id: str) -> bool:
        cb = self._circuits.get(connector_id)
        return not cb.allow_request() if cb else False
