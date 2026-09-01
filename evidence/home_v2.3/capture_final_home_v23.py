#!/usr/bin/env python3
"""
NEXARA Home V2.3 — FINAL Acceptance Capture.

Captures the running NEXARA Control Console (Next.js dev at localhost:3000,
backend at 127.0.0.1:8766, direct cross-origin calls) with real browser
screenshots + network/console diagnostics. No mocks.

Acceptance scope:
  * /api/memory/stats must return 200 (previously 500 / CORS-blocked)
  * Memory wheel quadrant labels must include record counts
  * Sidebar brand, 4 quadrants, wheel center 柏韩, CurrentMission present,
    exactly one continue CTA (no duplicates)

Screenshots (evidence/home_v2.3/):
  FINAL_home.png     full page, 1440x900
  FINAL_palette.png  command palette opened via the ⌘K button
  FINAL_wheel.png    MemoryWheel region clip
  FINAL_mission.png  CurrentMission region clip
  FINAL_mobile.png   full page, 390x844

Also writes FINAL_evidence.json with console/page/network diagnostics and
programmatic UI checks.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from playwright.sync_api import Page, sync_playwright

EVIDENCE_DIR = "/Users/agentos/NEXARA-PRIME/evidence/home_v2.3"
BASE_URL = "http://localhost:3000/console"
API_BASE = "http://127.0.0.1:8766"
API_HOST = "127.0.0.1:8766"
WHEEL_SEL = '[aria-label="柏韩 记忆系统"]'
ERROR_SEL = 'text="Runtime 不可用"'
DIALOG_SEL = '[role="dialog"][aria-label="命令面板"]'
MISSION_REGION_SEL = '[role="region"][aria-label^="当前使命"]'
MOBILE_NAV_SEL = 'nav[aria-label="移动导航"]'


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class SessionCapture:
    """Collects console, page-error and network events for one session."""

    def __init__(self, tag: str):
        self.tag = tag
        self.console_errors: list[dict[str, str]] = []
        self.console_warnings: list[dict[str, str]] = []
        self.page_errors: list[dict[str, str]] = []
        self.api_requests: list[dict[str, Any]] = []
        self.api_responses: list[dict[str, Any]] = []
        self.failed_requests: list[dict[str, Any]] = []
        self.failed_api_requests: list[dict[str, Any]] = []

    def attach(self, page: Page) -> None:
        def on_console(msg) -> None:
            loc = msg.location
            entry = {"text": msg.text, "url": loc.get("url", "")}
            if msg.type == "error":
                self.console_errors.append(entry)
            elif msg.type == "warning":
                self.console_warnings.append(entry)

        def on_pageerror(err) -> None:
            self.page_errors.append(
                {"message": err.message, "stack": (err.stack or "")[:1200]}
            )

        def on_request(req) -> None:
            if "/api/" in req.url:
                self.api_requests.append(
                    {"method": req.method, "url": req.url, "session": self.tag}
                )

        def on_response(res) -> None:
            if "/api/" in res.url:
                self.api_responses.append(
                    {
                        "method": res.request.method,
                        "url": res.url,
                        "status": res.status,
                        "session": self.tag,
                    }
                )

        def on_requestfailed(req) -> None:
            try:
                reason = req.failure or "aborted"
                entry = {"url": req.url, "method": req.method,
                         "failure": reason, "session": self.tag}
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


def goto_and_resolve(page: Page, wait_ms: int = 30000) -> dict[str, Any]:
    """Navigate, wait for network idle, then for MemoryWheel or error state."""
    state: dict[str, Any] = {
        "wheel_present": False,
        "error_shown": False,
        "error_message": None,
        "goto_error": None,
        "wait_error": None,
    }
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
            state["error_message"] = (
                err_p.inner_text().strip() if err_p.count() else None
            )
        except Exception:  # noqa: BLE001
            state["error_message"] = None
    return state


def center_text_of_wheel(page: Page) -> list[str]:
    """Text of the MemoryWheel center node (柏韩 + runtime status)."""
    region = page.locator(WHEEL_SEL)
    if region.count() == 0:
        return []
    spans = region.locator("span")
    out: list[str] = []
    for i in range(spans.count()):
        try:
            t = spans.nth(i).inner_text().strip()
        except Exception:  # noqa: BLE001
            continue
        if t == "柏韩":
            parent = spans.nth(i).locator("xpath=..")
            try:
                out.append(parent.inner_text().strip())
            except Exception:  # noqa: BLE001
                pass
    return out


def check_memory_wheel(page: Page) -> dict[str, Any]:
    region = page.locator(WHEEL_SEL)
    present = region.count() > 0
    result: dict[str, Any] = {"memory_wheel_present": present}
    if not present:
        result.update(
            {
                "memory_wheel_quadrant_count": 0,
                "memory_wheel_quadrant_labels": [],
                "memory_wheel_quadrant_counts": [],
                "quadrant_labels_include_counts": False,
                "memory_wheel_center_text": None,
                "memory_wheel_region_box": None,
            }
        )
        return result

    buttons = region.locator("button")
    labels: list[str] = []
    count_spans: list[str] = []
    for i in range(buttons.count()):
        labels.append(buttons.nth(i).get_attribute("aria-label") or "")
        # Count span is the last visible span inside the quadrant button.
        spans = buttons.nth(i).locator("span")
        try:
            counts = [s.inner_text().strip() for s in spans.all() if s.is_visible()]
        except Exception:  # noqa: BLE001
            counts = []
        count_spans.append(counts)

    labels_with_counts = [lb for lb in labels if re.search(r"·\s*\d+\s*条记录", lb)]
    box = region.bounding_box()
    result.update(
        {
            "memory_wheel_quadrant_count": buttons.count(),
            "memory_wheel_quadrant_labels": labels,
            "memory_wheel_quadrant_count_spans": count_spans,
            "quadrant_labels_include_counts": len(labels_with_counts) == buttons.count()
            and buttons.count() == 4,
            "quadrant_labels_with_counts": labels_with_counts,
            "memory_wheel_center_text": center_text_of_wheel(page),
            "memory_wheel_region_box": box,
        }
    )
    return result


def check_current_mission(page: Page) -> dict[str, Any]:
    regions = page.locator(MISSION_REGION_SEL)
    result: dict[str, Any] = {"current_mission_present": regions.count() > 0}
    if regions.count() == 0:
        result.update(
            {
                "current_mission_aria_label": None,
                "current_mission_text": None,
                "current_mission_region_box": None,
            }
        )
        return result
    region = regions.first
    result.update(
        {
            "current_mission_aria_label": region.get_attribute("aria-label"),
            "current_mission_text": region.inner_text().strip()[:600],
            "current_mission_region_box": region.bounding_box(),
        }
    )
    return result


def check_continue_duplicates(page: Page) -> dict[str, Any]:
    """Count distinct continue affordances.

    The CurrentMissionCard continue button exposes visible text 继续任务 AND
    aria-label 继续当前使命 (same element) — a naive text+label sum double
    counts it. We count unique buttons by accessible name and also scan all
    visible text occurrences for a true-duplicate audit.
    """
    buttons = page.get_by_role("button", name=re.compile("继续"))
    names: list[str] = []
    for i in range(buttons.count()):
        names.append(
            buttons.nth(i).get_attribute("aria-label")
            or buttons.nth(i).inner_text().strip()
        )
    text_hits = page.get_by_text(re.compile("继续任务|继续当前使命"), exact=False)
    visible_text_hits = 0
    for i in range(text_hits.count()):
        try:
            if text_hits.nth(i).is_visible():
                visible_text_hits += 1
        except Exception:  # noqa: BLE001
            pass
    return {
        "continue_button_count": buttons.count(),
        "continue_button_accessible_names": names,
        "continue_task_duplicate_detected": buttons.count() > 1,
        "visible_continue_text_hits": visible_text_hits,
    }


def probe_backend(paths: list[str]) -> list[dict[str, Any]]:
    """Directly probe the backend with a browser Origin header to record the
    true HTTP status and CORS headers for the endpoints the UI calls."""
    results: list[dict[str, Any]] = []
    for path in paths:
        req = urllib.request.Request(
            f"{API_BASE}{path}", headers={"Origin": "http://localhost:3000"}
        )
        entry: dict[str, Any] = {"path": path}
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                entry["status"] = r.status
                entry["access_control_allow_origin"] = r.headers.get(
                    "Access-Control-Allow-Origin"
                )
        except urllib.error.HTTPError as e:
            entry["status"] = e.code
            entry["access_control_allow_origin"] = e.headers.get(
                "Access-Control-Allow-Origin"
            )
            entry["error"] = "HTTPError"
        except Exception as e:  # noqa: BLE001
            entry["status"] = None
            entry["error"] = f"{type(e).__name__}: {e}"
        results.append(entry)
    return results


def run_desktop(browser) -> tuple[SessionCapture, dict[str, Any]]:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    capture = SessionCapture("desktop")
    capture.attach(page)

    checks: dict[str, Any] = goto_and_resolve(page)

    brand = page.get_by_text("Nexara-柏韩")
    checks["sidebar_brand_visible"] = (
        brand.count() > 0 and brand.first.is_visible()
    )

    cmdk = page.get_by_role("button", name="打开命令面板 (⌘K)")
    checks["topbar_cmdk_button_visible"] = (
        cmdk.count() > 0 and cmdk.first.is_visible()
    )

    status_els = page.locator('[role="status"]')
    checks["topbar_status_texts"] = [
        status_els.nth(i).inner_text().strip() for i in range(status_els.count())
    ]

    checks.update(check_memory_wheel(page))
    checks.update(check_current_mission(page))
    checks.update(check_continue_duplicates(page))

    # Screenshot 01 — full desktop page
    shot = f"{EVIDENCE_DIR}/FINAL_home.png"
    page.screenshot(path=shot, full_page=True)

    # Screenshot 02 — command palette opened via ⌘K button
    palette_opened = False
    palette_options: list[str] = []
    try:
        cmdk.first.click(timeout=10000)
        page.wait_for_selector(DIALOG_SEL, state="visible", timeout=8000)
        palette_opened = True
        page.wait_for_timeout(600)  # let the dialog settle
        shot = f"{EVIDENCE_DIR}/FINAL_palette.png"
        page.screenshot(path=shot, full_page=True)
        opts = page.locator('[role="listbox"] [role="option"]')
        for i in range(opts.count()):
            palette_options.append(opts.nth(i).inner_text().strip())
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception as e:  # noqa: BLE001
        checks["command_palette_error"] = f"{type(e).__name__}: {e}"
    checks["command_palette_opened"] = palette_opened
    checks["command_palette_options"] = palette_options
    checks["command_palette_option_count"] = len(palette_options)

    # Screenshot 03 — MemoryWheel clip
    if checks["wheel_present"]:
        wheel = page.locator(WHEEL_SEL)
        try:
            shot = f"{EVIDENCE_DIR}/FINAL_wheel.png"
            wheel.screenshot(path=shot)
        except Exception as e:  # noqa: BLE001
            checks["memory_wheel_screenshot_error"] = f"{type(e).__name__}: {e}"

    # Screenshot 04 — CurrentMission clip
    mission_region = page.locator(MISSION_REGION_SEL)
    if mission_region.count() > 0:
        try:
            shot = f"{EVIDENCE_DIR}/FINAL_mission.png"
            mission_region.first.screenshot(path=shot)
        except Exception as e:  # noqa: BLE001
            checks["current_mission_screenshot_error"] = f"{type(e).__name__}: {e}"

    # Let one 10s polling cycle run so repeat API calls are observable
    page.wait_for_timeout(12000)
    ctx.close()
    return capture, checks


def run_mobile(browser) -> tuple[SessionCapture, dict[str, Any]]:
    mctx = browser.new_context(viewport={"width": 390, "height": 844})
    mpage = mctx.new_page()
    capture = SessionCapture("mobile")
    capture.attach(mpage)

    checks: dict[str, Any] = goto_and_resolve(mpage)
    mobile_nav = mpage.locator(MOBILE_NAV_SEL)
    checks["mobile_bottom_nav_visible"] = (
        mobile_nav.count() > 0 and mobile_nav.first.is_visible()
    )
    mstatus = mpage.locator('[role="status"]')
    checks["mobile_topbar_status_texts"] = [
        mstatus.nth(i).inner_text().strip() for i in range(mstatus.count())
    ]
    checks["mobile_wheel_present"] = checks["wheel_present"]
    if checks["error_shown"]:
        checks["mobile_error_shown"] = True
        checks["mobile_error_message"] = checks["error_message"]

    shot = f"{EVIDENCE_DIR}/FINAL_mobile.png"
    mpage.screenshot(path=shot, full_page=True)
    mctx.close()
    return capture, checks


def main() -> int:
    started_at = now_iso()
    screenshots: list[str] = []
    checks: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()

        desktop, desktop_checks = run_desktop(browser)
        mobile, mobile_checks = run_mobile(browser)

        browser.close()

    checks.update(desktop_checks)
    checks["mobile_checks"] = mobile_checks

    # ── Evidence aggregation ──
    api_requests = desktop.api_requests + mobile.api_requests
    api_responses = desktop.api_responses + mobile.api_responses
    failed_all = desktop.failed_requests + mobile.failed_requests
    failed_api = desktop.failed_api_requests + mobile.failed_api_requests

    failed_urls: dict[str, list[str]] = {}
    for f in failed_api:
        failed_urls.setdefault(f["url"], []).append(f["failure"])

    # All /api/* requests must target the backend host 127.0.0.1:8766
    api_urls = sorted({r["url"] for r in api_requests})
    non_backend = [u for u in api_urls if API_HOST not in u]

    # Status per endpoint (from browser responses)
    endpoint_status: dict[str, list[int]] = {}
    for r in api_responses:
        path = r["url"].split(API_HOST, 1)[-1]
        endpoint_status.setdefault(path, []).append(r["status"])
    status_summary = {k: {"statuses": v, "last": v[-1]} for k, v in endpoint_status.items()}

    memory_stats_statuses = status_summary.get("/api/memory/stats", {}).get("statuses", [])
    checks["api_request_count"] = len(api_requests)
    checks["api_failed_count"] = len(failed_api)
    checks["failed_api_request_urls"] = failed_urls
    checks["non_api_failed_requests"] = [
        f for f in failed_all if "/api/" not in f["url"]
    ]
    checks["all_api_requests_target_127_0_0_1_8766"] = not non_backend
    checks["non_backend_api_urls"] = non_backend
    checks["api_endpoint_status_summary"] = status_summary
    checks["memory_stats_statuses"] = memory_stats_statuses
    checks["memory_stats_last_status"] = memory_stats_statuses[-1] if memory_stats_statuses else None
    checks["memory_stats_all_200"] = all(s == 200 for s in memory_stats_statuses)
    checks["backend_probe"] = probe_backend(
        ["/api/runtime/overview", "/api/runtime/stats", "/api/memory", "/api/memory/stats"]
    )

    evidence = {
        "capture": "FINAL — NEXARA Home V2.3 acceptance",
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
        "api_urls": api_urls,
        "checks": checks,
        "screenshots": screenshots,
    }

    # Record screenshots actually written
    import os

    for name in [
        "FINAL_home.png",
        "FINAL_palette.png",
        "FINAL_wheel.png",
        "FINAL_mission.png",
        "FINAL_mobile.png",
    ]:
        path = f"{EVIDENCE_DIR}/{name}"
        if os.path.exists(path):
            screenshots.append(path)

    out_path = f"{EVIDENCE_DIR}/FINAL_evidence.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, ensure_ascii=False, indent=2)

    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(f"\nEvidence JSON -> {out_path}")
    for s in screenshots:
        print(f"Screenshot   -> {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
