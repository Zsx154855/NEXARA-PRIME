"""NEXARA PRIME Python SDK — first-party Runtime Truth API client."""

from .client import NexaraClient, NexaraError
from .models import (
    ApprovalRequest,
    ApprovalStatus,
    EvidenceArtifact,
    MemoryKind,
    MemoryRecord,
    Mission,
    MissionSpec,
    MissionState,
    PluginManifest,
    RiskLevel,
    RuntimeOverview,
)

__version__ = "0.1.0"
__all__ = [
    "NexaraClient",
    "NexaraError",
    "ApprovalRequest",
    "ApprovalStatus",
    "EvidenceArtifact",
    "MemoryKind",
    "MemoryRecord",
    "Mission",
    "MissionSpec",
    "MissionState",
    "PluginManifest",
    "RiskLevel",
    "RuntimeOverview",
]
