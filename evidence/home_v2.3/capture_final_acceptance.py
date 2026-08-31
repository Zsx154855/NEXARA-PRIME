#!/usr/bin/env python3
"""
NEXARA Home V2.3 — Final Runtime UI Acceptance Capture.

Drives the real NEXARA Control Console (Next.js dev at localhost:3000/console,
backend at 127.0.0.1:8766) with Playwright and produces:

Screenshots -> /Users/agentos/NEXARA-PRIME/evidence/home_v2.3/
  FINAL_01_home_desktop.png  (1440x900 viewport, home)
  FINAL_02_palette.png       (command palette open, desktop)
  FINAL_03_memory_wheel.png  (clip to MemoryWheel region)
  FINAL_04_mission.png       (clip to CurrentMission region)
  FINAL_05_mobile.png        (390x844 viewport, home)

Diagnostics -> evidence_final.json
  - console errors / warnings, page errors
  - all /api/* requests with method, URL, status
  - programmatic UI checks (sidebar brand, wheel quadrants, center label,
    mission card, palette, duplicate "继续任务", API base URL target)
  - /api/memory/stats status + quadrant counts vs. wheel aria-labels
"""

import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

OUT_DIR = Path("/Users/agentos/NEXARA-PRIME/evidence/home_v2.3")
BASE_URL = "http://localhost:3000/console"
API_BASE = "http://127.0.0.1:8766"

WHEEL_SEL = '[aria-label="柏韩 记忆系统"]'
PALETTE_BTN_SEL = '[aria-label="打开命令面板 (⌘K)"]'
PALETTE_SEL = '[role="dialog"][aria-label="命令面板"]'
MISSION_SEL = '[aria-label^="当前使命"]'

QUADRANT_LABEL_MAP = {
    "感知记忆": "perceptual",
    "程序记忆": "procedural",
    "世界记忆": "world",
    "关系记忆": "relational",
}
# wheel labels -> memory stats layers mapping used by the UI
LABEL_TO_LAYER = {
    "感知记忆": "working",
    "程序记忆": "procedural",
    "世界记忆": "semantic",
    "关系记忆": "episodic",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class SessionCapture:
    """Collects console/page/network events for one page."""

    def __init__(self, tag: str):
        self.tag = tag
        self.console_errors = []
        self.console_warnings = []
        self.console_logs = []
        self.page_errors = []
        self.api_requests = []   # {method, url, session}
        self.api_responses = []  # {method, url, status, session}
        self.api_failures = []   # {url, error, session}
        self.memory_stats_body = None
        self._seen_requests = {}

    def attach(self, page):
        def on_console(msg):
            entry = {"type": msg.type, "text": msg.text, "url": msg.location.get("url", "")}
            if msg.type == "error":
                self.console_errors.append(entry)
            elif msg.type == "warning":
                self.console_warnings.append(entry)
            else:
                self.console_logs.append(entry)

        def on_pageerror(err):
            self.page_errors.append({"text": str(err)})

        def on_request(req):
            if "/api/" in req.url:
                self.api_requests.append(
                    {"method": req.method, "url": req.url, "session": self.tag}
                )
                self._seen_requests[req.url] = req.method

        def on_response(res):
            if "/api/" in res.url:
                self.api_responses.append(
                    {
                        "method": res.request.method,
                        "url": res.url,
                        "status": res.status,
                        "session": self.tag,
                    }
                )
                if res.url.rstrip("/").endswith("/api/memory/stats") and res.ok:
                    try:
                        body = res.json()
                        if isinstance(body, dict):
                            self.memory_stats_body = json.dumps(
                                body, ensure_ascii=False, default=str
                            )[:4000]
                    except Exception:  # noqa: BLE001
                        self.memory_stats_body = "<unparseable body>"

        def on_requestfailed(req):
            if "/api/" in req.url:
                self.api_failures.append(
                    {"url": req.url, "error": req.failure or "unknown", "session": self.tag}
                )

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_requestfailed)


