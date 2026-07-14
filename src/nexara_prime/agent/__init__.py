"""NEXARA PRIME — First-Party Agent Domain.

Per Blueprint §7: Agent Identity, Mission, Context, Contract, Planning,
Orchestration, Capability Registry, Policy & Approval, Execution,
Verification, Evidence & Audit, Memory & Knowledge, Evaluation & Evolution.

All modules here depend on Platform Service interfaces to reach the Kernel.
No direct dependency on Hermes, Claude, Codex, or external agent SDKs.
"""

from nexara_prime.identity import AgentIdentity, AGENT_DEFAULT_PERMISSIONS

__all__ = ["AgentIdentity", "AGENT_DEFAULT_PERMISSIONS"]
