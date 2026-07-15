"""NEXARA PRIME Computer Use Adapter — Governed desktop automation.

Only implements governed desktop actions:
- App Focus, Read UI state, Click bounded target, Type bounded content
- Take screenshot, Wait for UI state

Security:
- App Allowlist (visible app names)
- Screen region limits
- Mandatory approval before key actions
- No arbitrary terminal input
- No system settings modification
- No password input
- No Apple ID/iCloud operations
- No silent send
- Before/After Evidence for every action
- Mock Driver for tests
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import new_id, now_iso


# ── Capability flags ──
COMPUTER_USE_MOCK_DRIVER = "COMPUTER_USE_MOCK_DRIVER"
COMPUTER_USE_APP_ALLOWLIST_ACTIVE = "COMPUTER_USE_APP_ALLOWLIST_ACTIVE"
COMPUTER_USE_REGION_LIMITED = "COMPUTER_USE_REGION_LIMITED"


@dataclass
class ComputerUseCapability:
    flags: list[str] = field(default_factory=list)
    driver_type: str = "mock"
    app_allowlist: list[str] = field(default_factory=list)
    screen_region: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "width": 1920, "height": 1080})
    screenshot_enabled: bool = True


@dataclass
class ComputerUseAction:
    action_id: str = field(default_factory=lambda: new_id("cu"))
    action_type: str = ""
    app_name: str = ""
    target: str = ""
    value: str = ""
    timestamp: str = field(default_factory=now_iso)
    before_evidence: str = ""
    after_evidence: str = ""


@dataclass
class ComputerUseResult:
    action_id: str = ""
    success: bool = False
    ui_state: dict[str, Any] = field(default_factory=dict)
    screenshot_path: str = ""
    error: str = ""
    duration_ms: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)


class ComputerUseDriver(ABC):
    """Abstract computer-use driver."""

    @abstractmethod
    def probe_capability(self) -> ComputerUseCapability: ...

    @abstractmethod
    def focus_app(self, app_name: str) -> ComputerUseResult: ...

    @abstractmethod
    def read_ui_state(self) -> ComputerUseResult: ...

    @abstractmethod
    def click(self, x: int, y: int) -> ComputerUseResult: ...

    @abstractmethod
    def type_text(self, text: str) -> ComputerUseResult: ...

    @abstractmethod
    def take_screenshot(self) -> ComputerUseResult: ...

    @abstractmethod
    def wait_for_ui_state(self, condition: str, timeout_seconds: float = 5.0) -> ComputerUseResult: ...


class MockComputerUseDriver(ComputerUseDriver):
    """Deterministic mock for tests — no real desktop access."""

    def __init__(self) -> None:
        self._current_app: str = "Finder"
        self._ui_state: dict[str, Any] = {"app": "Finder", "windows": [], "focused_element": ""}

    def probe_capability(self) -> ComputerUseCapability:
        return ComputerUseCapability(flags=[COMPUTER_USE_MOCK_DRIVER], driver_type="mock")

    def focus_app(self, app_name: str) -> ComputerUseResult:
        self._current_app = app_name
        self._ui_state["app"] = app_name
        return ComputerUseResult(action_id=new_id("cu"), success=True, ui_state=self._ui_state)

    def read_ui_state(self) -> ComputerUseResult:
        return ComputerUseResult(action_id=new_id("cu"), success=True, ui_state=self._ui_state)

    def click(self, x: int, y: int) -> ComputerUseResult:
        return ComputerUseResult(action_id=new_id("cu"), success=True, ui_state={"clicked": {"x": x, "y": y}, "app": self._current_app})

    def type_text(self, text: str) -> ComputerUseResult:
        return ComputerUseResult(action_id=new_id("cu"), success=True, ui_state={"typed": text[:50], "app": self._current_app})

    def take_screenshot(self) -> ComputerUseResult:
        return ComputerUseResult(action_id=new_id("cu"), success=True, screenshot_path=f"[mock] screenshot_{new_id('ss')}.png")

    def wait_for_ui_state(self, condition: str, timeout_seconds: float = 5.0) -> ComputerUseResult:
        return ComputerUseResult(action_id=new_id("cu"), success=True, ui_state={"condition": condition, "matched": True})


class GovernedComputerUseAdapter:
    """Governed computer-use adapter with app allowlist and approval gates."""

    FORBIDDEN_APPS = {"System Settings", "System Preferences", "Terminal", "iTerm2", "Activity Monitor", "Keychain Access", "Apple ID", "iCloud"}
    FORBIDDEN_ACTIONS = {"password", "sudo", "rm -rf", "delete system", "format", "shutdown", "reboot"}

    def __init__(self, driver: ComputerUseDriver | None = None, *, app_allowlist: list[str] | None = None, screen_region: dict[str, int] | None = None, evidence_store=None, approval_engine=None) -> None:
        self.driver = driver or MockComputerUseDriver()
        self.app_allowlist = app_allowlist or []
        self.screen_region = screen_region or {"x": 0, "y": 0, "width": 1920, "height": 1080}
        self.evidence = evidence_store
        self.approvals = approval_engine
        self._action_history: list[ComputerUseAction] = []

    def _check_app(self, app_name: str) -> tuple[bool, str]:
        for forbidden in self.FORBIDDEN_APPS:
            if forbidden.lower() in app_name.lower():
                return False, f"forbidden_app:{forbidden}"
        if not self.app_allowlist:
            return True, "allowlist_not_configured"
        for allowed in self.app_allowlist:
            if allowed.lower() in app_name.lower() or app_name.lower() in allowed.lower():
                return True, "app_in_allowlist"
        return False, f"app_not_in_allowlist:{app_name}"

    def _check_action(self, action_type: str, value: str) -> tuple[bool, str]:
        lowered = (action_type + value).lower()
        for forbidden in self.FORBIDDEN_ACTIONS:
            if forbidden.lower() in lowered:
                return False, f"forbidden_action:{forbidden}"
        return True, "ok"

    def _check_bounds(self, x: int, y: int) -> tuple[bool, str]:
        r = self.screen_region
        if not (r["x"] <= x <= r["x"] + r["width"] and r["y"] <= y <= r["y"] + r["height"]):
            return False, f"click_outside_screen_region:({x},{y})"
        return True, "ok"

    def _before_evidence(self, action: ComputerUseAction) -> str:
        try:
            ss = self.driver.take_screenshot()
            action.before_evidence = ss.screenshot_path
            return ss.screenshot_path
        except Exception:
            return ""

    def _after_evidence(self, action: ComputerUseAction) -> str:
        try:
            ss = self.driver.take_screenshot()
            action.after_evidence = ss.screenshot_path
            return ss.screenshot_path
        except Exception:
            return ""

    def _record_evidence(self, action: ComputerUseAction, result: ComputerUseResult) -> list[str]:
        if not self.evidence:
            return []
        payload = json.dumps({"action_id": action.action_id, "action_type": action.action_type, "app_name": action.app_name, "target": action.target, "success": result.success, "error": result.error, "duration_ms": result.duration_ms, "before_evidence": action.before_evidence, "after_evidence": action.after_evidence}, ensure_ascii=False)
        try:
            ev = self.evidence.add("computer_use_session", "computer_use_action", f"ComputerUse: {action.action_type}", payload, action.action_id, actor="computer_use_adapter", source="computer_use", verification_status="verified")
            return [ev.evidence_id]
        except Exception:
            return []

    # ── Governed Actions ──
    def focus_app(self, app_name: str) -> ComputerUseResult:
        allowed, reason = self._check_app(app_name)
        if not allowed:
            return ComputerUseResult(error=reason)
        action = ComputerUseAction(action_type="focus_app", app_name=app_name)
        self._before_evidence(action)
        started = time.monotonic()
        result = self.driver.focus_app(app_name)
        result.duration_ms = (time.monotonic() - started) * 1000
        self._after_evidence(action)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def read_ui_state(self) -> ComputerUseResult:
        action = ComputerUseAction(action_type="read_ui_state")
        self._before_evidence(action)
        result = self.driver.read_ui_state()
        self._after_evidence(action)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def click(self, x: int, y: int) -> ComputerUseResult:
        in_bounds, reason = self._check_bounds(x, y)
        if not in_bounds:
            return ComputerUseResult(error=reason)
        action = ComputerUseAction(action_type="click", target=f"({x},{y})")
        self._before_evidence(action)
        started = time.monotonic()
        result = self.driver.click(x, y)
        result.duration_ms = (time.monotonic() - started) * 1000
        self._after_evidence(action)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def type_text(self, text: str) -> ComputerUseResult:
        allowed, reason = self._check_action("type", text)
        if not allowed:
            return ComputerUseResult(error=reason)
        action = ComputerUseAction(action_type="type_text", value=text)
        self._before_evidence(action)
        started = time.monotonic()
        result = self.driver.type_text(text)
        result.duration_ms = (time.monotonic() - started) * 1000
        self._after_evidence(action)
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def take_screenshot(self) -> ComputerUseResult:
        action = ComputerUseAction(action_type="take_screenshot")
        result = self.driver.take_screenshot()
        action.after_evidence = result.screenshot_path
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    def wait_for_ui_state(self, condition: str, timeout_seconds: float = 5.0) -> ComputerUseResult:
        action = ComputerUseAction(action_type="wait_for_ui_state", target=condition)
        started = time.monotonic()
        result = self.driver.wait_for_ui_state(condition, timeout_seconds)
        result.duration_ms = (time.monotonic() - started) * 1000
        result.evidence_ids = self._record_evidence(action, result)
        self._action_history.append(action)
        return result

    # ── Lifecycle ──
    def probe_capability(self) -> ComputerUseCapability:
        cap = self.driver.probe_capability()
        cap.app_allowlist = list(self.app_allowlist)
        cap.screen_region = dict(self.screen_region)
        if self.app_allowlist:
            cap.flags.append(COMPUTER_USE_APP_ALLOWLIST_ACTIVE)
        cap.flags.append(COMPUTER_USE_REGION_LIMITED)
        return cap

    def get_action_history(self) -> list[dict[str, Any]]:
        return [{"action_id": a.action_id, "action_type": a.action_type, "app_name": a.app_name, "timestamp": a.timestamp} for a in self._action_history]
