"""Fail-closed inspection of *references* from a private GitHub mailbox.

This module is deliberately NON-EXECUTING. A successful inspection grants no
permission to run a tool, read a secret, or write a file. Trusted macOS Broker
must separately verify a real P3 signature, its existing SQLite lease/epoch,
CAB-01/Mission/Contract/Policy/Kernel admission, and the OS identity boundary
on EVERY dispatch and resume. Never pass model-controlled GitHub metadata here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping


MAX_BODY_BYTES = 4096
MAX_TTL_SECONDS = 300
CLOCK_SKEW_SECONDS = 30
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{5,95}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_FIELDS = frozenset({
    "schema", "channel_repo_id", "channel_issue_number", "mission_id",
    "contract_id", "approval_id", "nonce", "signed_sha256", "issued_at",
    "expires_at",
})


class ChannelRejected(ValueError):
    """Transport metadata or a reference envelope failed closed."""


@dataclass(frozen=True)
class PinnedPrivateChannel:
    """Provisioned BY the trusted host, never inferred from a task comment."""

    repository_id: int
    repository_full_name: str
    owner_id: int
    issue_number: int

    def __post_init__(self) -> None:
        if (type(self.repository_id) is not int or self.repository_id <= 0
            or type(self.owner_id) is not int or self.owner_id <= 0
            or type(self.issue_number) is not int or self.issue_number <= 0
            or not isinstance(self.repository_full_name, str)
            or self.repository_full_name.count("/") != 1
            or any(not part for part in self.repository_full_name.split("/"))):
            raise ChannelRejected("invalid_pinned_channel")


@dataclass(frozen=True)
class TransportReference:
    """Inert result only; MUST NOT be treated as authorization."""

    status: str
    channel_repo_id: int
    channel_issue_number: int
    comment_id: int
    mission_id: str
    contract_id: str
    approval_id: str
    nonce: str
    signed_sha256: str
    body_sha256: str


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ChannelRejected("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_: str) -> Any:
    raise ChannelRejected("non_finite_json_value")


def _safe_int(value: Any) -> bool:
    return type(value) is int and value > 0


def inspect_reference(
    *,
    binding: PinnedPrivateChannel,
    github_repository: Mapping[str, Any],
    github_issue: Mapping[str, Any],
    github_comment: Mapping[str, Any],
    now_epoch: int,
) -> TransportReference:
    """Inspect REST API data supplied by a trusted, credential-isolated Broker.

    In particular this function does NOT verify signed_sha256, authentication
    material, CAB-01 approval or lease freshness. Its return type is intentionally
    inert; the caller must NEVER dispatch or resume from this result alone.
    """
    if not isinstance(binding, PinnedPrivateChannel):
        raise ChannelRejected("host_binding_required")
    if type(now_epoch) is not int or now_epoch <= 0:
        raise ChannelRejected("invalid_broker_clock")
    try:
        repo_owner = github_repository["owner"]
        author = github_comment["user"]
        if (not isinstance(repo_owner, Mapping) or not isinstance(author, Mapping)
            or github_repository["id"] != binding.repository_id
            or type(github_repository["id"]) is not int
            or github_repository["full_name"] != binding.repository_full_name
            or github_repository["private"] is not True
            or github_repository.get("archived") is not False
            or type(repo_owner["id"]) is not int
            or repo_owner["id"] != binding.owner_id
            or type(github_issue["number"]) is not int
            or github_issue["number"] != binding.issue_number
            or github_issue.get("state") != "open"
            or not _safe_int(github_comment["id"])
            or type(author["id"]) is not int
            or author["id"] != binding.owner_id):
            raise ChannelRejected("private_channel_identity_mismatch")
        body = github_comment["body"]
    except (KeyError, TypeError) as exc:
        raise ChannelRejected("missing_trusted_github_metadata") from exc
    if not isinstance(body, str):
        raise ChannelRejected("invalid_comment_body")
    encoded = body.encode("utf-8")
    if not encoded or len(encoded) > MAX_BODY_BYTES:
        raise ChannelRejected("comment_size_invalid")
    try:
        envelope = json.loads(body, object_pairs_hook=_unique_keys,
                              parse_constant=_reject_constant)
    except (ValueError, TypeError) as exc:
        raise ChannelRejected("invalid_reference_json") from exc
    if not isinstance(envelope, dict) or frozenset(envelope) != _FIELDS:
        raise ChannelRejected("reference_schema_mismatch")
    if (type(envelope["schema"]) is not int or envelope["schema"] != 1
        or type(envelope["channel_repo_id"]) is not int
        or envelope["channel_repo_id"] != binding.repository_id
        or type(envelope["channel_issue_number"]) is not int
        or envelope["channel_issue_number"] != binding.issue_number):
        raise ChannelRejected("reference_channel_mismatch")
    for key in ("mission_id", "contract_id", "approval_id", "nonce"):
        if not isinstance(envelope[key], str) or not _REF.fullmatch(envelope[key]):
            raise ChannelRejected("invalid_reference_identifier")
    if (not isinstance(envelope["signed_sha256"], str)
        or not _SHA.fullmatch(envelope["signed_sha256"])):
        raise ChannelRejected("invalid_signed_digest_reference")
    issued = envelope["issued_at"]
    expiry = envelope["expires_at"]
    if (not _safe_int(issued) or not _safe_int(expiry)
        or expiry <= issued or expiry - issued > MAX_TTL_SECONDS
        or issued > now_epoch + CLOCK_SKEW_SECONDS
        or expiry <= now_epoch):
        raise ChannelRejected("reference_expired_or_skewed")

    return TransportReference(
        status="TRANSPORT_ONLY_NOT_AUTHORIZED",
        channel_repo_id=binding.repository_id,
        channel_issue_number=binding.issue_number,
        comment_id=github_comment["id"],
        mission_id=envelope["mission_id"],
        contract_id=envelope["contract_id"],
        approval_id=envelope["approval_id"],
        nonce=envelope["nonce"],
        signed_sha256=envelope["signed_sha256"],
        body_sha256=hashlib.sha256(encoded).hexdigest(),
    )
