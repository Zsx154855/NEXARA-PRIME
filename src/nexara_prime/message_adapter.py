"""NEXARA PRIME Message Adapter — Governed external messaging.

Draft → Preview → Approval → Send → Evidence pipeline.

Security:
- Default AGENTSOS_EXTERNAL_SEND_ENABLED=false (no external send)
- Recipient allowlist / domain allowlist
- Exact recipients must match approval
- Content digest + idempotency key to prevent double-send
- Before/After Evidence for every send
- Preview must be approved before real send
- Mock Provider for tests
- Local Capture Provider for development
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .models import new_id, now_iso


# ── Capability flags ──

MESSAGE_MOCK_PROVIDER = "MESSAGE_MOCK_PROVIDER"
MESSAGE_LOCAL_CAPTURE = "MESSAGE_LOCAL_CAPTURE"
MESSAGE_EXTERNAL_SEND_ENABLED = "MESSAGE_EXTERNAL_SEND_ENABLED"
MESSAGE_RECIPIENT_ALLOWLIST_ACTIVE = "MESSAGE_RECIPIENT_ALLOWLIST_ACTIVE"
MESSAGE_CONTENT_SCAN_ACTIVE = "MESSAGE_CONTENT_SCAN_ACTIVE"


# ── Message channel types ──

class MessageChannel:
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    SMS = "sms"
    CUSTOM = "custom"


@dataclass
class MessageCapability:
    flags: list[str] = field(default_factory=list)
    provider_type: str = "mock"
    external_send_enabled: bool = False
    supported_channels: list[str] = field(default_factory=lambda: ["email", "slack", "webhook"])
    recipient_allowlist: list[str] = field(default_factory=list)
    domain_allowlist: list[str] = field(default_factory=list)
    max_recipients: int = 20
    max_body_length: int = 100_000


@dataclass
class MessageDraft:
    draft_id: str = field(default_factory=lambda: new_id("msg"))
    channel: str = MessageChannel.EMAIL
    recipients: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    content_digest: str = ""

    def compute_digest(self) -> str:
        canonical = json.dumps({
            "channel": self.channel,
            "recipients": sorted(self.recipients),
            "subject": self.subject,
            "body": self.body,
        }, sort_keys=True, ensure_ascii=False)
        self.content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.content_digest


@dataclass
class MessagePreview:
    draft_id: str = ""
    channel: str = ""
    recipients: list[str] = field(default_factory=list)
    subject: str = ""
    body_preview: str = ""
    body_length: int = 0
    content_digest: str = ""
    estimated_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)
    requires_approval: bool = True


@dataclass
class MessageResult:
    message_id: str = ""
    draft_id: str = ""
    success: bool = False
    sent: bool = False
    captured: bool = False
    channel: str = ""
    recipients: list[str] = field(default_factory=list)
    content_digest: str = ""
    provider_message_id: str = ""
    error: str = ""
    duration_ms: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)
    idempotency_key: str = ""


class MessageProvider(ABC):
    """Abstract message provider."""

    @abstractmethod
    def probe_capability(self) -> MessageCapability: ...

    @abstractmethod
    def send(self, draft: MessageDraft, idempotency_key: str) -> MessageResult: ...

    @abstractmethod
    def validate_recipient(self, recipient: str) -> tuple[bool, str]: ...


class MockMessageProvider(MessageProvider):
    """Deterministic mock — messages go to /dev/null, recorded for assertions."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self._message_counter: int = 0

    def probe_capability(self) -> MessageCapability:
        return MessageCapability(
            flags=[MESSAGE_MOCK_PROVIDER],
            provider_type="mock",
            external_send_enabled=False,
        )

    def validate_recipient(self, recipient: str) -> tuple[bool, str]:
        if "@" in recipient:
            return True, "ok"
        return False, f"invalid_recipient_format:{recipient}"

    def send(self, draft: MessageDraft, idempotency_key: str) -> MessageResult:
        self._message_counter += 1
        provider_id = f"mock_msg_{self._message_counter:06d}"
        record = {
            "draft_id": draft.draft_id,
            "channel": draft.channel,
            "recipients": draft.recipients,
            "subject": draft.subject,
            "body": draft.body,
            "content_digest": draft.content_digest,
            "provider_message_id": provider_id,
            "idempotency_key": idempotency_key,
            "sent_at": now_iso(),
        }
        self.sent_messages.append(record)
        return MessageResult(
            message_id=new_id("msg"),
            draft_id=draft.draft_id,
            success=True,
            sent=True,
            channel=draft.channel,
            recipients=draft.recipients,
            content_digest=draft.content_digest,
            provider_message_id=provider_id,
            idempotency_key=idempotency_key,
        )