def goto_and_settle(page, timeout_ms: int = 60_000):
    for attempt in (1, 2):
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except PWTimeoutError:
            pass  # polling may keep the network busy; settle below instead
        try:
            page.wait_for_selector(WHEEL_SEL, state="visible", timeout=30_000)
            break
        except PWTimeoutError:
            if attempt == 1:
                page.reload()
                continue
            raise
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeoutError:
        pass
    page.wait_for_timeout(700)  # let fade-in finish


def collect_ui_checks(page, cap: SessionCapture) -> dict:
    checks = {}

    # 1. Sidebar brand
    brand = page.get_by_text("Nexara-柏韩", exact=True)
    checks["sidebar_brand"] = {
        "expected": "Nexara-柏韩",
        "present": brand.count() > 0,
        "visible": brand.first.is_visible() if brand.count() else False,
        "text": brand.first.text_content() if brand.count() else None,
    }

    # 2. Memory wheel
    wheel = page.locator(WHEEL_SEL)
    wheel_present = wheel.count() > 0
    quadrants = []
    center_labels = []
    if wheel_present:
        for btn in wheel.locator("button").all():
            label = btn.get_attribute("aria-label") or ""
            text = (btn.text_content() or "").strip()
            quadrants.append({"aria_label": label, "text": text})
        center = wheel.locator("span")
        center_labels = [(el.text_content() or "").strip() for el in center.all() if el.is_visible()]
    checks["wheel"] = {
        "present": wheel_present,
        "aria_label": wheel.get_attribute("aria-label") if wheel_present else None,
        "quadrant_count": len(quadrants),
        "expected_quadrant_count": 4,
        "quadrants": quadrants,
        "center_visible_texts": center_labels,
        "center_contains_柏韩": any(t == "柏韩" for t in center_labels),
    }

    # 3. Mission card
    mission = page.locator(MISSION_SEL)
    mission_present = mission.count() > 0
    checks["mission_card"] = {
        "present": mission_present,
        "aria_label": mission.first.get_attribute("aria-label") if mission_present else None,
        "visible": mission.first.is_visible() if mission_present else False,
    }

    # 4. Duplicate "继续任务" on the home view (palette closed)
    continue_all = page.get_by_text("继续任务", exact=True)
    checks["continue_task"] = {
        "dom_count_palette_closed": continue_all.count(),
        "expected_max_1_on_home": 1,
    }

    return checks


def open_palette_and_check(page, cap: SessionCapture) -> dict:
    out = {}
    btn = page.locator(PALETTE_BTN_SEL)
    out["palette_button"] = {
        "present": btn.count() > 0,
        "visible": btn.first.is_visible() if btn.count() else False,
    }
    btn.first.click()
    try:
        page.wait_for_selector(PALETTE_SEL, state="visible", timeout=10_000)
        out["opened"] = True
    except PWTimeoutError:
        out["opened"] = False
        out["error"] = "dialog did not open"
        return out
    page.wait_for_timeout(600)

    dialog = page.locator(PALETTE_SEL)
    continue_in_palette = dialog.get_by_text("继续任务", exact=True)
    out["continue_task_in_palette_count"] = continue_in_palette.count()
    out["palette_groups"] = [el.text_content().strip() for el in dialog.locator("div").all() if False]
    # list result titles (role=option) for the record
    options = dialog.locator('[role="option"]')
    out["option_count"] = options.count()
    out["options"] = [(o.get_attribute("aria-selected"), (o.text_content() or "").replace("\n", " | ")) for o in options.all()]
    # close
    page.keyboard.press("Escape")
    try:
        page.wait_for_selector(PALETTE_SEL, state="hidden", timeout=5_000)
        out["closed_on_escape"] = True
    except PWTimeoutError:
        out["closed_on_escape"] = False
    page.wait_for_timeout(400)
    return out


