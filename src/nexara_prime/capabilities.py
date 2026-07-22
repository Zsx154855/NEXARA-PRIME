"""Authoritative Capability Registry — NEXARA PRIME converged V2.1.

Single source of truth for capability registration, resolution, scoring,
and evidence tracking.  Formerly capabilities.py (V1) + capability_registry_v2.py
were two separate registries.  This module now contains both APIs in one class.

Version: 2.0 (converged from capabilities.py + capability_registry_v2.py)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import Capability, CapabilityScore, CapabilityType, RiskLevel, now_iso


class CapabilityRegistry:
    """Authoritative capability registry for NEXARA PRIME.

    Provides:
    - Static capability registration (retained from V1)
    - Evidence-scored capability tracking (merged from V2)
    - Decay and confidence gating (merged from V2)
    """

    def __init__(self) -> None:
        # ── V1 fields ──
        self._capabilities: dict[str, Capability] = {}
        self._mounted: dict[str, set[str]] = {}

        # ── V2 fields (evidence-scored) ──
        self._scores: dict[str, CapabilityScore] = {}
        self._mission_history: dict[str, list[dict[str, Any]]] = {}

        self._register_defaults()

    # ── V1 API (registration / resolution / mount) ──────────────────

    def register(self,
                 capability: Capability | str | None = None,
                 capability_id: str | None = None,
                 name: str | None = None,
                 supported_task_types: list[str] | None = None,
                 tool_permissions: list[str] | None = None,
                 risk_ceiling: str = RiskLevel.R1.value,
                 model_requirements: list[str] | None = None) -> Capability | CapabilityScore:
        """Register a capability — V1 (Capability object) or V2 (str id+name) API.

        When called with a Capability object: uses V1 API.
        When called with string args: uses V2 scored API.
        """
        # V2 path: string-style registration
        if isinstance(capability, str):
            cap_id = capability
            cap_name = capability_id or cap_id  # capability_id param reused as name in V2 call
            return self.register_v2(
                capability_id=cap_id,
                name=cap_name if isinstance(cap_name, str) else cap_id,
                supported_task_types=supported_task_types,
                tool_permissions=tool_permissions,
                risk_ceiling=risk_ceiling,
                model_requirements=model_requirements,
            )

        # V1 path: object registration
        if isinstance(capability, Capability):
            self._capabilities[capability.capability_id] = capability
            return capability

        raise TypeError("register() requires a Capability object or string capability_id")

    def _register_defaults(self) -> None:
        defaults = [
            Capability(capability_id="skill.mission_compilation", name="Mission Compilation", capability_type=CapabilityType.SKILL, description="Compile human intent into bounded MissionSpec."),
            Capability(capability_id="skill.contracts", name="Contract Engine", capability_type=CapabilityType.SKILL, description="Version and validate WorkContract."),
            Capability(capability_id="skill.evidence", name="Evidence Chain", capability_type=CapabilityType.SKILL, description="Attach evidence to state and tool events."),
            Capability(capability_id="tool.file_read", name="Read Local Files", capability_type=CapabilityType.TOOL, description="Read files under the approved workspace root.", risk_level=RiskLevel.R0),
            Capability(capability_id="tool.file_write_report", name="Write Local Report", capability_type=CapabilityType.TOOL, description="Write a bounded report under the report root.", risk_level=RiskLevel.R2),
            Capability(capability_id="tool.code_exec", name="Controlled Code Execution", capability_type=CapabilityType.TOOL, description="Run allow-listed local Python commands.", risk_level=RiskLevel.R1),
            Capability(capability_id="tool.browser_readonly", name="Browser Read Only", capability_type=CapabilityType.TOOL, description="Placeholder for read-only browser access.", risk_level=RiskLevel.R1),
            Capability(capability_id="model.mock", name="Deterministic Mock Model", capability_type=CapabilityType.MODEL, description="Provider-free deterministic model for tests."),
            Capability(capability_id="model.provider", name="Configured Model Provider", capability_type=CapabilityType.MODEL, description="A configured non-mock model provider with durable usage metadata."),
            Capability(capability_id="memory.sqlite", name="SQLite Memory", capability_type=CapabilityType.MEMORY, description="Short-term, fact, decision, failure and patch memory."),
            Capability(capability_id="policy.risk", name="Risk Policy", capability_type=CapabilityType.POLICY, description="R0-R4 policy and approval gates."),
        ]
        for capability in defaults:
            self.register(capability)

    def resolve(self, required: list[str]) -> list[Capability]:
        resolved = []
        for name in required:
            capability = self._capabilities.get(name) or next((c for c in self._capabilities.values() if c.name == name), None)
            if capability and capability.enabled:
                resolved.append(capability)
        return resolved

    def mount_for(self, worker_id: str, required: list[str]) -> list[str]:
        loaded = [item.capability_id for item in self.resolve(required)]
        self._mounted[worker_id] = set(loaded)
        return loaded

    def unmount_for(self, worker_id: str) -> None:
        self._mounted.pop(worker_id, None)

    def mounted(self, worker_id: str) -> list[str]:
        return sorted(self._mounted.get(worker_id, set()))

    def list(self) -> list[dict]:
        return [c.model_dump(mode="json") for c in self._capabilities.values()]

    # ── V2 API (evidence-scored registration / update / query / decay) ──

    def register_v2(
        self,
        capability_id: str,
        name: str,
        supported_task_types: list[str] | None = None,
        tool_permissions: list[str] | None = None,
        risk_ceiling: str = RiskLevel.R1.value,
        model_requirements: list[str] | None = None,
    ) -> CapabilityScore:
        """Register a new evidence-scored capability."""
        score = CapabilityScore(
            capability_id=capability_id,
            name=name,
            supported_task_types=supported_task_types or [],
            tool_permissions=tool_permissions or [],
            risk_ceiling=risk_ceiling,
            model_requirements=model_requirements or [],
            historical_success_rate=0.0,
            average_latency_ms=0.0,
            average_token_cost=0.0,
            recent_failure_rate=0.0,
            confidence=0.5,
            evidence_count=0,
            last_updated=now_iso(),
            source_evidence=[],
            schema_version=2,
        )
        self._scores[capability_id] = score
        self._mission_history[capability_id] = []
        return score

    def update_score(
        self,
        capability_id: str,
        mission_success: bool,
        latency_ms: float,
        token_cost: float,
        evidence_ids: list[str] | None = None,
    ) -> CapabilityScore | None:
        """Update capability score from real mission outcomes."""
        score = self._scores.get(capability_id)
        if score is None:
            return None

        evidence_ids = evidence_ids or []

        outcome: dict[str, Any] = {
            "success": mission_success,
            "latency_ms": latency_ms,
            "token_cost": token_cost,
            "evidence_ids": evidence_ids,
            "timestamp": now_iso(),
        }
        self._mission_history.setdefault(capability_id, []).append(outcome)

        history = self._mission_history[capability_id]
        total_missions = len(history)
        successes = sum(1 for o in history if o["success"])
        score.historical_success_rate = successes / total_missions if total_missions > 0 else 0.0

        recent = history[-10:]
        recent_failures = sum(1 for o in recent if not o["success"])
        score.recent_failure_rate = recent_failures / len(recent) if recent else 0.0

        all_latencies = [o["latency_ms"] for o in history]
        score.average_latency_ms = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0

        all_costs = [o["token_cost"] for o in history]
        score.average_token_cost = sum(all_costs) / len(all_costs) if all_costs else 0.0

        new_evidence = [eid for eid in evidence_ids if eid not in score.source_evidence]
        score.evidence_count += len(new_evidence)
        score.source_evidence.extend(new_evidence)

        if score.evidence_count >= 3:
            score.confidence = min(score.evidence_count / 10.0, 1.0)
        else:
            score.confidence = max(0.3, score.evidence_count * 0.1)

        score.last_updated = now_iso()
        return score

    def _apply_decay(self, score: CapabilityScore) -> None:
        try:
            last = datetime.fromisoformat(score.last_updated)
        except (ValueError, TypeError):
            return

        now = datetime.now(timezone.utc)
        days_since_update = (now - last).total_seconds() / 86400.0

        if days_since_update > 7.0:
            days_overdue = days_since_update - 7.0
            decay = days_overdue * 0.1
            score.confidence = max(0.1, score.confidence - decay)

    def get_score(self, capability_id: str) -> CapabilityScore | None:
        score = self._scores.get(capability_id)
        if score is None:
            return None
        self._apply_decay(score)
        return score

    def list_capable(self, task_type: str, min_confidence: float = 0.5) -> list[CapabilityScore]:
        results: list[CapabilityScore] = []
        for score in self._scores.values():
            self._apply_decay(score)
            if task_type.lower() in (tt.lower() for tt in score.supported_task_types):
                if score.confidence >= min_confidence:
                    results.append(score)
        results.sort(key=lambda s: (s.confidence, s.historical_success_rate), reverse=True)
        return results

    def list_all(self) -> list[CapabilityScore]:
        for score in self._scores.values():
            self._apply_decay(score)
        return list(self._scores.values())

    def get_mission_history(self, capability_id: str) -> list[dict[str, Any]]:
        return self._mission_history.get(capability_id, [])


# ── DEPRECATED compat alias (for backwards-compatibility) ──
# capability_registry_v2.CapabilityRegistryV2 redirected here.
# Remove this alias in next major release (v0.2.0+).
CapabilityRegistryV2 = CapabilityRegistry
