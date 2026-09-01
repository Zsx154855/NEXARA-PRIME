"""Conversation attachments — durable file uploads bound to conversations.

Uploaded files (images, videos, documents) are stored under the runtime
uploads directory keyed by attachment id; records live in the canonical
``records`` table like every other projection.  Plugin and connection
attachments are registry references and are bound to messages at send time,
not uploaded.  Uploads are size-bounded, filename-sanitized, and audited.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .db import SQLiteStore
from .models import new_id, now_iso
from .security_audit import SecurityAuditLedger


MAX_ATTACHMENT_BYTES = 32 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^\w.\-\u4e00-\u9fff]+", re.UNICODE)


def classify_kind(media_type: str) -> str:
    if media_type.startswith("image/"):
        return "image"
    if media_type.startswith("video/"):
        return "video"
    return "file"


def sanitize_name(name: str) -> str:
    base = Path(name or "attachment.bin").name
    cleaned = _SAFE_NAME.sub("_", base).strip("._")
    return (cleaned or "attachment.bin")[:80]


class ConversationAttachmentStore:
    """Persist conversation file uploads in the canonical runtime store."""

    def __init__(
        self,
        store: SQLiteStore,
        audit: SecurityAuditLedger,
        root: Path,
    ) -> None:
        self.store = store
        self.audit = audit
        self.root = Path(root)

    def upload(
        self,
        conversation_id: str,
        *,
        name: str,
        media_type: str,
        data: bytes,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        if not data:
            raise ValueError("attachment_empty")
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise ValueError("attachment_too_large")

        timestamp = now_iso()
        attachment_id = new_id("attachment")
        safe_name = sanitize_name(name)
        stored_rel = f"{conversation_id}/{attachment_id}__{safe_name}"
        dest = (self.root / stored_rel).resolve()
        if self.root.resolve() not in dest.parents:
            raise ValueError("attachment_path_invalid")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

        record = {
            "attachment_id": attachment_id,
            "conversation_id": conversation_id,
            "name": safe_name,
            "kind": classify_kind(media_type or "application/octet-stream"),
            "media_type": media_type or "application/octet-stream",
            "size": len(data),
            "content_hash": hashlib.sha256(data).hexdigest(),
            "stored_path": stored_rel,
            "created_at": timestamp,
        }
        self.store.save_record(
            attachment_id,
            "conversation_attachment",
            record,
            timestamp,
            conversation_id,
        )
        self.audit.record(
            "conversation.attachment",
            actor_id="human",
            actor_type="human",
            session_id=conversation_id,
            resource=attachment_id,
            action="upload_attachment",
            decision="allowed",
            risk_level="R0",
            trace_id=trace_id or conversation_id,
            metadata={"name": safe_name, "size": len(data), "kind": record["kind"]},
        )
        return record

    def get(self, conversation_id: str, attachment_id: str) -> dict[str, Any]:
        record = self.store.get_record(attachment_id)
        if (
            not record
            or record.get("attachment_id") != attachment_id
            or record.get("conversation_id") != conversation_id
        ):
            raise KeyError(f"attachment_not_found:{attachment_id}")
        return record

    def list(self, conversation_id: str) -> list[dict[str, Any]]:
        records = [
            record
            for record in self.store.list_records("conversation_attachment")
            if record.get("conversation_id") == conversation_id
        ]
        return sorted(
            records,
            key=lambda item: (item.get("created_at", ""), item.get("attachment_id", "")),
        )

    def content_path(self, record: dict[str, Any]) -> Path:
        path = (self.root / record["stored_path"]).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("attachment_path_invalid")
        if not path.is_file():
            raise FileNotFoundError(f"attachment_content_missing:{record['attachment_id']}")
        return path
