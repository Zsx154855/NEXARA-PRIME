"""Identity & Authorization Foundation — local-first, no premature multi-tenancy."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Set

from .models import new_id, now_iso


class Role(str, enum.Enum):
    LOCAL_OWNER = "local-owner"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"
    READ_ONLY = "read-only"


@dataclass
class UserIdentity:
    user_id: str = field(default_factory=lambda: "local-owner")
    name: str = "Local Owner"
    roles: list[Role] = field(default_factory=lambda: [Role.LOCAL_OWNER])
    created_at: str = field(default_factory=now_iso)


@dataclass
class DeviceIdentity:
    device_id: str = field(default_factory=lambda: new_id('evt'))
    hostname: str = ""
    platform: str = ""
    trusted: bool = True
    created_at: str = field(default_factory=now_iso)


@dataclass
class SessionIdentity:
    session_id: str = field(default_factory=lambda: new_id('evt'))
    user_id: str = ""
    device_id: str = ""
    created_at: str = field(default_factory=now_iso)
    expires_at: str = ""
    is_active: bool = True
    is_agent: bool = False  # Agent sessions have reduced permissions


@dataclass
class AgentIdentity:
    """First-party sovereign agent identity — model-independent.

    Per Constitution §4 and Blueprint §7: agent_id, product principles,
    capability profile, permission profile, memory namespace, and version
    are owned by the platform. Models are replaceable reasoning resources
    that do NOT own any part of this identity.
    """
    agent_id: str = "nexara_prime.agent"
    display_name: str = "NEXARA"
    product_principles: list[str] = field(default_factory=lambda: [
        "Human sovereignty — user owns goals, approval, takeover, revocation",
        "First-party identity — agent_id, memory namespace, evolution history owned by platform",
        "Model independence — models are replaceable reasoning resources",
        "Runtime Truth — UI displays authoritative state only",
        "Evidence before Completion — no E1/E2 evidence means not complete",
        "Single Writer — one writer lease per mutable resource",
        "Policy before Capability — capability available ≠ authorized to execute",
        "Evolution by Experiment — proposal → simulate → benchmark → approve → deploy → rollback",
        "Local-first — default local persistence, cloud is optional migration",
        "Hermes dependency = 0 — product runtime, tests, packaging never require Hermes",
    ])
    capability_profile: list[str] = field(default_factory=lambda: [
        "mission.compile", "mission.plan", "mission.execute",
        "context.build", "context.refresh",
        "contract.generate", "contract.validate",
        "plan.generate", "plan.simulate",
        "reasoning.route", "reasoning.compare",
        "capability.resolve", "capability.health",
        "execution.run", "execution.checkpoint",
        "verification.test", "verification.assert",
        "evidence.collect", "evidence.verify",
        "memory.store", "memory.retrieve", "memory.resolve_conflict",
        "evolution.propose", "evolution.evaluate",
    ])
    permission_profile: list[str] = field(default_factory=list)
    memory_namespace: str = "nexara_prime.agent.memory"
    version: str = "1.0.0"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)


# Agent permission templates — what the first-party agent is allowed by default
AGENT_DEFAULT_PERMISSIONS = {
    "mission.read", "mission.create", "mission.pause", "mission.resume", "mission.cancel",
    "connector.read", "connector.invoke",
    "evidence.read", "audit.read",
    "approval.read",
}


PERMISSIONS = {
    "mission.read": "Read mission status and results",
    "mission.create": "Create new missions",
    "mission.pause": "Pause running missions",
    "mission.resume": "Resume paused missions",
    "mission.cancel": "Cancel missions",
    "approval.read": "Read approval records",
    "approval.decide": "Make approval decisions",
    "connector.read": "Read connector state and manifests",
    "connector.invoke": "Invoke connector actions",
    "connector.configure": "Configure connector settings",
    "secret.reference": "Reference secrets by name",
    "secret.manage": "Create/delete secrets",
    "evidence.read": "Read evidence records",
    "audit.read": "Read audit trail",
    "runtime.control": "Control runtime (start/stop/config)",
    "security.admin": "Full security administration",
}


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.LOCAL_OWNER: set(PERMISSIONS.keys()),
    Role.OPERATOR: {
        "mission.read", "mission.create", "mission.pause", "mission.resume",
        "connector.read", "connector.invoke", "evidence.read", "audit.read",
    },
    Role.REVIEWER: {
        "mission.read", "approval.read", "approval.decide",
        "evidence.read", "audit.read",
    },
    Role.AUDITOR: {
        "mission.read", "evidence.read", "audit.read",
    },
    Role.READ_ONLY: {
        "mission.read", "connector.read", "evidence.read", "audit.read",
    },
}


AGENT_DENIED_PERMISSIONS = {
    "secret.manage", "security.admin", "runtime.control",
    "connector.configure", "approval.decide",
}


@dataclass
class PermissionGrant:
    grant_id: str = field(default_factory=lambda: new_id('evt'))
    user_id: str = ""
    permission: str = ""
    granted_by: str = ""
    granted_at: str = field(default_factory=now_iso)
    scope: str = "*"


@dataclass
class PermissionRevocation:
    revocation_id: str = field(default_factory=lambda: new_id('evt'))
    grant_id: str = ""
    permission: str = ""
    revoked_by: str = ""
    revoked_at: str = field(default_factory=now_iso)
    reason: str = ""


@dataclass
class ApprovalAuthority:
    authority_id: str = field(default_factory=lambda: new_id('evt'))
    user_id: str = ""
    role: Role = Role.LOCAL_OWNER
    max_risk_level: str = "R3"
    scope: str = "*"
    active: bool = True
    created_at: str = field(default_factory=now_iso)


class IdentityStore:
    """Local identity store — single-user foundation."""

    def __init__(self):
        self._user: UserIdentity = UserIdentity()
        self._device: DeviceIdentity = DeviceIdentity()
        self._sessions: dict[str, SessionIdentity] = {}
        self._grants: dict[str, PermissionGrant] = {}
        self._revocations: dict[str, PermissionRevocation] = {}
        self._authorities: dict[str, ApprovalAuthority] = {}
        self._localhost_only: bool = True

    def get_user(self) -> UserIdentity:
        return self._user

    def get_device(self) -> DeviceIdentity:
        return self._device

    def create_session(self, is_agent: bool = False) -> SessionIdentity:
        s = SessionIdentity(
            user_id=self._user.user_id,
            device_id=self._device.device_id,
            is_agent=is_agent,
        )
        self._sessions[s.session_id] = s
        return s

    def end_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].is_active = False

    def check_permission(self, user_id: str, permission: str,
                          is_agent: bool = False) -> bool:
        if is_agent and permission in AGENT_DENIED_PERMISSIONS:
            return False
        # Check revocations
        for rev in self._revocations.values():
            if rev.permission == permission:
                return False
        # Check user roles
        for role in self._user.roles:
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        return False

    def grant_permission(self, permission: str, granted_by: str) -> PermissionGrant:
        g = PermissionGrant(permission=permission, granted_by=granted_by)
        self._grants[g.grant_id] = g
        return g

    def revoke_permission(self, grant_id: str, revoked_by: str, reason: str = "") -> PermissionRevocation:
        if grant_id not in self._grants:
            raise KeyError(f"grant {grant_id} not found")
        g = self._grants[grant_id]
        r = PermissionRevocation(
            grant_id=grant_id, permission=g.permission,
            revoked_by=revoked_by, reason=reason,
        )
        self._revocations[r.revocation_id] = r
        return r

    @property
    def localhost_only(self) -> bool:
        return self._localhost_only

    def set_localhost_only(self, value: bool) -> None:
        self._localhost_only = value

    def list_permissions(self, user_id: str = "") -> list[dict]:
        perms = []
        for p in PERMISSIONS:
            granted = self.check_permission(user_id or self._user.user_id, p)
            perms.append({"permission": p, "granted": granted,
                          "description": PERMISSIONS[p]})
        return perms
