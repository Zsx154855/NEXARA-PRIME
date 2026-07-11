"""BrowserReadOnlyConnector — read-only browser via Playwright with SSRF protection."""
from __future__ import annotations

import hashlib
import ipaddress
import time
import urllib.parse
from typing import List

from .base import (
    BaseConnector, ConnectorInvocation, ConnectorManifest,
    ConnectorReceipt, ConnectorPermission, RiskLevel,
    ConnectorPolicyDecision,
)
from ..models import now_iso, new_id

_PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]
_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal"}
_BLOCKED_SCHEMES = {"file", "javascript", "data", "ftp"}
_MAX_REDIRECTS = 5
_DEFAULT_TIMEOUT_MS = 15_000
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


def _ssrf_check(url: str) -> tuple[bool, str]:
    """Validate URL target is not private/malicious."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        return False, f"blocked scheme: {parsed.scheme}"
    hostname = parsed.hostname
    if not hostname:
        return False, "no hostname in URL"
    if hostname in _METADATA_HOSTS:
        return False, f"blocked metadata host: {hostname}"
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        import socket
        try:
            resolved = socket.gethostbyname(hostname)
            addr = ipaddress.ip_address(resolved)
        except Exception:
            return True, "unresolvable"
    for priv in _PRIVATE_IP_RANGES:
        if addr in priv:
            return False, f"blocked private IP: {addr}"
    return True, "ok"


class BrowserReadOnlyConnector(BaseConnector):
    """Read-only browser with SSRF guard. Uses Playwright when available."""

    def __init__(self, allow_test_localhost: bool = False):
        manifest = ConnectorManifest(
            connector_id="browser_readonly",
            version="0.1.0",
            capabilities=["navigate", "read_dom", "read_text", "screenshot", "get_title"],
            permission_scopes=[
                ConnectorPermission("browser.navigate", RiskLevel.R1),
                ConnectorPermission("browser.read_dom", RiskLevel.R1),
                ConnectorPermission("browser.read_text", RiskLevel.R1),
                ConnectorPermission("browser.screenshot", RiskLevel.R1),
            ],
            risk_level=RiskLevel.R1,
            network_policy="deny_by_default",
            timeout=30.0,
            retry_policy={"max_retries": 2, "backoff": "exponential", "base_delay": 1.0},
            circuit_breaker_policy={"failure_threshold": 5, "recovery_timeout": 60.0},
            idempotency_support=True,
            evidence_policy="all",
            max_response_bytes=_MAX_RESPONSE_BYTES,
        )
        super().__init__(manifest)
        self._allow_test_localhost = allow_test_localhost
        self._browser = None
        self._playwright = None

    async def _do_start(self) -> None:
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        except ImportError:
            self._browser = None
        except Exception:
            self._browser = None

    async def _do_stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _do_health_check(self) -> tuple[bool, str]:
        if self._browser is None:
            return False, "browser not available"
        return True, "ready"

    async def invoke(self, invocation: ConnectorInvocation) -> ConnectorReceipt:
        started = time.time()
        action = invocation.params.get("action", "navigate")
        url = invocation.params.get("url", "")
        decisions: list[dict] = []

        if not url:
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error="no URL", started_at=now_iso(), finished_at=now_iso(),
                trace_id=invocation.trace_id)

        if not self._allow_test_localhost:
            ok, reason = _ssrf_check(url)
            decisions.append(ConnectorPolicyDecision(
                invocation_id=invocation.invocation_id, action="navigate",
                allowed=ok, reason=reason, policy_id="ssrf_check",
            ).__dict__)
            if not ok:
                return ConnectorReceipt(
                    invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                    status="blocked", error=reason, started_at=now_iso(), finished_at=now_iso(),
                    trace_id=invocation.trace_id, policy_decisions=decisions)

        blocked_actions = {"POST", "submit", "upload", "download", "login", "payment", "publish"}
        if action in blocked_actions or invocation.params.get("method", "GET") not in ("GET", "HEAD", ""):
            decisions.append(ConnectorPolicyDecision(
                invocation_id=invocation.invocation_id, action=action, allowed=False,
                reason=f"action '{action}' blocked in read-only mode", policy_id="read_only",
            ).__dict__)
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="blocked", error=f"action '{action}' blocked",
                started_at=now_iso(), finished_at=now_iso(),
                trace_id=invocation.trace_id, policy_decisions=decisions)

        if self._browser is None:
            return ConnectorReceipt(
                invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error="browser not available (playwright not installed)",
                started_at=now_iso(), finished_at=now_iso(), trace_id=invocation.trace_id,
                policy_decisions=decisions)

        if action == "navigate":
            return await self._navigate(invocation, url, decisions, started)
        if action == "screenshot":
            return await self._screenshot(invocation, url, decisions, started)
        return ConnectorReceipt(
            invocation_id=invocation.invocation_id, connector_id=self.manifest.connector_id,
            status="success", result={"action": action}, started_at=now_iso(), finished_at=now_iso(),
            trace_id=invocation.trace_id, policy_decisions=decisions)

    async def _navigate(self, inv, url, decisions, started):
        page = await self._browser.new_page()
        try:
            resp = await page.goto(url, timeout=_DEFAULT_TIMEOUT_MS, wait_until="domcontentloaded")
            title = await page.title()
            text = (await page.inner_text("body"))[:_MAX_RESPONSE_BYTES]
            content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            # Safely get redirect chain
            redirect_chain: list[str] = []
            try:
                if resp and hasattr(resp, 'request') and resp.request:
                    if hasattr(resp.request, 'redirect_chain'):
                        redirect_chain = [r.url for r in resp.request.redirect_chain]
            except Exception:
                pass
            actual_url = page.url
            # Post-redirect SSRF check
            if not self._allow_test_localhost and actual_url != url:
                ok2, reason2 = _ssrf_check(actual_url)
                if not ok2:
                    await page.close()
                    decisions.append(ConnectorPolicyDecision(
                        invocation_id=inv.invocation_id, action="redirect",
                        allowed=False, reason=f"post-redirect SSRF: {reason2}",
                        policy_id="ssrf_redirect_check").__dict__)
                    return ConnectorReceipt(
                        invocation_id=inv.invocation_id, connector_id=self.manifest.connector_id,
                        status="blocked", error=f"redirect to blocked target: {reason2}",
                        started_at=now_iso(), finished_at=now_iso(),
                        trace_id=inv.trace_id, policy_decisions=decisions)
            await page.close()
            return ConnectorReceipt(
                invocation_id=inv.invocation_id, connector_id=self.manifest.connector_id,
                status="success", started_at=now_iso(), finished_at=now_iso(),
                duration_ms=(time.time() - started) * 1000,
                result={"title": title, "url": actual_url, "text_preview": text[:500]},
                trace_id=inv.trace_id, content_hash=content_hash,
                redirect_chain=[actual_url] if not redirect_chain else redirect_chain,
                policy_decisions=decisions)
        except Exception as exc:
            await page.close()
            return ConnectorReceipt(
                invocation_id=inv.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error=str(exc), started_at=now_iso(), finished_at=now_iso(),
                trace_id=inv.trace_id, policy_decisions=decisions)

    async def _screenshot(self, inv, url, decisions, started):
        page = await self._browser.new_page()
        try:
            await page.goto(url, timeout=_DEFAULT_TIMEOUT_MS, wait_until="domcontentloaded")
            data = await page.screenshot(type="png")
            ch = hashlib.sha256(data).hexdigest()[:16]
            await page.close()
            return ConnectorReceipt(
                invocation_id=inv.invocation_id, connector_id=self.manifest.connector_id,
                status="success", started_at=now_iso(), finished_at=now_iso(),
                duration_ms=(time.time() - started) * 1000,
                result={"screenshot_bytes": len(data)},
                trace_id=inv.trace_id, content_hash=ch, policy_decisions=decisions)
        except Exception as exc:
            await page.close()
            return ConnectorReceipt(
                invocation_id=inv.invocation_id, connector_id=self.manifest.connector_id,
                status="failed", error=str(exc), started_at=now_iso(), finished_at=now_iso(),
                trace_id=inv.trace_id, policy_decisions=decisions)
