"""T8: every API path the UI calls must exist in the backend.

A static export does not fail on a missing route; it 404s at runtime on a page
that looks finished. This test keeps that gap at zero.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ui"))

import route_truth


def test_no_ui_endpoint_is_missing_from_the_backend():
    data = route_truth.report()
    assert data["missing"] == [], f"UI calls routes the backend does not serve: {data['missing']}"
    assert len(data["ui_endpoints"]) >= 10


def test_known_503_route_is_present_but_module_is_absent():
    # Honest edge: the route exists, the module behind it does not, so the UI
    # shows 503. That is documented in the page, not hidden.
    data = route_truth.report()
    assert "/api/knowledge-universe" in data["backend_routes"]
    assert not (ROOT / "src" / "nexara_prime" / "knowledge_universe.py").exists()
