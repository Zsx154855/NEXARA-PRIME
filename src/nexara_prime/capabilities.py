from __future__ import annotations

from .models import Capability, CapabilityType, RiskLevel


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._mounted: dict[str, set[str]] = {}
        self._register_defaults()

    def register(self, capability: Capability) -> Capability:
        self._capabilities[capability.capability_id] = capability
        return capability

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
