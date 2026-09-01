#!/usr/bin/env python3
"""
NEXARA Home V2.3 — Real Runtime UI Acceptance Capture (FIXED API CONNECTIVITY).

Captures the running NEXARA Control Console (Next.js dev at localhost:3000,
backend at 127.0.0.1:8766, direct cross-origin calls) with real browser
screenshots + network/console diagnostics. No mocks.

Screenshots:
  01_home_desktop_1440x900.png  (full page, 1440x900 viewport)
  02_command_palette_cmdk.png   (palette opened via the ⌘K button)
  03_memory_wheel.png           (clip to MemoryWheel region)
  04_current_mission.png        (clip to CurrentMission region)
  05_mobile_390x844.png         (full page, 390x844 viewport)

Also writes evidence_home_v23.json with console/page/network diagnostics
and programmatic UI checks.
"""

import json
import re
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright

EVIDENCE_DIR = "/Users/agentos/NEXARA-PRIME/evidence/home_v2.3"
BASE_URL = "http://localhost:3000/console"
API_BASE = "http://127.0.0.1:8766"
WHEEL_SEL = '[aria-label="柏韩 记忆系统"]'
ERROR_SEL = 'text="Runtime 不可用"'


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class SessionCapture:
    """Collects console, page-error and network events for one session."""

    def __init__(self, tag: str):
        self.tag = tag
        self.console_errors = []
        self.console_warnings = []
        self.page_errors = []
        self.api_requests = []
        self.api_responses = []
        self.failed_requests = []
        self.failed_api_requests = []

    def attach(self, page):
        def on_console(msg):
            text = msg.text
            loc = msg.location
            entry = {"text": text, "url": loc.get("url", "")}
            if msg.type == "error":
                self.console_errors.append(entry)
            elif msg.type == "warning":
                self.console_warnings.append(entry)

        def on_pageerror(err):
            self.page_errors.append({"message": err.message, "stack": (err.stack or "")[:1200]})

        def on_request(req):
            if "/api/" in req.url:
                self.api_requests.append({"method": req.method, "url": req.url, "session": self.tag})

        def on_response(res):
            if "/api/" in res.url:
                self.api_responses.append({
                    "method": res.request.method,
                    "url": res.url,
                    "status": res.status,
                    "session": self.tag,
                })

        def on_requestfailed(req):
            try:
                reason = req.failure or "aborted"
                entry = {"url": req.url, "method": req.method, "failure": reason, "session": self.tag}
                self.failed_requests.append(entry)
                if "/api/" in req.url:
                    self.failed_api_requests.append(entry)
            except Exception:  # noqa: BLE001 — never let a listener break the run
                pass

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_requestfailed)


def goto_and_resolve(page, wait_ms: int = 30000) -> dict:
    """Navigate, wait for network idle, then for MemoryWheel or error state."""
    state = {"wheel_present": False, "error_shown": False, "error_message": None,
             "goto_error": None, "wait_error": None}
    try:
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
    except Exception as e:  # noqa: BLE001
        state["goto_error"] = f"{type(e).__name__}: {e}"
    try:
        page.wait_for_selector(WHEEL_SEL, state="visible", timeout=wait_ms)
    except Exception as e:  # noqa: BLE001
        state["wait_error"] = f"{type(e).__name__}: {e}"
        try:
            page.wait_for_selector(ERROR_SEL, state="visible", timeout=wait_ms)
        except Exception:  # noqa: BLE001
            pass
    state["wheel_present"] = page.locator(WHEEL_SEL).count() > 0
    if page.locator(ERROR_SEL).count() > 0:
        state["error_shown"] = True
        err_p = page.locator(ERROR_SEL).locator("xpath=following-sibling::p").first
        try:
            state["error_message"] = err_p.inner_text().strip() if err_p.count() else None
        except Exception:  # noqa: BLE001
            state["error_message"] = None
    return state


def center_text_of_wheel(page) -> list:
    """Text of the MemoryWheel center node (柏韩 + runtime status)."""
    region = page.locator(WHEEL_SEL)
    if region.count() == 0:
        return []
    spans = region.locator("span")
    out = []
    for i in range(spans.count()):
        try:
            t = spans.nth(i).inner_text().strip()
        except Exception:  # noqa: BLE001
            continue
        if t == "柏韩":
            parent = spans.nth(i).locator("xpath=..")
            out.append(parent.inner_text().strip())
    return out


