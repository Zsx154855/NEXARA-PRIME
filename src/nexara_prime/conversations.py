"""Durable Conversation/Message projections over the canonical runtime store.

Conversation data lives in the existing ``records`` and ``events`` tables.  No
second database or parallel evidence system is introduced.  Message writes
carry an idempotency key so a retried HTTP request cannot create a second user
turn or a second assistant response.
"""

from __future__ import annotations

from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .models import Event, new_id, now_iso
from .security_audit import SecurityAuditLedger


_ROLES = {"user", "assistant", "system"}


class ConversationStore:
    """Persist conversations and messages in the canonical runtime store."""

    def __init__(
        self,
        store: SQLiteStore,
        events: EventBus,
        audit: SecurityAuditLedger,
    ) -> None:
        self.store = store
        self.events = events
        self.audit = audit

    def create(self, title: str | None = None) -> dict[str, Any]:
        timestamp = now_iso()
        conversation = {
            "conversation_id": new_id("conversation"),
            "title": (title or "NEXARA 对话").strip()[:120],
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "open",
            "message_ids": [],
        }
        self.store.save_record(
            conversation["conversation_id"],
            "conversation",
            conversation,
            timestamp,
            conversation["conversation_id"],
        )
        self.events.publish(
            "conversation.created",
            conversation["conversation_id"],
            "conversation",
            "nexara.runtime",
            conversation["conversation_id"],
            {"title": conversation["title"]},
            idempotency_key=f"conversation-created:{conversation['conversation_id']}",
        )
        self.audit.record(
            "conversation.created",
            actor_id="nexara.runtime",
            actor_type="system",
            session_id=conversation["conversation_id"],
            resource=conversation["conversation_id"],
            action="create_conversation",
            decision="allowed",
            risk_level="R0",
            trace_id=conversation["conversation_id"],
        )
        return conversation

    def get(self, conversation_id: str) -> dict[str, Any]:
        conversation = self.store.get_record(conversation_id)
        if not conversation or conversation.get("conversation_id") != conversation_id:
            raise KeyError(f"conversation_not_found:{conversation_id}")
        envelope = self.store.find_record_envelope(
            "conversation", "conversation_id", conversation_id
        )
        if envelope is None:
            raise ValueError("conversation_integrity_invalid")
        return conversation

    def list(self) -> list[dict[str, Any]]:
        conversations = self.store.list_records("conversation")
        return sorted(
            conversations,
            key=lambda item: (item.get("updated_at", ""), item.get("conversation_id", "")),
            reverse=True,
        )

    def messages(self, conversation_id: str) -> list[dict[str, Any]]:
        conversation = self.get(conversation_id)
        messages = [
            message
            for message in self.store.list_records("conversation_message")
            if message.get("conversation_id") == conversation["conversation_id"]
        ]
        return sorted(
            messages,
            key=lambda item: (item.get("created_at", ""), item.get("message_id", "")),
        )

    def find_message_by_idempotency(
        self, conversation_id: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        for message in self.messages(conversation_id):
            if message.get("idempotency_key") == idempotency_key:
                return message
        return None

    def find_assistant_response(
        self, conversation_id: str, user_message_id: str
    ) -> dict[str, Any] | None:
        for message in self.messages(conversation_id):
            metadata = message.get("metadata") or {}
            if (
                message.get("role") == "assistant"
                and metadata.get("response_to") == user_message_id
            ):
                return message
        return None

    def provider_attempts(self, conversation_id: str, message_id: str) -> list[dict[str, Any]]:
        return sorted(
            [item for item in self.store.list_records("provider_attempt")
             if item.get("conversation_id") == conversation_id and item.get("message_id") == message_id],
            key=lambda item: (item.get("created_at", ""), item.get("attempt_id", "")),
        )

    def save_provider_attempt(self, attempt: dict[str, Any]) -> None:
        self.store.save_record(
            attempt["attempt_id"], "provider_attempt", attempt,
            attempt["created_at"], attempt.get("conversation_id"),
        )

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        trace_id: str,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if role not in _ROLES:
            raise ValueError("conversation_role_invalid")
        content = content.strip()
        if not content:
            raise ValueError("conversation_message_empty")
        conversation = self.get(conversation_id)
        if conversation.get("status") == "closed":
            raise ValueError("conversation_closed")
        if idempotency_key:
            existing = self.find_message_by_idempotency(
                conversation_id, idempotency_key
            )
            if existing is not None:
                if existing.get("role") != role or existing.get("content") != content:
                    raise ValueError("conversation_idempotency_conflict")
                return existing

        timestamp = now_iso()
        message = {
            "message_id": new_id("message"),
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "created_at": timestamp,
            "trace_id": trace_id,
            "idempotency_key": idempotency_key,
            "metadata": metadata or {},
        }
        conversation["message_ids"] = [
            *conversation.get("message_ids", []),
            message["message_id"],
        ]
        conversation["updated_at"] = timestamp
        if conversation.get("title") == "NEXARA 对话" and role == "user":
            conversation["title"] = content[:120]
        event = Event(
            event_id=new_id("evt"),
            event_type=f"conversation.message.{role}",
            aggregate_id=conversation_id,
            aggregate_type="conversation",
            actor="nexara.runtime",
            trace_id=trace_id,
            payload={"message_id": message["message_id"], "role": role},
            idempotency_key=f"conversation-message:{message['message_id']}",
        )
        persisted_event = self.store.save_conversation_bundle(
            message, conversation, event.model_dump(mode="json")
        )
        self.events.notify_persisted_dict(persisted_event)
        self.audit.record(
            "conversation.message",
            actor_id="human" if role == "user" else "nexara.runtime",
            actor_type="human" if role == "user" else "system",
            session_id=conversation_id,
            resource=message["message_id"],
            action=f"append_{role}_message",
            decision="allowed",
            risk_level="R0",
            trace_id=trace_id,
            metadata={"content_length": len(content)},
        )
        return message

    def close(self, conversation_id: str) -> dict[str, Any]:
        """Idempotently close a conversation. Closed conversations are read-only:
        no new messages, no new missions, until explicitly reopened."""
        conversation = self.get(conversation_id)
        if conversation.get("status") == "closed":
            return conversation
        conversation["status"] = "closed"
        conversation["updated_at"] = now_iso()
        self.store.save_record(
            conversation["conversation_id"],
            "conversation",
            conversation,
            conversation["created_at"],
            conversation["conversation_id"],
        )
        self.events.publish(
            "conversation.closed",
            conversation_id,
            "conversation",
            "nexara.runtime",
            conversation_id,
            {"status": "closed"},
            idempotency_key=f"conversation-closed:{conversation_id}",
        )
        self.audit.record(
            "conversation.closed",
            actor_id="human",
            actor_type="human",
            session_id=conversation_id,
            resource=conversation_id,
            action="close_conversation",
            decision="allowed",
            risk_level="R0",
            trace_id=conversation_id,
        )
        return conversation

    def reopen(self, conversation_id: str) -> dict[str, Any]:
        """Idempotently reopen a closed conversation back to OPEN."""
        conversation = self.get(conversation_id)
        if conversation.get("status") == "open":
            return conversation
        conversation["status"] = "open"
        conversation["updated_at"] = now_iso()
        self.store.save_record(
            conversation["conversation_id"],
            "conversation",
            conversation,
            conversation["created_at"],
            conversation["conversation_id"],
        )
        self.events.publish(
            "conversation.reopened",
            conversation_id,
            "conversation",
            "nexara.runtime",
            conversation_id,
            {"status": "open"},
            idempotency_key=f"conversation-reopened:{conversation_id}",
        )
        self.audit.record(
            "conversation.reopened",
            actor_id="human",
            actor_type="human",
            session_id=conversation_id,
            resource=conversation_id,
            action="reopen_conversation",
            decision="allowed",
            risk_level="R0",
            trace_id=conversation_id,
        )
        return conversation
