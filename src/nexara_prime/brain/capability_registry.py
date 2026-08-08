"""CapabilityRegistry — Unified registry for all NEXARA capabilities.

Architecture:
  Capabilities → Registry → Capability Lookup → Permission Check → Execution

Each capability is registered with:
  - Unique ID, version, provider
  - Input/output JSON schemas
  - Risk classification (R0-R4)
  - Required permissions
  - Health status
  - Evidence policy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..models import RiskLevel, new_id, now_iso


class CapabilityHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class Capability:
    """A registered capability in the NEXARA system."""
    capability_id: str
    name: str
    version: str = "1.0.0"
    provider: str = "nexara"
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    risk_class: RiskLevel = RiskLevel.R1
    required_permission: str = "read"
    availability: CapabilityHealth = CapabilityHealth.UNKNOWN
    cost: float = 0.0
    latency_ms: int = 100
    evidence_policy: str = "log_only"
    fallback: str | None = None
    enabled: bool = True
    registered_at: str = field(default_factory=now_iso)


class CapabilityRegistry:
    """Unified registry for discovering and managing capabilities.

    Integrates:
      - Local tools
      - Runtime capabilities
      - Apple adapters
      - Gateway capabilities
      - Model capabilities
      - Agent capabilities
      - Memory capabilities
      - Evidence capabilities
    """

    name = "capability_registry"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._register_builtins()

    def health(self) -> dict[str, Any]:
        return {
            "component": self.name,
            "total_capabilities": len(self._capabilities),
            "healthy": len([c for c in self._capabilities.values() if c.availability == CapabilityHealth.HEALTHY]),
            "degraded": len([c for c in self._capabilities.values() if c.availability == CapabilityHealth.DEGRADED]),
            "unavailable": len([c for c in self._capabilities.values() if c.availability == CapabilityHealth.UNAVAILABLE]),
        }

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, cap: Capability) -> str:
        """Register a new capability. Returns its ID."""
        self._capabilities[cap.capability_id] = cap
        return cap.capability_id

    def unregister(self, capability_id: str) -> bool:
        """Remove a capability from the registry."""
        if capability_id in self._capabilities:
            del self._capabilities[capability_id]
            return True
        return False

    def enable(self, capability_id: str) -> bool:
        cap = self._capabilities.get(capability_id)
        if cap:
            cap.enabled = True
            return True
        return False

    def disable(self, capability_id: str) -> bool:
        cap = self._capabilities.get(capability_id)
        if cap:
            cap.enabled = False
            return True
        return False

    # ── Lookup ───────────────────────────────────────────────────────────────

    def lookup(self, capability_id: str) -> Capability | None:
        """Look up a capability by ID."""
        return self._capabilities.get(capability_id)

    def find_by_name(self, name: str) -> list[Capability]:
        """Find capabilities by name (partial match)."""
        name_lower = name.lower()
        return [c for c in self._capabilities.values() if name_lower in c.name.lower()]

    def find_by_risk(self, max_risk: RiskLevel) -> list[Capability]:
        """Find capabilities at or below a risk level."""
        return [c for c in self._capabilities.values()
                if c.enabled and c.risk_class.value <= max_risk.value]

    def list_all(self) -> list[Capability]:
        """List all registered capabilities."""
        return list(self._capabilities.values())

    def list_available(self) -> list[Capability]:
        """List available (healthy or degraded) capabilities."""
        return [c for c in self._capabilities.values()
                if c.enabled and c.availability in (CapabilityHealth.HEALTHY, CapabilityHealth.DEGRADED)]

    # ── Permission Check ─────────────────────────────────────────────────────

    def can_use(self, capability_id: str, risk_context: RiskLevel) -> bool:
        """Check if a capability can be used at the given risk level."""
        cap = self._capabilities.get(capability_id)
        if cap is None:
            return False
        if not cap.enabled:
            return False
        if cap.availability == CapabilityHealth.UNAVAILABLE:
            return False
        return cap.risk_class.value <= risk_context.value

    # ── Built-in Registration ────────────────────────────────────────────────

    def _register_builtins(self) -> None:
        """Register the standard built-in capabilities."""
        builtins = [
            Capability(
                capability_id="file_read",
                name="File Read",
                description="Read files from the local filesystem",
                risk_class=RiskLevel.R0,
                required_permission="read",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"content": {"type": "string"}}},
            ),
            Capability(
                capability_id="file_write",
                name="File Write",
                description="Write files to the local filesystem",
                risk_class=RiskLevel.R2,
                required_permission="write",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"written": {"type": "boolean"}}},
            ),
            Capability(
                capability_id="terminal_read",
                name="Terminal Read",
                description="Execute read-only shell commands",
                risk_class=RiskLevel.R1,
                required_permission="execute",
                input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"output": {"type": "string"}, "exit_code": {"type": "integer"}}},
            ),
            Capability(
                capability_id="test_execution",
                name="Test Execution",
                description="Run test suites (pytest)",
                risk_class=RiskLevel.R2,
                required_permission="execute",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"passed": {"type": "integer"}, "failed": {"type": "integer"}}},
            ),
            Capability(
                capability_id="build_execution",
                name="Build Execution",
                description="Build projects (xcodebuild, cargo, etc.)",
                risk_class=RiskLevel.R2,
                required_permission="execute",
                input_schema={"type": "object", "properties": {"target": {"type": "string"}, "configuration": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
            ),
            Capability(
                capability_id="model_inference",
                name="Model Inference",
                description="Execute AI model inference via configured provider",
                risk_class=RiskLevel.R2,
                required_permission="execute",
                provider="model_gateway",
                cost=0.01,
                latency_ms=2000,
                input_schema={"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"response": {"type": "string"}, "tokens": {"type": "integer"}}},
            ),
            Capability(
                capability_id="evidence_write",
                name="Evidence Write",
                description="Write evidence records",
                risk_class=RiskLevel.R1,
                required_permission="write",
                input_schema={"type": "object", "properties": {"mission_id": {"type": "string"}, "content": {"type": "object"}}},
                output_schema={"type": "object", "properties": {"evidence_id": {"type": "string"}}},
            ),
            Capability(
                capability_id="memory_read",
                name="Memory Read",
                description="Read from memory layers",
                risk_class=RiskLevel.R0,
                required_permission="read",
                input_schema={"type": "object", "properties": {"mission_id": {"type": "string"}, "layer": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
            ),
            Capability(
                capability_id="memory_write",
                name="Memory Write",
                description="Write to memory layers",
                risk_class=RiskLevel.R2,
                required_permission="write",
                input_schema={"type": "object", "properties": {"mission_id": {"type": "string"}, "content": {"type": "string"}, "kind": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"memory_id": {"type": "string"}}},
            ),
            Capability(
                capability_id="approval_request",
                name="Approval Request",
                description="Request human approval for high-risk actions",
                risk_class=RiskLevel.R3,
                required_permission="approve",
                input_schema={"type": "object", "properties": {"action": {"type": "string"}, "reason": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"approved": {"type": "boolean"}, "approval_id": {"type": "string"}}},
            ),
        ]
        for cap in builtins:
            self.register(cap)
