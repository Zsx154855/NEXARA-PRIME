"""ConnectorPermissionRegistry — permission scope management."""
from __future__ import annotations

from .base import ConnectorPermission, RiskLevel


class ConnectorPermissionRegistry:
    def __init__(self):
        self._permissions: dict[str, dict[str, ConnectorPermission]] = {}
        self._revoked: set[str] = set()

    def register_permissions(self, connector_id: str, permissions: list[ConnectorPermission]) -> None:
        self._permissions[connector_id] = {p.scope: p for p in permissions}

    def get_permission(self, connector_id: str, scope: str) -> ConnectorPermission | None:
        return self._permissions.get(connector_id, {}).get(scope)

    def revoke_permission(self, connector_id: str, scope: str) -> None:
        self._revoked.add(f"{connector_id}:{scope}")

    def is_revoked(self, connector_id: str, scope: str) -> bool:
        return f"{connector_id}:{scope}" in self._revoked

    def list_permissions(self, connector_id: str) -> list[dict]:
        perms = self._permissions.get(connector_id, {})
        return [
            {"scope": p.scope, "risk_level": p.risk_level.value,
             "requires_approval": p.requires_approval,
             "revoked": self.is_revoked(connector_id, p.scope)}
            for p in perms.values()
        ]

    def auto_approve_r0_r1(self, connector_id: str, scope: str) -> bool:
        perm = self.get_permission(connector_id, scope)
        if perm is None:
            return False
        if self.is_revoked(connector_id, scope):
            return False
        return perm.risk_level in (RiskLevel.R0, RiskLevel.R1) and not perm.requires_approval