def check_memory_wheel(page) -> dict:
    region = page.locator(WHEEL_SEL)
    present = region.count() > 0
    result = {"memory_wheel_present": present}
    if not present:
        result.update({
            "memory_wheel_quadrant_count": 0,
            "memory_wheel_quadrant_labels": [],
            "memory_wheel_center_text": None,
            "memory_wheel_region_box": None,
        })
        return result
    buttons = region.locator("button")
    labels = []
    for i in range(buttons.count()):
        labels.append(buttons.nth(i).get_attribute("aria-label"))
    box = region.bounding_box()
    result.update({
        "memory_wheel_quadrant_count": buttons.count(),
        "memory_wheel_quadrant_labels": labels,
        "memory_wheel_center_text": center_text_of_wheel(page),
        "memory_wheel_region_box": box,
    })
    return result


def check_current_mission(page) -> dict:
    regions = page.locator('[role="region"][aria-label^="当前使命"]')
    result = {"current_mission_present": regions.count() > 0}
    if regions.count() == 0:
        result.update({"current_mission_aria_label": None,
                       "current_mission_text": None,
                       "current_mission_region_box": None})
        return result
    region = regions.first
    result.update({
        "current_mission_aria_label": region.get_attribute("aria-label"),
        "current_mission_text": region.inner_text().strip()[:600],
        "current_mission_region_box": region.bounding_box(),
    })
    return result


def check_continue_duplicates(page) -> dict:
    """Count distinct 继续任务/继续当前使命 affordances on the page.

    The CurrentMissionCard continue button exposes visible text 继续任务 AND
    aria-label 继续当前使命 (same element) — a naive text+label sum double
    counts it. We therefore count unique buttons by accessible name.
    """
    buttons = page.get_by_role("button", name=re.compile("继续"))
    names = []
    for i in range(buttons.count()):
        names.append(buttons.nth(i).get_attribute("aria-label")
                     or buttons.nth(i).inner_text().strip())
    return {
        "continue_button_count": buttons.count(),
        "continue_button_accessible_names": names,
        "continue_task_duplicate_detected": buttons.count() > 1,
    }


def probe_backend(paths) -> list:
    """Directly probe the backend with a browser Origin header to record the
    true HTTP status and CORS headers for the endpoints the UI calls."""
    import urllib.error
    import urllib.request

    results = []
    for path in paths:
        req = urllib.request.Request(
            f"{API_BASE}{path}", headers={"Origin": "http://localhost:3000"}
        )
        entry = {"path": path}
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                entry["status"] = r.status
                entry["access_control_allow_origin"] = r.headers.get("Access-Control-Allow-Origin")
        except urllib.error.HTTPError as e:
            entry["status"] = e.code
            entry["access_control_allow_origin"] = e.headers.get("Access-Control-Allow-Origin")
            entry["error"] = "HTTPError"
        except Exception as e:  # noqa: BLE001
            entry["status"] = None
            entry["error"] = f"{type(e).__name__}: {e}"
        results.append(entry)
    return results