def wheel_quadrant_counts(page) -> list:
    """Extract counts from quadrant aria-labels, e.g. '感知记忆 · 42 条记录'."""
    out = []
    wheel = page.locator(WHEEL_SEL)
    for btn in wheel.locator("button").all():
        label = btn.get_attribute("aria-label") or ""
        m = re.search(r"([\d,]+)\s*条记录", label)
        name = next((n for n in QUADRANT_LABEL_MAP if label.startswith(n)), label)
        out.append({"quadrant": name, "count": int(m.group(1).replace(",", "")) if m else None})
    return out


def screenshot_clip(page, locator_sel, path: Path):
    loc = page.locator(locator_sel)
    if loc.count() == 0:
        return {"path": str(path), "taken": False, "reason": "locator not found"}
    box = loc.first.bounding_box()
    if not box:
        return {"path": str(path), "taken": False, "reason": "no bounding box"}
    page.screenshot(path=str(path), clip=box)
    return {"path": str(path), "taken": True, "clip": box}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = now_iso()
    result = {
        "started_at": started,
        "base_url": BASE_URL,
        "api_base_url": API_BASE,
        "console_errors": [],
        "console_warnings": [],
        "page_errors": [],
        "api_requests": [],
        "api_responses": [],
        "api_failures": [],
        "memory_stats": None,
        "checks": {},
        "screenshots": {},
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # ── Desktop session ──
            desktop_ctx = browser.new_context(
                viewport={"width": 1440, "height": 900}, device_scale_factor=1,
            )
            page = desktop_ctx.new_page()
            cap = SessionCapture("desktop")
            cap.attach(page)
            goto_and_settle(page)
            page.wait_for_timeout(500)

            # Screenshot 01: home desktop
            shot01 = str(OUT_DIR / "FINAL_01_home_desktop.png")
            page.screenshot(path=shot01)
            result["screenshots"]["01_home_desktop"] = {"path": shot01, "taken": True}

            # UI checks before palette
            checks = collect_ui_checks(page, cap)
            result["checks"].update(checks)

            # Screenshot 02: palette open
            palette_out = open_palette_and_check(page, cap)
            result["checks"]["command_palette"] = palette_out
            shot02 = str(OUT_DIR / "FINAL_02_palette.png")
            page.screenshot(path=shot02)
            result["screenshots"]["02_palette"] = {"path": shot02, "taken": True}

            # Screenshot 03: memory wheel clip
            result["screenshots"]["03_memory_wheel"] = screenshot_clip(
                page, WHEEL_SEL, OUT_DIR / "FINAL_03_memory_wheel.png"
            )

            # Screenshot 04: mission clip
            result["screenshots"]["04_mission"] = screenshot_clip(
                page, MISSION_SEL, OUT_DIR / "FINAL_04_mission.png"
            )

            # Quadrant counts from the live DOM
            result["checks"]["wheel_quadrant_counts"] = wheel_quadrant_counts(page)

            # API target verification (requests observed on desktop session)
            api_urls = [r["url"] for r in cap.api_requests]
            api_base = [u for u in api_urls if u.startswith(API_BASE)]
            wrong_base = [u for u in api_urls if not u.startswith(API_BASE)]
            result["checks"]["api_base_url_target"] = {
                "all_api_requests_target_127_0_0_1_8766": len(api_urls) == len(api_base) and len(api_urls) > 0,
                "count_127_0_0_1_8766": len(api_base),
                "count_other": len(wrong_base),
                "other_urls": wrong_base[:10],
                "observed_api_urls": sorted(set(api_urls)),
            }

            # /api/memory/stats verification (grab last response body)
            mem_responses = [
                r for r in cap.api_responses
                if r["url"].endswith("/api/memory/stats")
            ]
            if mem_responses:
                latest = mem_responses[-1]
                result["checks"]["memory_stats_endpoint"] = {
                    "last_status": latest["status"],
                    "requested": True,
                }
            else:
                result["checks"]["memory_stats_endpoint"] = {
                    "last_status": None,
                    "requested": False,
                }

            # Live memory stats body (fetch while the page is still open)
            try:
                stats = page.evaluate(
                    "async (u) => { const r = await fetch(u); let b = null; "
                    "try { b = await r.json(); } catch (e) {} "
                    "return {status: r.status, body: b}; }",
                    f"{API_BASE}/api/memory/stats",
                )
                result["memory_stats"] = stats
            except Exception as exc:  # noqa: BLE001
                result["memory_stats"] = {"error": str(exc)}
            if result["memory_stats"].get("body") is None and cap.memory_stats_body:
                try:
                    result["memory_stats"] = {
                        "status": 200,
                        "body": json.loads(cap.memory_stats_body),
                        "source": "response-capture",
                    }
                except Exception:  # noqa: BLE001
                    pass

            page.close()
            desktop_ctx.close()

            # ── Mobile session ──
            mobile_ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=1,
                is_mobile=True,
                has_touch=True,
            )
            mpage = mobile_ctx.new_page()
            mcap = SessionCapture("mobile")
            mcap.attach(mpage)
            goto_and_settle(mpage)
            mpage.wait_for_timeout(500)
            shot05 = str(OUT_DIR / "FINAL_05_mobile.png")
            mpage.screenshot(path=shot05)
            result["screenshots"]["05_mobile"] = {"path": shot05, "taken": True}
            result["checks"]["mobile"] = {
                "wheel_present": mpage.locator(WHEEL_SEL).count() > 0,
                "mobile_bottom_nav_present": mpage.locator('[aria-label="移动导航"]').count() > 0,
                "brand_present": mpage.get_by_text("Nexara-柏韩", exact=True).count() > 0,
            }
            mpage.close()
            mobile_ctx.close()
            browser.close()

            # ── Merge event logs ──
            for cap in (cap, mcap):
                for e in cap.console_errors:
                    e["session"] = cap.tag
                    result["console_errors"].append(e)
                for e in cap.console_warnings:
                    e["session"] = cap.tag
                    result["console_warnings"].append(e)
                for e in cap.page_errors:
                    e["session"] = cap.tag
                    result["page_errors"].append(e)
                for r in cap.api_requests:
                    result["api_requests"].append(r)
                for r in cap.api_responses:
                    result["api_responses"].append(r)
                for f in cap.api_failures:
                    result["api_failures"].append(f)

            # Cross-check quadrant counts vs /api/memory/stats layers
            ms = (result["memory_stats"] or {}).get("body") or {}
            layers = ms.get("layers") if isinstance(ms, dict) else None
            dom_counts = result["checks"].get("wheel_quadrant_counts", [])
            matched = True
            layer_values = {}
            if layers:
                layer_values = {
                    k: layers.get(k) for k in ("working", "procedural", "semantic", "episodic")
                }
                for item in dom_counts:
                    want = layer_values.get(LABEL_TO_LAYER.get(item["quadrant"]))
                    if want is not None and item["count"] != want:
                        matched = False
            result["checks"]["quadrant_counts_match_api"] = {
                "match": matched,
                "api_layers": layer_values,
                "dom_quadrants": dom_counts,
            }

            # Duplicate 继续任务 final assessment
            cont = result["checks"].get("continue_task", {})
            result["checks"]["continue_task"]["verdict"] = (
                "no duplicate" if cont.get("dom_count_palette_closed", 0) <= 1 else "DUPLICATE FOUND"
            )

    except Exception as exc:  # noqa: BLE001
        result["runtime_error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        # Diagnose the page state at failure time, if any page is alive
        try:
            cur_page = page
            result["failure_page"] = {
                "url": cur_page.url,
                "title": cur_page.title(),
                "body_text_prefix": (cur_page.locator("body").inner_text() or "")[:1500],
            }
            try:
                cur_page.screenshot(
                    path=str(OUT_DIR / "FINAL_00_failure_diag.png"), full_page=True
                )
                result["failure_page"]["screenshot"] = str(
                    OUT_DIR / "FINAL_00_failure_diag.png"
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass

    result["finished_at"] = now_iso()
    out_json = OUT_DIR / "evidence_final.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {out_json}")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
    return 0 if "runtime_error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
