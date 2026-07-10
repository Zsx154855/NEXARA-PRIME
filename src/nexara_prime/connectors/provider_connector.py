"""ProviderConnector — wraps model_gateway as a connector."""
from __future__ import annotations

import time

from .base import (
    BaseConnector, ConnectorInvocation, ConnectorManifest,
    ConnectorReceipt, ConnectorPermission, RiskLevel,
    ConnectorCredentialReference,
)
from ..models import now_iso


class ProviderConnector(BaseConnector):
    def __init__(self, gateway=None, credential_ref: str = ""):
        creds = []
        if credential_ref:
            creds.append(ConnectorCredentialReference(backend="keychain", path=credential_ref))
        manifest = ConnectorManifest(
            connector_id="provider",
            version="0.1.0",
            capabilities=["chat_completion", "structured_output"],
            permission_scopes=[
                ConnectorPermission("provider.chat", RiskLevel.R1),
                ConnectorPermission("provider.structured", RiskLevel.R1),
            ],
            risk_level=RiskLevel.R1,
            network_policy="deny_by_default",
            timeout=60.0,
            retry_policy={"max_retries": 2, "backoff": "exponential", "base_delay": 1.0},
            circuit_breaker_policy={"failure_threshold": 3, "recovery_timeout": 60.0},
            idempotency_support=False,
            evidence_policy="receipt_only",
            credential_refs=creds,
        )
        super().__init__(manifest)
        self._gateway = gateway

    async def invoke(self, invocation: ConnectorInvocation) -> ConnectorReceipt:
        if not self._gateway:
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error="no gateway configured",
                started_at=now_iso(), finished_at=now_iso(), trace_id=invocation.trace_id)
        started = time.time()
        try:
            result = await self._gateway.chat(invocation.params)
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="success", started_at=now_iso(), finished_at=now_iso(),
                duration_ms=(time.time() - started) * 1000,
                result={"model": result.get("model", "unknown")},
                trace_id=invocation.trace_id)
        except Exception as exc:
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error=str(exc), started_at=now_iso(), finished_at=now_iso(),
                trace_id=invocation.trace_id)