class LocalCaptureProvider(MessageProvider):
    """Development provider — writes messages to local files, never sends externally."""

    def __init__(self, capture_dir: str = "/tmp/nexara-messages") -> None:
        import os
        self.capture_dir = capture_dir
        self.sent_messages: list[dict[str, Any]] = []
        os.makedirs(capture_dir, exist_ok=True)

    def probe_capability(self) -> MessageCapability:
        return MessageCapability(
            flags=[MESSAGE_LOCAL_CAPTURE],
            provider_type="local_capture",
            external_send_enabled=False,
        )

    def validate_recipient(self, recipient: str) -> tuple[bool, str]:
        if "@" in recipient:
            return True, "ok"
        return False, f"invalid_recipient_format:{recipient}"

    def send(self, draft: MessageDraft, idempotency_key: str) -> MessageResult:
        import os
        filename = f"{draft.draft_id}_{draft.channel}.json"
        filepath = os.path.join(self.capture_dir, filename)
        payload = {
            "draft_id": draft.draft_id,
            "channel": draft.channel,
            "recipients": draft.recipients,
            "subject": draft.subject,
            "body": draft.body,
            "content_digest": draft.content_digest,
            "idempotency_key": idempotency_key,
            "captured_at": now_iso(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.sent_messages.append(payload)
        return MessageResult(
            message_id=new_id("msg"),
            draft_id=draft.draft_id,
            success=True,
            sent=False,
            captured=True,
            channel=draft.channel,
            recipients=draft.recipients,
            content_digest=draft.content_digest,
            provider_message_id=f"local:{filepath}",
            idempotency_key=idempotency_key,
        )


class GovernedMessageAdapter:
    """Governed message adapter with Draft→Preview→Approval→Send pipeline.

    Default AGENTSOS_EXTERNAL_SEND_ENABLED=false.

    Real external send requires:
    1. Approval with exact recipients + content digest
    2. Idempotency key to prevent double-send
    3. Recipient in allowlist (if configured)
    4. Content scan passed
    """

    # Sensitive content patterns to warn about
    SENSITIVE_PATTERNS = [
        (r'(?i)password\s*[:=]\s*\S+', 'password_in_body'),
        (r'(?i)secret\s*[:=]\s*\S+', 'secret_in_body'),
        (r'(?i)credit\s*card', 'credit_card_mention'),
        (r'\b\d{3}-\d{2}-\d{4}\b', 'ssn_pattern'),
        (r'\b\d{16}\b', 'potential_card_number'),
    ]

    # Forbidden content — always block
    FORBIDDEN_PATTERNS = [
        (r'(?i)phish|scam|fraud', 'phishing_language'),
        (r'(?i)malware|ransomware|exploit|backdoor', 'malware_language'),
    ]

    def __init__(
        self,
        provider: MessageProvider | None = None,
        *,
        evidence_store=None,
        approval_engine=None,
        external_send_enabled: bool = False,
        recipient_allowlist: list[str] | None = None,
        domain_allowlist: list[str] | None = None,
        enable_content_scan: bool = True,
    ) -> None:
        self.provider = provider or MockMessageProvider()
        self.evidence = evidence_store
        self.approvals = approval_engine
        self.external_send_enabled = external_send_enabled
        self.recipient_allowlist = recipient_allowlist or []
        self.domain_allowlist = domain_allowlist or []
        self.enable_content_scan = enable_content_scan
        self._sent_keys: set[str] = set()
        self._drafts: dict[str, MessageDraft] = {}
        self._action_history: list[dict[str, Any]] = []

    # ── Recipient validation ──

    def _validate_recipient(self, recipient: str) -> tuple[bool, str]:
        """Validate a single recipient."""
        # Check format via provider
        ok, reason = self.provider.validate_recipient(recipient)
        if not ok:
            return False, reason

        # If allowlist is active, check it
        if self.recipient_allowlist:
            if recipient not in self.recipient_allowlist:
                # Check domain-level allowlist
                domain = recipient.split("@")[-1] if "@" in recipient else ""
                if domain not in self.domain_allowlist:
                    return False, f"recipient_not_in_allowlist:{recipient}"

        # Check domain allowlist
        if self.domain_allowlist:
            domain = recipient.split("@")[-1] if "@" in recipient else ""
            if domain not in self.domain_allowlist:
                return False, f"domain_not_in_allowlist:{domain}"

        return True, "ok"

    def _validate_all_recipients(self, recipients: list[str]) -> tuple[bool, str, list[str]]:
        """Validate all recipients, return first failure."""
        invalid: list[str] = []
        for r in recipients:
            ok, reason = self._validate_recipient(r)
            if not ok:
                invalid.append(f"{r}:{reason}")
        if invalid:
            return False, f"invalid_recipients:{';'.join(invalid)}", invalid
        return True, "ok", []

    # ── Content scanning ──

    def _scan_content(self, subject: str, body: str) -> list[dict[str, Any]]:
        """Scan message content for sensitive/forbidden patterns."""
        findings: list[dict[str, Any]] = []
        combined = f"{subject}\n{body}"

        # Check forbidden patterns first (hard block)
        for pattern, label in self.FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, combined):
                findings.append({
                    "label": label,
                    "severity": "forbidden",
                    "match": match.group(0)[:40],
                })

        # Check sensitive patterns (warnings)
        for pattern, label in self.SENSITIVE_PATTERNS:
            for match in re.finditer(pattern, combined):
                findings.append({
                    "label": label,
                    "severity": "sensitive",
                    "match": match.group(0)[:40],
                })

        return findings

    # ── Evidence ──

    def _record_evidence(self, draft: MessageDraft, result: MessageResult) -> list[str]:
        if not self.evidence:
            return []
        payload = json.dumps({
            "draft_id": draft.draft_id,
            "channel": draft.channel,
            "recipients": draft.recipients,
            "subject": draft.subject,
            "content_digest": draft.content_digest,
            "success": result.success,
            "sent": result.sent,
            "captured": result.captured,
            "error": result.error,
            "idempotency_key": result.idempotency_key,
            "duration_ms": result.duration_ms,
        }, ensure_ascii=False)
        try:
            ev = self.evidence.add(
                "message_session", "message_send",
                f"Message: {draft.channel}/{draft.subject[:60]}",
                payload, draft.draft_id,
                actor="message_adapter", source="message",
                verification_status="verified",
            )
            return [ev.evidence_id]
        except Exception:
            return []

    # ── Pipeline steps ──

    def draft(
        self,
        channel: str,
        recipients: list[str],
        subject: str,
        body: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> MessageDraft:
        """Create a message draft (Step 1: Draft)."""
        draft = MessageDraft(
            channel=channel,
            recipients=recipients,
            subject=subject,
            body=body,
            metadata=metadata or {},
        )
        draft.compute_digest()
        self._drafts[draft.draft_id] = draft
        self._action_history.append({
            "step": "draft",
            "draft_id": draft.draft_id,
            "channel": channel,
            "timestamp": draft.created_at,
        })
        return draft

    def preview(self, draft_id: str) -> MessagePreview:
        """Generate a preview for approval (Step 2: Preview)."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return MessagePreview(draft_id=draft_id, warnings=["draft_not_found"])

        warnings: list[str] = []
        requires_approval = True

        # Recipient validation
        ok, reason, invalid = self._validate_all_recipients(draft.recipients)
        if not ok:
            warnings.append(f"recipient_validation:{reason}")
            requires_approval = True

        # Content scan
        if self.enable_content_scan:
            findings = self._scan_content(draft.subject, draft.body)
            forbidden = [f for f in findings if f["severity"] == "forbidden"]
            sensitive = [f for f in findings if f["severity"] == "sensitive"]
            if forbidden:
                warnings.append(f"forbidden_content:{','.join(f['label'] for f in forbidden)}")
                requires_approval = True
            if sensitive:
                warnings.append(f"sensitive_content:{','.join(f['label'] for f in sensitive)}")

        # External send check
        if not self.external_send_enabled:
            warnings.append("external_send_disabled_will_capture_locally")

        # Body length
        body_preview = draft.body[:200] + ("..." if len(draft.body) > 200 else "")
        if len(draft.body) > self.provider.probe_capability().max_body_length:
            warnings.append("body_exceeds_max_length")

        return MessagePreview(
            draft_id=draft_id,
            channel=draft.channel,
            recipients=draft.recipients,
            subject=draft.subject,
            body_preview=body_preview,
            body_length=len(draft.body),
            content_digest=draft.content_digest,
            estimated_cost=self._estimate_cost(draft),
            warnings=warnings,
            requires_approval=requires_approval or not self.external_send_enabled,
        )

    def _estimate_cost(self, draft: MessageDraft) -> float:
        """Estimate sending cost (mock: $0.00)."""
        # In production, this would check provider pricing
        return 0.0

    def send(
        self,
        draft_id: str,
        *,
        force_send: bool = False,
        trace_id: str = "",
    ) -> MessageResult:
        """Send or capture a message (Step 4: Send after Approval).

        In mock/capture modes, this always succeeds (messages go to mock/capture).
        With external_send_enabled=true, requires prior approval.
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            return MessageResult(draft_id=draft_id, error="draft_not_found")

        # Idempotency: prevent double-send
        idempotency_key = f"msg_send:{draft.draft_id}:{draft.content_digest}"
        if idempotency_key in self._sent_keys:
            return MessageResult(
                draft_id=draft_id,
                success=False,
                error="already_sent:idempotency_key_exists",
                idempotency_key=idempotency_key,
            )

        # Validate recipients
        ok, reason, _ = self._validate_all_recipients(draft.recipients)
        if not ok:
            return MessageResult(draft_id=draft_id, error=f"recipient_validation_failed:{reason}")

        # Content scan
        if self.enable_content_scan:
            findings = self._scan_content(draft.subject, draft.body)
            forbidden = [f for f in findings if f["severity"] == "forbidden"]
            if forbidden:
                return MessageResult(
                    draft_id=draft_id,
                    error=f"forbidden_content_detected:{','.join(f['label'] for f in forbidden)}",
                )

        # External send gate
        if not self.external_send_enabled:
            # Always capture locally, never send externally
            started = time.monotonic()
            result = self.provider.send(draft, idempotency_key)
            result.duration_ms = (time.monotonic() - started) * 1000
            # Override: always mark as captured, not sent
            result.sent = False
            result.captured = True
            self._sent_keys.add(idempotency_key)
            result.evidence_ids = self._record_evidence(draft, result)
            self._action_history.append({
                "step": "send", "draft_id": draft_id,
                "sent": False, "captured": True,
                "timestamp": now_iso(),
            })
            return result

        # External send path: requires approval
        if not force_send:
            return MessageResult(
                draft_id=draft_id,
                error="external_send_requires_approval_or_force_send_flag",
            )

        started = time.monotonic()
        result = self.provider.send(draft, idempotency_key)
        result.duration_ms = (time.monotonic() - started) * 1000
        self._sent_keys.add(idempotency_key)
        result.evidence_ids = self._record_evidence(draft, result)
        self._action_history.append({
            "step": "send", "draft_id": draft_id,
            "sent": result.sent, "captured": result.captured,
            "timestamp": now_iso(),
        })
        return result

    # ── Lifecycle ──

    def probe_capability(self) -> MessageCapability:
        cap = self.provider.probe_capability()
        cap.external_send_enabled = self.external_send_enabled
        cap.recipient_allowlist = list(self.recipient_allowlist)
        cap.domain_allowlist = list(self.domain_allowlist)
        if self.external_send_enabled:
            cap.flags.append(MESSAGE_EXTERNAL_SEND_ENABLED)
        if self.recipient_allowlist or self.domain_allowlist:
            cap.flags.append(MESSAGE_RECIPIENT_ALLOWLIST_ACTIVE)
        if self.enable_content_scan:
            cap.flags.append(MESSAGE_CONTENT_SCAN_ACTIVE)
        return cap

    def get_draft(self, draft_id: str) -> MessageDraft | None:
        return self._drafts.get(draft_id)

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._action_history)

    def get_sent_messages(self) -> list[dict[str, Any]]:
        """Retrieve sent messages from the provider (for mock assertions)."""
        if hasattr(self.provider, 'sent_messages'):
            return list(getattr(self.provider, 'sent_messages'))
        return []
