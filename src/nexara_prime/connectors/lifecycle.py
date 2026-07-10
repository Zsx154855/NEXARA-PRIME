"""ConnectorLifecycle — state machine enforcement."""
from __future__ import annotations

from .base import ConnectorLifecycleState, BaseConnector, _VALID_TRANSITIONS


class ConnectorLifecycle:
    @staticmethod
    def can_transition(current: ConnectorLifecycleState, target: ConnectorLifecycleState) -> bool:
        return target in _VALID_TRANSITIONS.get(current, set()) or current == target

    @staticmethod
    def validate_transition(connector: BaseConnector, target: ConnectorLifecycleState) -> None:
        if not ConnectorLifecycle.can_transition(connector.state, target):
            raise ValueError(
                f"Invalid transition: {connector.state.value} -> {target.value}")

    @staticmethod
    def is_operational(state: ConnectorLifecycleState) -> bool:
        return state in (ConnectorLifecycleState.HEALTHY, ConnectorLifecycleState.DEGRADED)

    @staticmethod
    def is_terminal(state: ConnectorLifecycleState) -> bool:
        return state in (ConnectorLifecycleState.STOPPED, ConnectorLifecycleState.FAILED)
