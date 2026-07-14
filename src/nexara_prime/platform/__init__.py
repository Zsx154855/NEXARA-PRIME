"""NEXARA PRIME — Platform Runtime Services.

Per Blueprint §7 recommendation: Platform services provide the capability,
policy, telemetry, knowledge, identity, and evidence layers that the
first-party Agent Domain uses to execute missions.

These services are running Python modules — not YAML manifests, not stubs.
Each service is independently testable and has a defined API surface.

Services:
- capability: CapabilityRegistry — register, resolve, health, dependencies
- policy: PolicyEngine — R0-R4 risk gating, approval binding
- telemetry: EventBus — mission/task/provider/token/cost/approval observation
- knowledge: KnowledgeUniverse — vault scanning, search index
- identity: IdentityStore — user, device, session, agent identity
- evidence: EvidenceLedger — immutable evidence envelope, hash chain, audit
"""

from nexara_prime.capability_registry_v2 import CapabilityRegistryV2 as CapabilityRegistry
from nexara_prime.events import EventBus
from nexara_prime.governance import PolicyEngine  # noqa: F401 — re-export
from nexara_prime.identity import IdentityStore
from nexara_prime.network_policy import NetworkPolicyEngine
from nexara_prime.governance import PolicyEngine, ApprovalEngine

__all__ = [
    "CapabilityRegistry",
    "EventBus",
    "IdentityStore",
    "NetworkPolicyEngine",
    "PolicyEngine",
    "ApprovalEngine",
]
