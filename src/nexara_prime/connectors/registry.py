"""ConnectorRegistry — register, unregister, list, find connectors."""
from __future__ import annotations

from .base import BaseConnector, ConnectorLifecycleState, ConnectorManifest


class ConnectorRegistry:
    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {}
        self._manifests: dict[str, ConnectorManifest] = {}

    def register(self, connector: BaseConnector) -> None:
        cid = connector.manifest.connector_id
        if cid in self._connectors:
            raise ValueError(f"Connector {cid} already registered")
        connector.register()
        self._connectors[cid] = connector
        self._manifests[cid] = connector.manifest

    def unregister(self, connector_id: str) -> None:
        if connector_id not in self._connectors:
            raise KeyError(f"Connector {connector_id} not found")
        del self._connectors[connector_id]
        del self._manifests[connector_id]

    def get(self, connector_id: str) -> BaseConnector:
        if connector_id not in self._connectors:
            raise KeyError(f"Connector {connector_id} not found")
        return self._connectors[connector_id]

    def list_connectors(self) -> list[dict]:
        return [
            {"connector_id": cid, "version": m.version,
             "state": conn.state.value, "healthy": conn.health.healthy,
             "risk_level": m.risk_level.value,
             "capabilities": m.capabilities}
            for cid, conn in self._connectors.items()
            for m in [self._manifests[cid]]
        ]

    def list_ids(self) -> list[str]:
        return list(self._connectors.keys())

    def get_manifest(self, connector_id: str) -> ConnectorManifest:
        return self._manifests[connector_id]

    async def start_all(self) -> dict[str, str]:
        results = {}
        for cid, conn in self._connectors.items():
            if conn.state in (ConnectorLifecycleState.CONFIGURED, ConnectorLifecycleState.STOPPED):
                try:
                    await conn.start()
                    results[cid] = "started"
                except Exception as exc:
                    results[cid] = f"failed: {exc}"
        return results

    async def stop_all(self) -> dict[str, str]:
        results = {}
        for cid, conn in self._connectors.items():
            if conn.state in (ConnectorLifecycleState.HEALTHY, ConnectorLifecycleState.DEGRADED):
                try:
                    await conn.stop()
                    results[cid] = "stopped"
                except Exception as exc:
                    results[cid] = f"failed: {exc}"
        return results
