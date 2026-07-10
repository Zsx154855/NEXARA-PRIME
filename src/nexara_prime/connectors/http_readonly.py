"""HTTPReadOnlyConnector — read-only HTTP GET/HEAD with SSRF guard."""
from __future__ import annotations

import hashlib
import time

from .base import (
    BaseConnector, ConnectorInvocation, ConnectorManifest,
    ConnectorReceipt, ConnectorPermission, RiskLevel,
    ConnectorPolicyDecision,
)
from .browser_readonly import _ssrf_check, _MAX_RESPONSE_BYTES
from ..models import now_iso


class HTTPReadOnlyConnector(BaseConnector):
    def __init__(self, allow_test_localhost: bool = False):
        manifest = ConnectorManifest(
            connector_id="http_readonly",
            version="0.1.0",
            capabilities=["http_get", "http_head"],
            permission_scopes=[
                ConnectorPermission("http.get", RiskLevel.R1),
                ConnectorPermission("http.head", RiskLevel.R1),
            ],
            risk_level=RiskLevel.R1,
            network_policy="deny_by_default",
            timeout=30.0,
            retry_policy={"max_retries": 2, "backoff": "exponential"},
            circuit_breaker_policy={"failure_threshold": 5, "recovery_timeout": 60.0},
            idempotency_support=True,
            max_response_bytes=_MAX_RESPONSE_BYTES,
        )
        super().__init__(manifest)
        self._allow_test_localhost = allow_test_localhost

    async def invoke(self, invocation: ConnectorInvocation) -> ConnectorReceipt:
        started = time.time()
        action = invocation.params.get("action", "http_get")
        url = invocation.params.get("url", "")
        headers = invocation.params.get("headers", {})
        decisions: list[dict] = []

        if action not in ("http_get", "http_head"):
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="blocked", error=f"action '{action}' not allowed",
                started_at=now_iso(), finished_at=now_iso(), trace_id=invocation.trace_id)

        if not url:
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error="no URL", started_at=now_iso(), finished_at=now_iso())

        if not self._allow_test_localhost:
            ok, reason = _ssrf_check(url)
            decisions.append(ConnectorPolicyDecision(
                invocation_id=invocation.invocation_id, action=action,
                allowed=ok, reason=reason, policy_id="ssrf_check").__dict__)
            if not ok:
                return ConnectorReceipt(
                    invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                    status="blocked", error=reason, started_at=now_iso(), finished_at=now_iso(),
                    trace_id=invocation.trace_id, policy_decisions=decisions)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.manifest.timeout) as client:
                if action == "http_get":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.head(url, headers=headers)
                body = resp.text[:_MAX_RESPONSE_BYTES]
                ch = hashlib.sha256(body.encode()).hexdigest()[:16]
                return ConnectorReceipt(
                    invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                    status="success", started_at=now_iso(), finished_at=now_iso(),
                    duration_ms=(time.time() - started) * 1000,
                    result={"status_code": resp.status_code, "content_type": resp.headers.get("content-type", ""),
                            "body_preview": body[:500]},
                    trace_id=invocation.trace_id, content_hash=ch, policy_decisions=decisions)
        except Exception as exc:
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error=str(exc), started_at=now_iso(), finished_at=now_iso(),
                trace_id=invocation.trace_id, policy_decisions=decisions)
