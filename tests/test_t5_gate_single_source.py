"""T5 acceptance: one derived gate authority, and the other files agree with it."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _derived() -> dict:
    return json.loads((ROOT / ".nexara" / "GATE_STATUS_DERIVED.json").read_text(encoding="utf-8"))


def test_derived_status_is_honest():
    data = _derived()
    statuses = {g["id"]: g["status"] for g in data["gates"]}
    # no dist artifacts in the repository -> G10 cannot be PASS
    assert statuses["G10"] == "BLOCKED"
    # Swift SDK and plugin signature are missing -> G8 cannot be PASS
    assert statuses["G8"] != "PASS"


def test_all_gate_surfaces_agree():
    statuses = {g["id"]: g["status"] for g in _derived()["gates"]}

    gate = json.loads((ROOT / ".nexara" / "GATE_STATUS.json").read_text(encoding="utf-8"))
    assert {g["id"]: g["status"] for g in gate["gates"]} == statuses
    assert gate["authority"] == ".nexara/GATE_STATUS_DERIVED.json"

    program = json.loads((ROOT / ".nexara" / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    assert program["gate_status"] == "PARTIAL_WITH_BLOCKERS"
    assert program["gates_blocked"] == ["G10"]

    yaml_text = (ROOT / "NEXARA_DEVELOPMENT_GATES_V1.yaml").read_text(encoding="utf-8")
    block = re.search(r"- id: G10.*?status: (\w+)", yaml_text, re.DOTALL)
    assert block and block.group(1) == "BLOCKED"
