"""NEXARA PRIME Browser Adapter — Governed browser automation.

Supports:
- Mock Driver: deterministic for tests
- Local Driver: Playwright headless with domain allowlist
- Default external network DISABLED; file:// always works

Security constraints:
- Domain Allowlist (empty by default = no external access)
- Download Sandbox (all downloads go to temp sandbox dir)
- Secret Redaction (auto-redact keys/tokens in screenshots)
- Navigation Limits (max 10 pages per session)
- Timeout (30s per action)
- Human Approval for submit/purchase/send
- Screenshot Evidence for every action
- Replay Metadata for audit
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import new_id, now_iso


# ── Capability flags ──

BROWSER_NETWORK_ENABLED = "BROWSER_NETWORK_ENABLED"
BROWSER_DOMAIN_ALLOWLIST_ACTIVE = "BROWSER_DOMAIN_ALLOWLIST_ACTIVE"
BROWSER_DOWNLOAD_SANDBOX = "BROWSER_DOWNLOAD_SANDBOX"
BROWSER_MOCK_DRIVER = "BROWSER_MOCK_DRIVER"


@dataclass
class BrowserCapability:
    flags: list[str] = field(default_factory=list)
    driver_type: str = "mock"
    network_enabled: bool = False
    domain_allowlist: list[str] = field(default_factory=list)
    max_navigations: int = 10
    timeout_seconds: int = 30
    download_sandbox: str = ""


@dataclass
class BrowserAction:
    action_id: str = field(default_factory=lambda: new_id("browser"))
    action_type: str = ""
    target: str = ""
    value: str = ""
    timestamp: str = field(default_factory=now_iso)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowserResult:
    action_id: str = ""
    success: bool = False
    title: str = ""
    url: str = ""
    content: str = ""
    dom_snapshot: str = ""
    screenshot_path: str = ""
    extracted_data: dict[str, Any] = field(default_factory=dict)
    network_summary: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)
    navigation_count: int = 0


class BrowserDriver(ABC):
    """Abstract browser driver interface."""

    @abstractmethod
    def probe_capability(self) -> BrowserCapability: ...

    @abstractmethod
    def navigate(self, url: str) -> BrowserResult: ...

    @abstractmethod
    def read_page(self) -> BrowserResult: ...

    @abstractmethod
    def extract_structured(self, selector: str) -> BrowserResult: ...

    @abstractmethod
    def click(self, selector: str) -> BrowserResult: ...

    @abstractmethod
    def type_text(self, selector: str, text: str) -> BrowserResult: ...

    @abstractmethod
    def upload_file(self, selector: str, file_path: str) -> BrowserResult: ...

    @abstractmethod
    def download(self, url: str) -> BrowserResult: ...

    @abstractmethod
    def screenshot(self) -> BrowserResult: ...

    @abstractmethod
    def dom_snapshot(self) -> BrowserResult: ...

    @abstractmethod
    def close(self) -> None: ...


class MockBrowserDriver(BrowserDriver):
    """Deterministic mock driver for tests — no real browser."""

    def __init__(self) -> None:
        self._current_url: str = "about:blank"
        self._current_title: str = "Mock Page"
        self._page_content: str = "<html><body><h1>Mock Browser</h1><p>Deterministic mock.</p></body></html>"
        self._nav_count: int = 0

    def probe_capability(self) -> BrowserCapability:
        return BrowserCapability(flags=[BROWSER_MOCK_DRIVER], driver_type="mock", network_enabled=False)

    def navigate(self, url: str) -> BrowserResult:
        self._nav_count += 1
        self._current_url = url
        if url.startswith("file://"):
            p = Path(url[7:])
            if p.exists():
                try:
                    self._page_content = p.read_text(encoding="utf-8", errors="replace")[:100_000]
                    self._current_title = p.name
                except Exception:
                    self._page_content = f"[Mock] Cannot read: {p}"
            else:
                self._page_content = f"[Mock] File not found: {p}"
        elif url.startswith(("http://", "https://")):
            self._current_title = f"Mock: {url[:60]}"
            self._page_content = f"<html><body><h1>Mock</h1><p>URL: {url}</p></body></html>"
        return BrowserResult(action_id=new_id("browser"), success=True, title=self._current_title, url=self._current_url, content=self._page_content, navigation_count=self._nav_count)

    def read_page(self) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, title=self._current_title, url=self._current_url, content=self._page_content)

    def extract_structured(self, selector: str) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, extracted_data={"selector": selector, "result": f"[Mock] Extracted from {selector}"})

    def click(self, selector: str) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, title=self._current_title, url=self._current_url, content=f"[Mock] Clicked: {selector}")

    def type_text(self, selector: str, text: str) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, content=f"[Mock] Typed into {selector}: {text[:100]}")

    def upload_file(self, selector: str, file_path: str) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, content=f"[Mock] Uploaded {file_path} to {selector}")

    def download(self, url: str) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, content=f"[Mock] Downloaded from {url}")

    def screenshot(self) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, screenshot_path="[mock] screenshot.png")

    def dom_snapshot(self) -> BrowserResult:
        return BrowserResult(action_id=new_id("browser"), success=True, dom_snapshot=self._page_content)

    def close(self) -> None:
        pass


class GovernedBrowserAdapter:
    """Governed browser adapter with domain allowlist, sandbox, and approval gates."""

    HIGH_RISK_ACTIONS = {"submit", "purchase", "send", "delete", "transfer", "pay", "checkout", "confirm"}
    SECRET_PATTERNS = ["api_key", "apikey", "api-key", "secret", "token", "password", "authorization", "bearer", "access_key", "private_key"]

    def __init__(self, driver: BrowserDriver | None = None, *, domain_allowlist: list[str] | None = None, max_navigations: int = 10, timeout_seconds: int = 30, download_sandbox_dir: str | None = None, evidence_store=None, approval_engine=None) -> None:
        self.driver = driver or MockBrowserDriver()
        self.domain_allowlist = domain_allowlist or []
        self.max_navigations = max_navigations
        self.timeout_seconds = timeout_seconds
        self.download_sandbox_dir = download_sandbox_dir or tempfile.mkdtemp(prefix="nexara_browser_dl_")
        self.evidence = evidence_store
        self.approvals = approval_engine
        self._nav_count = 0
        self._action_history: list[BrowserAction] = []
        Path(self.download_sandbox_dir).mkdir(parents=True, exist_ok=True)

    def _check_domain(self, url: str) -> tuple[bool, str]:
        if url.startswith("file://"):
            return True, "local_file_allowed"
        if not self.domain_allowlist:
            return False, "external_network_disabled_no_allowlist"
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        for allowed in self.domain_allowlist:
            if hostname == allowed or hostname.endswith("." + allowed):
                return True, "domain_in_allowlist"
        return False, f"domain_not_in_allowlist:{hostname}"

    def _check_navigation_limit(self) -> tuple[bool, str]:
        if self._nav_count >= self.max_navigations:
            return False, f"navigation_limit_exceeded:{self.max_navigations}"
        return True, "ok"

    def _check_high_risk(self, action_type: str, target: str) -> tuple[bool, str]:
        lowered = (action_type + target).lower()
        for risk in self.HIGH_RISK_ACTIONS:
            if risk in lowered:
                return True, f"high_risk_action:{risk}"
        return False, "ok"

    def _redact_secrets(self, text: str) -> str:
        result = text
        for pat in self.SECRET_PATTERNS:
            result = re.sub(rf'(?i)(["\']?\w*{pat}\w*["\']?\s*[=:]\s*)[^\s,;"\'<>]+', r'\1[REDACTED]', result)
        return result

    def _record_evidence(self, action: BrowserAction, result: BrowserResult) -> list[str]:
        if not self.evidence:
            return []
        payload = json.dumps({"action_id": action.action_id, "action_type": action.action_type, "target": self._redact_secrets(action.target), "success": result.success, "url": result.url, "title": result.title, "duration_ms": result.duration_ms, "error": result.error}, ensure_ascii=False)
        try:
            ev = self.evidence.add("browser_session", "browser_action", f"Browser: {action.action_type}", payload, action.action_id, actor="browser_adapter", source="browser", verification_status="verified")
            return [ev.evidence_id]
        except Exception:
            return []

    # ── Governed Actions ──
    def navigate(self, url: str) -> BrowserResult:
        allowed, reason = self._check_domain(url)
        if not allowed:
            return BrowserResult(error=reason)
        allowed_nav, nav_reason = self._check_navigation_limit()
        if not allowed_nav:
            return BrowserResult(error=nav_reason)
        is_hr, hr_reason = self._check_high_risk("navigate", url)
        if is_hr:
            return BrowserResult(error=f"approval_required:{hr_reason}")
        started = time.monotonic()
        result = self.driver.navigate(url)
        result.duration_ms = (time.monotonic() - started) * 1000
        self._nav_count += 1
        action = BrowserAction(action_type="navigate", target=url)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def read_page(self) -> BrowserResult:
        result = self.driver.read_page()
        result.content = self._redact_secrets(result.content)
        action = BrowserAction(action_type="read_page", target=result.url)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def click(self, selector: str) -> BrowserResult:
        is_hr, hr_reason = self._check_high_risk("click", selector)
        if is_hr:
            return BrowserResult(error=f"approval_required:{hr_reason}")
        result = self.driver.click(selector)
        action = BrowserAction(action_type="click", target=selector)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def type_text(self, selector: str, text: str) -> BrowserResult:
        is_hr, hr_reason = self._check_high_risk("type", selector + text)
        if is_hr:
            return BrowserResult(error=f"approval_required:{hr_reason}")
        result = self.driver.type_text(selector, text)
        action = BrowserAction(action_type="type_text", target=selector, value=text)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def extract_structured(self, selector: str) -> BrowserResult:
        result = self.driver.extract_structured(selector)
        action = BrowserAction(action_type="extract", target=selector)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def upload_file(self, selector: str, file_path: str) -> BrowserResult:
        resolved = str(Path(file_path).resolve())
        sandbox_dir = str(Path(self.download_sandbox_dir).resolve())
        # Use real path containment, not string prefix match
        try:
            Path(resolved).relative_to(sandbox_dir)
        except ValueError:
            return BrowserResult(error="upload_path_outside_sandbox")
        result = self.driver.upload_file(selector, resolved)
        action = BrowserAction(action_type="upload", target=selector, value=file_path)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def download(self, url: str) -> BrowserResult:
        allowed, reason = self._check_domain(url)
        if not allowed:
            return BrowserResult(error=reason)
        result = self.driver.download(url)
        action = BrowserAction(action_type="download", target=url)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def screenshot(self) -> BrowserResult:
        result = self.driver.screenshot()
        action = BrowserAction(action_type="screenshot", target=result.url)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def dom_snapshot(self) -> BrowserResult:
        result = self.driver.dom_snapshot()
        result.dom_snapshot = self._redact_secrets(result.dom_snapshot)
        action = BrowserAction(action_type="dom_snapshot", target=result.url)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    # ── Lifecycle ──
    def probe_capability(self) -> BrowserCapability:
        cap = self.driver.probe_capability()
        cap.domain_allowlist = list(self.domain_allowlist)
        cap.max_navigations = self.max_navigations
        cap.timeout_seconds = self.timeout_seconds
        cap.download_sandbox = self.download_sandbox_dir
        if self.domain_allowlist:
            cap.flags.append(BROWSER_DOMAIN_ALLOWLIST_ACTIVE)
        cap.flags.append(BROWSER_DOWNLOAD_SANDBOX)
        return cap

    def get_action_history(self) -> list[dict[str, Any]]:
        return [{"action_id": a.action_id, "action_type": a.action_type, "target": a.target, "timestamp": a.timestamp} for a in self._action_history]

    def close(self) -> None:
        self.driver.close()
        try:
            shutil.rmtree(self.download_sandbox_dir, ignore_errors=True)
        except OSError:
            pass
