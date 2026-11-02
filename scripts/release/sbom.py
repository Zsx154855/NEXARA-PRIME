#!/usr/bin/env python3
"""Emit a CycloneDX 1.5 JSON SBOM from `pip freeze` output on stdin.

    docker run --rm IMAGE python -m pip freeze | python3 scripts/release/sbom.py > SBOM.cdx.json
"""
from __future__ import annotations

import json
import sys
import uuid


def parse(freeze: str) -> list[dict]:
    components = []
    for line in freeze.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-e "):
            continue
        name, _, version = line.partition("==")
        if not version:
            continue
        name = name.split("[")[0]
        components.append({
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name.lower().replace('_', '-')}@{version}",
        })
    return sorted(components, key=lambda item: item["name"].lower())


def build(freeze: str) -> dict:
    components = parse(freeze)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, freeze)}",
        "version": 1,
        "metadata": {"tools": [{"name": "nexara-sbom", "version": "1"}]},
        "components": components,
    }


def main() -> int:
    print(json.dumps(build(sys.stdin.read()), indent=2) + "\n", end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
