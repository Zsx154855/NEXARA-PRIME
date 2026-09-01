#!/usr/bin/env python3
"""
NEXARA Home V2.3 — Real Runtime UI Acceptance Capture.

Captures the running NEXARA Control Console (Next.js dev at localhost:3000,
backend at 127.0.0.1:8766) with real browser screenshots + diagnostics.

Screenshots (all real, no mocks):
  01_home_desktop_1440x900.png
  02_command_palette_cmdk.png
  03_memory_wheel.png
  04_current_mission.png
  05_mobile_390x844.png
Plus evidence_home_v23.json with console/page/network diagnostics.
"""

import json
import os
import sys
import time

BASE_URL = "http://localhost:3000/console"
OUT_DIR = "/Users/agentos/NEXARA-PRIME/evidence/home_v2.3"
CHROMIUM_FALLBACK = (
    "/Users/agentos/Library/Caches/ms-playwright/chromium_headless_shell-1234/"
    "chrome-headless-shell-mac-arm64/chrome-headless-shell"
)

results = {
    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "base_url": BASE_URL,
    "console_errors": [],
    "console_warnings": [],
    "page_errors": [],
    "api_requests": [],
    "api_responses": [],
    "failed_requests": [],
    "checks": {},
}


def log(msg: str) -> None:
    print(f"[capture] {msg}", flush=True)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as exc:  # browser revision mismatch fallback
            log(f"Default launch failed ({exc}); falling back to cached Chromium")
            browser = p.chromium.launch(headless=True, executable_path=CHROMIUM_FALLBACK)

        desktop = browser.new_context(viewport={"width": 1440, "height": 900})
        page = desktop.new_page()

        def on_console(msg):
            if msg.type == "error":
                results["console_errors"].append({"text": msg.text})
            elif msg.type == "warning":
                results["console_warnings"].append({"text": msg.text})

        def on_pageerror(err):
            results["page_errors"].append(str(err))

        def on_request(req):
            if "/api/" in req.url:
                results["api_requests"].append({"method": req.method, "url": req.url})

        def on_response(resp):
            if "/api/" in resp.url:
                results["api_responses"].append(
                    {"status": resp.status, "url": resp.url}
                )

        def on_requestfailed(req):
            if "/api/" in req.url:
                results["failed_requests"].append(
                    {"url": req.url, "failure": req.failure}
                )

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_requestfailed)

        # ── 01 HOME DESKTOP ──
        log(f"goto {BASE_URL}")
        page.goto(BASE_URL, wait_until="networkidle", timeout=90000)
        # Wait for the dashboard to resolve: MemoryWheel region OR error screen
        try:
            page.wait_for_selector(
                '[aria-label="柏韩 记忆系统"], text="Runtime 不可用"',
                timeout=30000,
            )
        except Exception:
            log("Dashboard never resolved to wheel or error state")
        page.wait_for_timeout(2500)  # settle animations / first paint

        checks = results["checks"]
        checks["topbar_status_texts"] = page.locator("[role=status]").all_inner_texts()
        checks["sidebar_brand_visible"] = (
            page.get_by_text("Nexara-柏韩", exact=True).first.is_visible()
            if page.get_by_text("Nexara-柏韩", exact=True).count()
            else False
        )
        checks["topbar_cmdk_button_visible"] = (
            page.locator('button[aria-label="打开命令面板 (⌘K)"]').count() > 0
            and page.locator('button[aria-label="打开命令面板 (⌘K)"]').is_visible()
        )

        wheel = page.locator('[aria-label="柏韩 记忆系统"]')
        checks["memory_wheel_present"] = wheel.count() > 0
        if wheel.count():
            checks["memory_wheel_quadrant_count"] = wheel.locator("button").count()
            checks["memory_wheel_center_text"] = wheel.locator(
                "text=柏韩"
            ).first.inner_text()
            checks["memory_quadrant_labels"] = wheel.locator(
                "button[aria-label]"
            ).evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")
        else:
            checks["memory_wheel_quadrant_count"] = 0

        cm = page.locator('[aria-label^="当前使命"]')
        checks["current_mission_present"] = cm.count() > 0
        if cm.count():
            checks["current_mission_aria"] = cm.first.get_attribute("aria-label")
            checks["current_mission_text"] = cm.first.inner_text()

        err_screen = page.locator('text="Runtime 不可用"')
        checks["error_screen_shown"] = err_screen.count() > 0
        if err_screen.count():
            checks["error_message"] = (
                page.locator("text=Runtime 不可用")
                .locator("xpath=following::p[1]")
                .first.inner_text()
            )

        page.screenshot(
            path=os.path.join(OUT_DIR, "01_home_desktop_1440x900.png"),
            full_page=True,
        )
        log("saved 01_home_desktop_1440x900.png")

        # ── 02 COMMAND PALETTE (⌘K / Ctrl+K) ──
        page.keyboard.press("Meta+K")
        try:
            page.wait_for_selector(
                '[role="dialog"][aria-label="命令面板"]', timeout=5000
            )
        except Exception:
            page.keyboard.press("Control+K")
            try:
                page.wait_for_selector(
                    '[role="dialog"][aria-label="命令面板"]', timeout=5000
                )
            except Exception:
                pass
        palette = page.locator('[role="dialog"][aria-label="命令面板"]')
        checks["command_palette_opened"] = palette.count() > 0
        page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(OUT_DIR, "02_command_palette_cmdk.png"))
        if palette.count():
            checks["command_palette_option_count"] = palette.locator(
                '[role="option"]'
            ).count()
            checks["command_palette_options"] = palette.locator(
                '[role="option"]'
            ).all_inner_texts()
            # search query variant
            page.fill('input[aria-label="搜索 NEXARA"]', "创建")
            page.wait_for_timeout(400)
            page.screenshot(
                path=os.path.join(OUT_DIR, "02b_command_palette_search.png")
            )
        log("saved 02_command_palette_cmdk.png")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ── 03 MEMORY WHEEL ──
        if wheel.count():
            wheel.scroll_into_view_if_needed()
            page.wait_for_timeout(700)
            box = wheel.first.bounding_box()
            if box:
                page.screenshot(
                    path=os.path.join(OUT_DIR, "03_memory_wheel.png"),
                    clip={
                        "x": max(box["x"] - 30, 0),
                        "y": max(box["y"] - 30, 0),
                        "width": min(box["width"] + 60, 1440 - max(box["x"] - 30, 0)),
                        "height": min(box["height"] + 80, 900 - max(box["y"] - 30, 0)),
                    },
                )
            else:
                page.screenshot(path=os.path.join(OUT_DIR, "03_memory_wheel.png"))
            log("saved 03_memory_wheel.png")

        # ── 04 ACTIVE MISSION ──
        if cm.count():
            cm.first.scroll_into_view_if_needed()
            page.wait_for_timeout(700)
            box = cm.first.bounding_box()
            if box:
                page.screenshot(
                    path=os.path.join(OUT_DIR, "04_current_mission.png"),
                    clip={
                        "x": max(box["x"] - 30, 0),
                        "y": max(box["y"] - 30, 0),
                        "width": min(box["width"] + 60, 1440 - max(box["x"] - 30, 0)),
                        "height": min(box["height"] + 60, 900 - max(box["y"] - 30, 0)),
                    },
                )
            else:
                page.screenshot(path=os.path.join(OUT_DIR, "04_current_mission.png"))
            log("saved 04_current_mission.png")
        else:
            page.screenshot(path=os.path.join(OUT_DIR, "04_current_mission.png"))
            log("saved 04_current_mission.png (no mission region found)")

        desktop.close()

        # ── 05 MOBILE 390x844 ──
        mobile = browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True
        )
        mpage = mobile.new_page()
        mpage.on("console", on_console)
        mpage.on("pageerror", on_pageerror)
        mpage.goto(BASE_URL, wait_until="networkidle", timeout=90000)
        try:
            mpage.wait_for_selector(
                '[aria-label="柏韩 记忆系统"], text="Runtime 不可用"',
                timeout=30000,
            )
        except Exception:
            pass
        mpage.wait_for_timeout(2500)
        checks["mobile_topbar_status_texts"] = mpage.locator(
            "[role=status]"
        ).all_inner_texts()
        checks["mobile_wheel_present"] = mpage.locator(
            '[aria-label="柏韩 记忆系统"]'
        ).count() > 0
        checks["mobile_bottom_nav_visible"] = mpage.locator(
            'nav[aria-label="移动导航"]'
        ).is_visible()
        mpage.screenshot(
            path=os.path.join(OUT_DIR, "05_mobile_390x844.png"), full_page=True
        )
        log("saved 05_mobile_390x844.png")
        mobile.close()
        browser.close()

    results["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(os.path.join(OUT_DIR, "evidence_home_v23.json"), "w") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    log(f"evidence written to {OUT_DIR}/evidence_home_v23.json")
    print("=== SUMMARY ===")
    print(
        "console_errors: %d, console_warnings: %d, page_errors: %d"
        % (
            len(results["console_errors"]),
            len(results["console_warnings"]),
            len(results["page_errors"]),
        )
    )
    print("api_requests: %d, api_responses: %d, failed: %d" % (
        len(results["api_requests"]),
        len(results["api_responses"]),
        len(results["failed_requests"]),
    ))
    for k, v in results["checks"].items():
        print(f"  {k}: {v}")
    print("=== END SUMMARY ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        with open(os.path.join(OUT_DIR, "evidence_home_v23.json"), "w") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        raise
