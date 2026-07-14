"""Runtime Truth data models — mirrors NEXARA API contracts."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MissionState(str, Enum):
    DRAFT = "DRAFT"
    CONTEXT_READY = "CONTEXT_READY"
    CONTRACTED = "CONTRACTED"
    PLANNED = "PLANNED"
    SIMULATED = "SIMULATED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class RiskLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class RuntimeOverview(BaseModel):
    system: dict[str, Any] = Field(default_factory=dict)
    missions: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    capabilities: list[dict[str, Any]] = Field(default_factory=list)


class MissionSpec(BaseModel):
    mission_id: str
    title: str
    objective: str
    boundaries: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2


class Mission(BaseModel):
    mission_id: str
    spec: MissionSpec | None = None


class PluginManifest(BaseModel):
    """Plugin manifest schema — capability declaration != authorization."""
    plugin_id: str
    name: str
    version: str
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    network_scope: list[str] = Field(default_factory=list)
    secret_scope: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.R2
    signature_required: bool = True
    isolation: str = "process"  # process | sandbox | none
