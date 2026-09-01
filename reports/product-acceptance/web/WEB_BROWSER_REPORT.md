# WEB / BROWSER REPORT (V2)

## Web Runtime
- static_export: ui/out/ (Next.js output:export)
- title: 柏韩 · NEXARA
- root_serve: HTTP 200 (22745 bytes)
- basePath: /console (next.config.ts) — JS chunks served under /console/_next/
- correct_mapping: /console/ -> out/ (verified: HTML 200 + JS 200)

## Browser
- html_load: HTTP 200
- js_assets: HTTP 200 (with correct /console/ mapping)
- root_serve_without_mapping: JS 404 (deployment config note, not code defect)

## Browser Visual
- NOT_VERIFIED: vision provider unavailable (hermes setup needed for vision analysis)

## Finding (P2, deployment)
- basePath=/console requires a reverse proxy / static server mapping /console/ to ui/out/.
- Serving from document root without the /console prefix returns 404 for JS chunks.
