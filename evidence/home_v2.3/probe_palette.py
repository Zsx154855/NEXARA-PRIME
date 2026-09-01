#!/usr/bin/env python3
"""Probe: why did the command palette not open on Meta+K?"""
import json, os, time
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:3000/console"
OUT = "/Users/agentos/NEXARA-PRIME/evidence/home_v2.3"
CHROMIUM = "/Users/agentos/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"

out = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=CHROMIUM)
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    page.goto(BASE_URL, wait_until="networkidle", timeout=90000)
    try:
        page.wait_for_selector('text="Runtime 不可用"', timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(1500)

    def dialog_count():
        return page.locator('[role="dialog"][aria-label="命令面板"]').count()

    # 1) Meta+K
    page.keyboard.press("Meta+K")
    page.wait_for_timeout(1200)
    out["meta_k"] = dialog_count()
    if out["meta_k"]:
        page.keyboard.press("Escape"); page.wait_for_timeout(300)

    # 2) Control+K
    page.keyboard.press("Control+K")
    page.wait_for_timeout(1200)
    out["ctrl_k"] = dialog_count()
    if out["ctrl_k"]:
        page.keyboard.press("Escape"); page.wait_for_timeout(300)

    # 3) Synthetic KeyboardEvent with metaKey (bypasses Playwright keyboard layer)
    out["synthetic_meta_k"] = page.evaluate("""() => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
    }""")
    page.wait_for_timeout(1200)
    out["dialog_after_synthetic"] = dialog_count()

    # 4) Click the TopBar search button
    btn = page.locator('button[aria-label="打开命令面板 (⌘K)"]')
    out["cmdk_button_count"] = btn.count()
    if btn.count():
        btn.click()
        page.wait_for_timeout(1200)
        out["dialog_after_click"] = dialog_count()
        if out["dialog_after_click"]:
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(OUT, "02_command_palette_cmdk.png"))
            pal = page.locator('[role="dialog"][aria-label="命令面板"]')
            out["option_count"] = pal.locator('[role="option"]').count()
            out["options"] = pal.locator('[role="option"]').all_inner_texts()
            page.fill('input[aria-label="搜索 NEXARA"]', "创建")
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(OUT, "02b_command_palette_search.png"))
            out["search_options"] = pal.locator('[role="option"]').all_inner_texts()
            print("PALETTE OPENED VIA CLICK; screenshots 02 + 02b saved")
        else:
            page.screenshot(path=os.path.join(OUT, "02_command_palette_cmdk.png"))
            print("Palette did not open even via click")

    # Focus state of cmd button + any visible overlay text
    out["dialog_any"] = page.locator('[role="dialog"]').count()
    out["body_text_snippet"] = page.locator("body").inner_text()[:400]
    browser.close()

with open(os.path.join(OUT, "palette_probe.json"), "w") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
