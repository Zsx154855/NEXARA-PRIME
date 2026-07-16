"""Notification gateway — routes notifications via abstract channels."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class NotificationLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    CRITICAL = "critical"


@dataclass
class Notification:
    level: NotificationLevel
    title: str
    body: str
    mission_id: str = ""
    approval_id: str = ""
    action: str = ""
    timestamp: str = ""
    delivered: bool = False


class NotificationChannel(Protocol):
    def send(self, notification: Notification) -> bool: ...


class NotificationGateway:
    """Abstracts notification delivery across channels.

    Only APPROVAL_REQUIRED, BLOCKED, and CRITICAL notifications are
    dispatched to user-facing channels. INFO and SUCCESS are logged
    locally only.
    """

    USER_FACING_LEVELS = {
        NotificationLevel.APPROVAL_REQUIRED,
        NotificationLevel.BLOCKED,
        NotificationLevel.CRITICAL,
    }

    def __init__(self) -> None:
        self._channels: list[NotificationChannel] = []
        self._history: list[Notification] = []

    def register_channel(self, channel: NotificationChannel) -> None:
        self._channels.append(channel)

    def notify(
        self, level: NotificationLevel, title: str, body: str,
        mission_id: str = "", approval_id: str = "", action: str = "",
    ) -> Notification:
        from datetime import datetime, timezone
        notification = Notification(
            level=level, title=title, body=body,
            mission_id=mission_id, approval_id=approval_id, action=action,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        if level in self.USER_FACING_LEVELS:
            for channel in self._channels:
                try:
                    notification.delivered = channel.send(notification)
                except Exception:
                    pass
        self._history.append(notification)
        return notification

    def should_interrupt_user(self, level: NotificationLevel) -> bool:
        return level in self.USER_FACING_LEVELS

    @property
    def pending_approvals(self) -> list[Notification]:
        return [
            n for n in self._history
            if n.level == NotificationLevel.APPROVAL_REQUIRED and not n.delivered
        ]

    def to_evidence(self) -> dict[str, Any]:
        return {
            "total_notifications": len(self._history),
            "by_level": {
                level.value: sum(1 for n in self._history if n.level == level)
                for level in NotificationLevel
            },
            "channels": len(self._channels),
            "pending_approvals": len(self.pending_approvals),
        }
