"""Minimal goal discovery from real evidence (COGNITIVE-AUTONOMY-01, stages A/B).

Signals are collected from real sources (Runtime mission records, pytest JUnit
XML, QA review markdown). Goals are generated per signal by rules, not from a
prewritten candidate list, then ranked with explicit factors and an auditable
decision artifact. No model calls and no second SQLite authority.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

_QA_PATTERN = re.compile(
    r"(?:^|[\s\[(])(nit|risk|blocked|med|high|low)(?=[\s:.,\]\)]|$)|未决|风险|阻塞",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Signal:
    source: str
    kind: str
    subject: str
    detail: str
    severity: str


@dataclass(frozen=True)
class GoalCandidate:
    goal_id: str
    objective: str
    source: str
    kind: str
    success_criteria: str
    value_hypothesis: str
    risk: str
    estimated_cost: str
    dependencies: tuple[str, ...]
    evidence: str


def signals_from_runtime_missions(missions: Iterable[dict[str, Any]]) -> list[Signal]:
    signals: list[Signal] = []
    for mission in missions:
        state = str(mission.get("state", ""))
        if state not in {"Failed", "Blocked"}:
            continue
        mission_id = str(mission.get("mission_id", ""))
        spec = mission.get("spec", {}) if isinstance(mission.get("spec"), dict) else {}
        result = mission.get("result", {}) if isinstance(mission.get("result"), dict) else {}
        recovery = result.get("recovery")
        recovery_code = recovery.get("error_code") if isinstance(recovery, dict) else None
        error = result.get("error") or recovery_code or state
        signals.append(Signal(
            source=f"runtime:mission:{mission_id}",
            kind="mission_failure",
            subject=str(spec.get("objective") or mission_id),
            detail=f"state={state} error={error}",
            severity="high" if state == "Failed" else "medium",
        ))
    return signals


def signals_from_qa_markdown(path: Path, *, max_signals: int = 50) -> list[Signal]:
    signals: list[Signal] = []
    if not Path(path).exists():
        return signals
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text.startswith(("-", "*")):
            continue
        lowered = text.lower()
        if not _QA_PATTERN.search(lowered):
            continue
        severity = "high" if ("block" in lowered or "high" in lowered or "阻塞" in lowered) else "medium"
        signals.append(Signal(
            source=str(path), kind="qa_finding",
            subject=text[:140], detail=text[:500], severity=severity,
        ))
        if len(signals) >= max_signals:
            break
    return signals


def signals_from_junit(path: Path) -> list[Signal]:
    signals: list[Signal] = []
    if not Path(path).exists():
        return signals
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return signals
    for case in root.iter("testcase"):
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        if failure is None:
            continue
        name = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
        message = (failure.get("message") or (failure.text or "")).strip()[:500]
        signals.append(Signal(
            source=str(path), kind="test_failure", subject=name,
            detail=message or "test failed", severity="high",
        ))
    return signals


def propose_goals(signals: Iterable[Signal]) -> list[GoalCandidate]:
    goals: list[GoalCandidate] = []
    for index, signal in enumerate(signals):
        prefix = f"G{index + 1:03d}"
        if signal.kind == "mission_failure":
            objective = f"Diagnose and fix failed mission objective: {signal.subject}"
            criteria = "root cause identified; mission rerun succeeds or failure is documented"
        elif signal.kind == "test_failure":
            objective = f"Repair failing test: {signal.subject}"
            criteria = "targeted test passes; no regression in full suite"
        elif signal.kind == "qa_finding":
            objective = f"Resolve QA finding: {signal.subject}"
            criteria = "finding addressed with a regression test or explicit accepted-risk decision"
        else:
            continue
        goals.append(GoalCandidate(
            goal_id=prefix, objective=objective, source=signal.source,
            kind=signal.kind, success_criteria=criteria,
            value_hypothesis=f"removes a {signal.severity}-severity blocker from {signal.kind}",
            risk="scope creep" if signal.kind != "test_failure" else "flaky test",
            estimated_cost="small (local edits + tests)",
            dependencies=("repository baseline",),
            evidence=signal.detail,
        ))
    return goals


def _factors(candidate: GoalCandidate) -> dict[str, float]:
    value = 0.9 if candidate.kind in {"mission_failure", "test_failure"} else 0.6
    feasibility = 0.9 if candidate.kind == "test_failure" else 0.7
    info_gain = 0.8 if "error" in candidate.evidence.lower() else 0.4
    dependency_unlock = 0.6 if candidate.kind == "mission_failure" else 0.3
    cost = 0.2
    score = round(
        value * 0.4 + feasibility * 0.3 + info_gain * 0.2
        + dependency_unlock * 0.1 - cost * 0.1, 4,
    )
    return {
        "value": value, "feasibility": feasibility,
        "information_gain": info_gain, "dependency_unlock": dependency_unlock,
        "cost_penalty": cost, "score": score,
    }


def rank_goals(candidates: Iterable[GoalCandidate]) -> list[dict[str, Any]]:
    ranked = []
    for candidate in candidates:
        ranked.append({"candidate": asdict(candidate), "factors": _factors(candidate)})
    ranked.sort(
        key=lambda item: (
            -item["factors"]["score"],
            item["candidate"]["goal_id"],
        )
    )
    return ranked


def select_goal(candidates: Iterable[GoalCandidate]) -> dict[str, Any]:
    ranked = rank_goals(candidates)
    if not ranked:
        return {"selected": None, "rejected": [], "rationale": "no signals"}
    top = ranked[0]
    rationale = (
        f"selected {top['candidate']['goal_id']} for highest score "
        f"{top['factors']['score']} (value={top['factors']['value']}, "
        f"feasibility={top['factors']['feasibility']}, "
        f"info_gain={top['factors']['information_gain']})"
    )
    return {
        "selected": top["candidate"], "factors": top["factors"],
        "rejected": [item["candidate"]["goal_id"] for item in ranked[1:]],
        "rationale": rationale,
    }


def record_decision(path: Path, decision: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8")
    return target
