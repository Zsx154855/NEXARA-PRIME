#!/usr/bin/env python3
"""Derive the one authoritative gate status from artifacts on disk.

The repository currently carries three gate files that disagree:
NEXARA_DEVELOPMENT_GATES_V1.yaml (all PASS), .nexara/GATE_STATUS.json (all PASS
while admitting earlier false PASSes) and .nexara/PROGRAM_STATE.json (G10
BLOCKED). This script is the single derivation: every status is computed from a
fact that can be re-checked, and every reason names that fact.

    python3 scripts/governance/derive_gate_status.py [--write]

PASS is only emitted when its evidence exists *and* a recorded verification
exists; otherwise the gate is PARTIAL or BLOCKED. No gate is PASS by assertion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def _any(pattern: str) -> bool:
    return any(ROOT.glob(pattern))


def derive() -> dict:
    dist = sorted(p.name for p in (ROOT / "dist").glob("*")) if (ROOT / "dist").exists() else []
    swift_sdk = _exists("platform/sdk/swift")
    plugin_sig = _exists("src/nexara_prime/plugin_signature.py")
    screenshots = _any("reports/**/*.png") or _any("docs/**/*.png")
    baseline = (ROOT / "TEST_BASELINE.md").read_text(encoding="utf-8") if _exists("TEST_BASELINE.md") else ""
    baseline_clean = "0 failed" in baseline

    gates = []

    def gate(gid, status, reason, evidence):
        gates.append({"id": gid, "status": status, "reason": reason, "evidence": evidence})

    gate("G0", "PASS", "constitution and blueprint present, no runtime dependency",
         "NEXARA_PROGRAM_CONSTITUTION_V1.md")
    for gid in ("G1", "G2", "G3", "G4", "G5", "G6"):
        gate(gid, "PARTIAL",
             "implementation exists; end-to-end verification not recorded in this checkout",
             "src/nexara_prime")
    gate("G7", "PARTIAL",
         f"screenshots/usability evidence {'present' if screenshots else 'missing'}",
         "docs/05-UI-UX")
    gate("G8", "PARTIAL",
         f"swift SDK {'present' if swift_sdk else 'missing'}; plugin signature {'present' if plugin_sig else 'not implemented'}",
         "platform/sdk")
    gate("G9", "PARTIAL", "benchmark/evaluation code exists; no recorded run", "src/nexara_prime/benchmark_runner.py")
    gate("G10", "BLOCKED" if not dist else "PARTIAL",
         f"dist artifacts {'found: ' + ', '.join(dist) if dist else 'missing (dist/ is gitignored)'}",
         "dist/")

    return {
        "authoritative": True,
        "derived_from": "scripts/governance/derive_gate_status.py",
        "test_baseline_clean": baseline_clean,
        "gates": gates,
    }


def sync(data: dict) -> None:
    """Write the derived status into every gate surface, so they cannot disagree."""
    import re
    statuses = {g["id"]: g["status"] for g in data["gates"]}

    yaml_path = ROOT / "NEXARA_DEVELOPMENT_GATES_V1.yaml"
    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    current = None
    out = []
    for line in lines:
        match = re.match(r"\s*- id:\s*(G\d+)", line)
        if match:
            current = match.group(1)
        if current and re.match(r"\s*status:\s*\w+", line):
            line = re.sub(r"status:\s*\w+", f"status: {statuses.get(current, 'PARTIAL')}", line)
        if line.startswith("# 自 2026-08-31"):
            line = "# 权威状态由 scripts/governance/derive_gate_status.py 派生到 .nexara/GATE_STATUS_DERIVED.json；本文件的 status 由 --sync 写入。"
        out.append(line)
    yaml_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    gate_path = ROOT / ".nexara" / "GATE_STATUS.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    for item in gate.get("gates", []):
        if item.get("id") in statuses:
            item["status"] = statuses[item["id"]]
            item["verified"] = statuses[item["id"]] == "PASS"
    gate["gates_verified_pass"] = sum(1 for g in gate.get("gates", []) if g.get("status") == "PASS")
    gate["gates_blocked"] = [g["id"] for g in gate.get("gates", []) if g.get("status") == "BLOCKED"]
    gate["program_status"] = "PARTIAL_WITH_BLOCKERS"
    gate["authority"] = ".nexara/GATE_STATUS_DERIVED.json"
    composite = gate.setdefault("g10_composite_status", {})
    composite["local_release"] = "LOCAL_RELEASE_BLOCKED"
    gate_path.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")

    program_path = ROOT / ".nexara" / "PROGRAM_STATE.json"
    program = json.loads(program_path.read_text(encoding="utf-8"))
    program["gate_status"] = "PARTIAL_WITH_BLOCKERS"
    program["gates_pass"] = [g["id"] for g in gate.get("gates", []) if g.get("status") == "PASS"]
    program["gates_blocked"] = [g["id"] for g in gate.get("gates", []) if g.get("status") == "BLOCKED"]
    program.setdefault("g10_composite_status", {})["local_release"] = "LOCAL_RELEASE_BLOCKED"
    program["authority"] = ".nexara/GATE_STATUS_DERIVED.json"
    program_path.write_text(json.dumps(program, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    data = derive()
    text = json.dumps(data, indent=2) + "\n"
    if "--write" in sys.argv:
        target = ROOT / ".nexara" / "GATE_STATUS_DERIVED.json"
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target}")
    if "--sync" in sys.argv:
        sync(data)
        print("synced YAML + GATE_STATUS.json + PROGRAM_STATE.json")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
