"""T13: release artifacts must be describable and verifiable."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "release"))

import sbom  # noqa: E402


def test_sbom_is_valid_cyclonedx():
    doc = sbom.build("fastapi==0.110.0\nuvicorn==0.29.0\n# comment\n-e ./local\n")
    assert doc["bomFormat"] == "CycloneDX" and doc["specVersion"] == "1.5"
    names = [c["name"] for c in doc["components"]]
    assert names == ["fastapi", "uvicorn"]
    assert doc["components"][0]["purl"] == "pkg:pypi/fastapi@0.110.0"


def test_sbom_cli_reads_stdin():
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/release/sbom.py")],
                          input="requests==2.31.0\n", capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["components"][0]["name"] == "requests"
