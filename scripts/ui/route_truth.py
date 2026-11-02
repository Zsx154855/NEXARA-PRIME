#!/usr/bin/env python3
"""Check that every API path the UI calls exists in the backend.

    python3 scripts/ui/route_truth.py [--write]

The UI is a static export, so a missing route is not a build error — it is a 404
at runtime, on a page that looks finished. This script makes that class of lie
visible. `{param}` and `${expr}` are normalised before comparing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _norm(path: str) -> str:
    # `/api/events/${id}` is a path parameter; `/api/approvals${params}` is a
    # query suffix. Only the former keeps a placeholder.
    path = re.sub(r"/\$\{[^}]*\}", "/{id}", path)
    path = re.split(r"\$\{", path)[0]
    path = re.sub(r"\{[^}]+\}", "{id}", path)
    return path.rstrip("/")


def ui_endpoints() -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "ui" / "src").rglob("*.ts*"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.findall(r"[\"'`](/api/[^\"'`\s]*)", text):
            found.add(_norm(match))
    return found


def backend_routes() -> set[str]:
    text = (ROOT / "src" / "nexara_prime" / "api.py").read_text(encoding="utf-8")
    routes = re.findall(r"@app\.(?:get|post|put|delete|patch)\(\"([^\"]+)\"", text)
    return {_norm(route) for route in routes}


def report() -> dict:
    ui, backend = ui_endpoints(), backend_routes()
    missing = sorted(ui - backend)
    return {
        "ui_endpoints": sorted(ui),
        "backend_routes": sorted(backend),
        "missing": missing,
        "ok": not missing,
        "note": "A missing route here is a runtime 404 on a page that looks done.",
    }


def main() -> int:
    data = report()
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if "--write" in sys.argv:
        target = ROOT / "ui" / "ROUTE_TRUTH.json"
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target}")
    else:
        print(text)
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
