#!/usr/bin/env python3
"""Probe dev server routes with Playwright's request API."""
from playwright.sync_api import sync_playwright

paths = ["/", "/console", "/console/", "/nope-123", "/_next/static/chunks/0q-z4_zswx-ab.js"]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context()
    for path in paths:
        try:
            resp = ctx.request.get(f"http://localhost:3000{path}", timeout=15000)
            print(f"{resp.status:>3}  {path}  ({resp.headers.get('content-type','')})")
        except Exception as e:
            print(f"ERR  {path}  {type(e).__name__}: {str(e)[:120]}")
    b.close()
