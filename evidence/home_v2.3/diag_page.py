#!/usr/bin/env python3
"""Diagnostic: load /console, dump console messages, page errors, and body text."""
import json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000/console"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    console_msgs = []
    page_errors = []
    pg.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    pg.on("pageerror", lambda e: page_errors.append(str(e)))
    pg.goto(BASE, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(8000)
    print("URL:", pg.url)
    print("TITLE:", pg.title())
    body = pg.locator("body").inner_text()
    print("BODY (first 1500):")
    print(body[:1500])
    print("\nCONSOLE:")
    for m in console_msgs[:40]:
        print(" ", m)
    print("\nPAGE ERRORS:")
    for e in page_errors[:10]:
        print(" ", e[:500])
    pg.screenshot(path="/Users/agentos/NEXARA-PRIME/evidence/home_v2.3/diag_page.png")
    b.close()