def main() -> None:
    started_at = now_iso()
    screenshots = []
    checks = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ───────────────────────── Desktop session ─────────────────────────
        desktop = SessionCapture("desktop")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        desktop.attach(page)

        state = goto_and_resolve(page)
        checks.update(state)

        # Programmatic checks
        brand = page.get_by_text("Nexara-柏韩")
        checks["sidebar_brand_visible"] = brand.count() > 0 and brand.first.is_visible()

        cmdk = page.get_by_role("button", name="打开命令面板 (⌘K)")
        checks["topbar_cmdk_button_visible"] = cmdk.count() > 0 and cmdk.first.is_visible()

        status_els = page.locator('[role="status"]')
        checks["topbar_status_texts"] = [
            status_els.nth(i).inner_text().strip() for i in range(status_els.count())
        ]

        checks.update(check_memory_wheel(page))
        checks.update(check_current_mission(page))
        checks.update(check_continue_duplicates(page))

        # Screenshot 01 — full desktop page
        shot = f"{EVIDENCE_DIR}/01_home_desktop_1440x900.png"
        page.screenshot(path=shot, full_page=True)
        screenshots.append(shot)

        # Screenshot 02 — command palette opened via ⌘K button
        palette_opened = False
        palette_options = []
        try:
            cmdk.first.click(timeout=10000)
            page.wait_for_selector('[role="dialog"][aria-label="命令面板"]', state="visible", timeout=8000)
            palette_opened = True
            page.wait_for_timeout(500)
            shot = f"{EVIDENCE_DIR}/02_command_palette_cmdk.png"
            page.screenshot(path=shot, full_page=True)
            screenshots.append(shot)
            opts = page.locator('[role="listbox"] [role="option"]')
            for i in range(opts.count()):
                palette_options.append(opts.nth(i).inner_text().strip())
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception as e:  # noqa: BLE001
            checks["command_palette_error"] = f"{type(e).__name__}: {e}"
        checks["command_palette_opened"] = palette_opened
        checks["command_palette_options"] = palette_options

        # Screenshot 03 — MemoryWheel clip
        if state["wheel_present"]:
            wheel = page.locator(WHEEL_SEL)
            try:
                shot = f"{EVIDENCE_DIR}/03_memory_wheel.png"
                wheel.screenshot(path=shot)
                screenshots.append(shot)
            except Exception as e:  # noqa: BLE001
                checks["memory_wheel_screenshot_error"] = f"{type(e).__name__}: {e}"

        # Screenshot 04 — CurrentMission clip
        mission_region = page.locator('[role="region"][aria-label^="当前使命"]')
        if mission_region.count() > 0:
            try:
                shot = f"{EVIDENCE_DIR}/04_current_mission.png"
                mission_region.first.screenshot(path=shot)
                screenshots.append(shot)
            except Exception as e:  # noqa: BLE001
                checks["current_mission_screenshot_error"] = f"{type(e).__name__}: {e}"

        # Let one 10s polling cycle run so repeat API calls are observable
        page.wait_for_timeout(12000)
        ctx.close()

        # ───────────────────────── Mobile session ──────────────────────────
        mobile = SessionCapture("mobile")
        mctx = browser.new_context(viewport={"width": 390, "height": 844})
        mpage = mctx.new_page()
        mobile.attach(mpage)

        mstate = goto_and_resolve(mpage)
        mobile_nav = mpage.locator('nav[aria-label="移动导航"]')
        checks["mobile_bottom_nav_visible"] = mobile_nav.count() > 0 and mobile_nav.first.is_visible()
        mstatus = mpage.locator('[role="status"]')
        checks["mobile_topbar_status_texts"] = [
            mstatus.nth(i).inner_text().strip() for i in range(mstatus.count())
        ]
        checks["mobile_wheel_present"] = mstate["wheel_present"]
        if mstate["error_shown"]:
            checks["mobile_error_shown"] = True
            checks["mobile_error_message"] = mstate["error_message"]

        shot = f"{EVIDENCE_DIR}/05_mobile_390x844.png"
        mpage.screenshot(path=shot, full_page=True)
        screenshots.append(shot)
        mctx.close()

        browser.close()

    # ───────────────────────── Evidence aggregation ────────────────────────
    api_requests = desktop.api_requests + mobile.api_requests
    api_responses = desktop.api_responses + mobile.api_responses
    failed_all = desktop.failed_requests + mobile.failed_requests
    failed_api = desktop.failed_api_requests + mobile.failed_api_requests

    failed_urls = {}
    for f in failed_api:
        failed_urls.setdefault(f["url"], []).append(f["failure"])

    checks["api_request_count"] = len(api_requests)
    checks["api_failed_count"] = len(failed_api)
    checks["failed_api_request_urls"] = {u: v for u, v in failed_urls.items()}
    checks["non_api_failed_requests"] = [
        f for f in failed_all if "/api/" not in f["url"]
    ]
    checks["backend_probe"] = probe_backend(
        ["/api/runtime/overview", "/api/runtime/stats", "/api/memory", "/api/memory/stats"]
    )

    evidence = {
        "started_at": started_at,
        "finished_at": now_iso(),
        "base_url": BASE_URL,
        "api_base_url": API_BASE,
        "console_errors": desktop.console_errors + mobile.console_errors,
        "console_warnings": desktop.console_warnings + mobile.console_warnings,
        "page_errors": desktop.page_errors + mobile.page_errors,
        "api_requests": api_requests,
        "api_responses": api_responses,
        "failed_requests": failed_all,
        "checks": checks,
        "screenshots": screenshots,
    }

    out_path = f"{EVIDENCE_DIR}/evidence_home_v23.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, ensure_ascii=False, indent=2)

    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(f"\nEvidence JSON -> {out_path}")
    for s in screenshots:
        print(f"Screenshot   -> {s}")


if __name__ == "__main__":
    sys.exit(main())
