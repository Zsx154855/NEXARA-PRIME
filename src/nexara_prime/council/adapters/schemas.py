"""NEXARA Council V2 — Adapter Schemas

Unified schema for all model adapters. Every adapter must return
an AdapterResponse matching this schema.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TransportType(str, Enum):
    API = "api"
    CLI = "cli"
    HERMES_WORKER = "hermes-worker"


class UsageMode(str, Enum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class AdapterStatus(str, Enum):
    READY = "READY"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_FAILED = "AUTH_FAILED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass
class AdapterResponse:
    """Unified response schema for all adapters."""

    adapter_id: str = ""
    seat: str = ""
    transport: TransportType = TransportType.API
    provider: str = ""
    model_id: str = ""

    backend_identity: str = ""
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    started_at: str = ""
    completed_at: str = ""

    latency_ms: float = 0.0

    usage_mode: UsageMode = UsageMode.UNAVAILABLE
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    response_sha256: str = ""
    schema_valid: bool = True
    simulated: bool = False

    error: Optional[str] = None
    raw_response_preview: str = ""  # First 200 chars, redacted

    def compute_response_hash(self, content: str) -> str:
        self.response_sha256 = hashlib.sha256(content.encode()).hexdigest()
        return self.response_sha256

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "seat": self.seat,
            "transport": self.transport.value,
            "provider": self.provider,
            "model_id": self.model_id,
            "backend_identity": self.backend_identity,
            "request_id": self.request_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "latency_ms": self.latency_ms,
            "usage_mode": self.usage_mode.value,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "response_sha256": self.response_sha256,
            "schema_valid": self.schema_valid,
            "simulated": self.simulated,
            "error": self.error,
            "raw_response_preview": self.raw_response_preview[:200] if self.raw_response_preview else "",
        }

    @classmethod
    def error_response(cls, adapter_id: str, seat: str, error: str,
                       provider: str = "", transport: TransportType = TransportType.API) -> AdapterResponse:
        return cls(
            adapter_id=adapter_id,
            seat=seat,
            transport=transport,
            provider=provider,
            schema_valid=False,
            simulated=False,
            error=error,
        )


@dataclass
class AdapterDiscovery:
    """Result of adapter discovery/health probe."""

    adapter_id: str
    seat: str
    status: AdapterStatus = AdapterStatus.NOT_CONFIGURED

    credential_source: str = ""
    credential_present: bool = False
    client_found: bool = False
    auth_probe_pass: bool = False
    model_resolved: str = ""
    real_request_pass: bool = False

    provider: str = ""
    transport: TransportType = TransportType.API
    cli_path: str = ""
    cli_version: str = ""

    error_detail: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "seat": self.seat,
            "status": self.status.value,
            "credential_source": self.credential_source,
            "credential_present": self.credential_present,
            "client_found": self.client_found,
            "auth_probe_pass": self.auth_probe_pass,
            "model_resolved": self.model_resolved,
            "real_request_pass": self.real_request_pass,
            "provider": self.provider,
            "transport": self.transport.value,
            "cli_path": self.cli_path,
            "cli_version": self.cli_version,
            "error_detail": self.error_detail,
        }


@dataclass
class CanaryRequest:
    """Standard canary request for all adapters."""

    task: str = "NEXARA council adapter identity canary"
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    required_output: dict = field(default_factory=lambda: {
        "adapter_role": "",
        "risk": "NONE",
        "recommendation": "READY",
    })

    def to_prompt(self, seat: str) -> str:
        self.required_output["adapter_role"] = seat
        self.required_output["nonce"] = self.nonce
        return (
            f"{self.task}. Nonce: {self.nonce}. "
            f"Respond with EXACTLY this JSON and nothing else: "
            f'{{"nonce":"{self.nonce}","adapter_role":"{seat}","risk":"NONE","recommendation":"READY"}}'
        )


@dataclass
class CouncilDebatePacket:
    """Debate mission packet — identical for all participants."""

    mission_id: str = ""
    objective: str = (
        "Evaluate whether NEXARA Grand Slam Continuous Runner Full is ready to launch. "
        "Check: multi-model authenticity, authorization boundaries, token governance, "
        "recovery capability, and evidence integrity."
    )
    packet_hash: str = ""

    def compute_hash(self) -> str:
        content = f"{self.mission_id}|{self.objective}"
        self.packet_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.packet_hash
