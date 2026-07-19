"""NEXARA PRIME Connector base types — unified signatures for all connectors."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable

from ..models import RiskLevel, now_iso, new_id


class ConnectorLifecycleState(str, enum.Enum):
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    CONFIGURED = "configured"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ConnectorCredentialReference:
    backend: str
    path: str
    name_hint: str = ""


@dataclass
class ConnectorPermission:
    scope: str
    risk_level: RiskLevel = RiskLevel.R1
    requires_approval: bool = False
    description: str = ""


@dataclass
class ConnectorManifest:
    connector_id: str
    version: str = "0.1.0"
    capabilities: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    permission_scopes: list[ConnectorPermission] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R1
    network_policy: str = "deny_by_default"
    credential_refs: list[ConnectorCredentialReference] = field(default_factory=list)
    timeout: float = 30.0
    retry_policy: dict[str, Any] | None = None
    circuit_breaker_policy: dict[str, Any] | None = None
    idempotency_support: bool = False
    evidence_policy: str = "all"
    health_check_interval: float = 30.0
    max_response_bytes: int = 10 * 1024 * 1024


@dataclass
class ConnectorHealth:
    state: ConnectorLifecycleState = ConnectorLifecycleState.UNREGISTERED
    healthy: bool = False
    last_check: str = ""
    message: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorInvocation:
    invocation_id: str = field(default_factory=lambda: new_id("inv"))
    connector_id: str = ""
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: new_id("trc"))
    actor_id: str = ""
    session_id: str = ""
    mission_id: str = ""
    created_at: str = field(default_factory=now_iso)


@dataclass
class ConnectorReceipt:
    invocation_id: str
    connector_id: str = ""
    status: str = "unknown"
    started_at: str = ""
    finished_at: str = ""
    duration_ms: float = 0.0
    result: dict[str, Any] | None = None
    error: str | None = None
    evidence_ref: str = ""
    trace_id: str = ""
    content_hash: str = ""
    redirect_chain: list[str] = field(default_factory=list)
    policy_decisions: list[dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    circuit_state: str = ""


@dataclass
class ConnectorPolicyDecision:
    decision_id: str = field(default_factory=lambda: new_id("dec"))
    invocation_id: str = ""
    action: str = ""
    allowed: bool = False
    reason: str = ""
    policy_id: str = ""
    risk_level: RiskLevel = RiskLevel.R1
    timestamp: str = field(default_factory=now_iso)


class BaseConnector:
    manifest: ConnectorManifest

    def __init__(self, manifest: ConnectorManifest):
        self.manifest = manifest
        self._state = ConnectorLifecycleState.UNREGISTERED
        self._health = ConnectorHealth(state=self._state, healthy=False)

    @property
    def state(self) -> ConnectorLifecycleState:
        return self._state

    @property
    def health(self) -> ConnectorHealth:
        return self._health

    def register(self) -> None:
        self._state = ConnectorLifecycleState.REGISTERED

    def configure(self, config: dict) -> None:
        self._state = ConnectorLifecycleState.CONFIGURED

    async def start(self) -> None:
        self._transition(ConnectorLifecycleState.STARTING)
        try:
            await self._do_start()
            self._transition(ConnectorLifecycleState.HEALTHY)
        except Exception:
            self._transition(ConnectorLifecycleState.FAILED)
            raise

    async def stop(self) -> None:
        self._transition(ConnectorLifecycleState.STOPPING)
        try:
            await self._do_stop()
        finally:
            self._transition(ConnectorLifecycleState.STOPPED)

    async def health_check(self) -> ConnectorHealth:
        try:
            ok, msg = await self._do_health_check()
            if ok:
                self._health = ConnectorHealth(state=self._state, healthy=True, last_check=now_iso(), message=msg or "healthy")
            else:
                self._transition(ConnectorLifecycleState.DEGRADED)
                self._health = ConnectorHealth(state=self._state, healthy=False, last_check=now_iso(), message=msg or "degraded")
        except Exception as exc:
            self._transition(ConnectorLifecycleState.FAILED)
            self._health = ConnectorHealth(state=self._state, healthy=False, last_check=now_iso(), message=str(exc))
        return self._health

    async def invoke(self, invocation: ConnectorInvocation) -> ConnectorReceipt:
        raise NotImplementedError

    async def _do_start(self) -> None: pass
    async def _do_stop(self) -> None: pass

    async def _do_health_check(self) -> tuple[bool, str]:
        return True, "ok"

    def _transition(self, target: ConnectorLifecycleState) -> None:
        self._state = target

    def set_shutdown_hook(self, hook: Callable) -> None:
        self._shutdown_hook = hook


_VALID_TRANSITIONS: dict[ConnectorLifecycleState, set[ConnectorLifecycleState]] = {
    ConnectorLifecycleState.UNREGISTERED: {ConnectorLifecycleState.REGISTERED},
    ConnectorLifecycleState.REGISTERED: {ConnectorLifecycleState.CONFIGURED, ConnectorLifecycleState.UNREGISTERED},
    ConnectorLifecycleState.CONFIGURED: {ConnectorLifecycleState.STARTING, ConnectorLifecycleState.REGISTERED},
    ConnectorLifecycleState.STARTING: {ConnectorLifecycleState.HEALTHY, ConnectorLifecycleState.FAILED},
    ConnectorLifecycleState.HEALTHY: {ConnectorLifecycleState.DEGRADED, ConnectorLifecycleState.CIRCUIT_OPEN, ConnectorLifecycleState.STOPPING},
    ConnectorLifecycleState.DEGRADED: {ConnectorLifecycleState.HEALTHY, ConnectorLifecycleState.CIRCUIT_OPEN, ConnectorLifecycleState.FAILED, ConnectorLifecycleState.STOPPING},
    ConnectorLifecycleState.CIRCUIT_OPEN: {ConnectorLifecycleState.HEALTHY, ConnectorLifecycleState.FAILED, ConnectorLifecycleState.STOPPING},
    ConnectorLifecycleState.STOPPING: {ConnectorLifecycleState.STOPPED, ConnectorLifecycleState.FAILED},
    ConnectorLifecycleState.STOPPED: {ConnectorLifecycleState.STARTING},
    ConnectorLifecycleState.FAILED: {ConnectorLifecycleState.STARTING, ConnectorLifecycleState.UNREGISTERED},
}
