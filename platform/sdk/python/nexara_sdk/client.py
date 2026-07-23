"""NEXARA Runtime Truth API client — complete SDK."""
from __future__ import annotations

from typing import Any

import httpx2

from .models import (
    ApprovalRequest,
    EvidenceArtifact,
    MemoryRecord,
    Mission,
    RuntimeOverview,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class NexaraError(Exception):
    """Base error for NEXARA SDK."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NexaraClient:
    """First-party SDK client for NEXARA PRIME Runtime Truth API.

    Usage:
        async with NexaraClient() as client:
            health = await client.health()
            missions = await client.list_missions()
            m = await client.create_mission("Analyze project X")
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._base = f"http://{host}:{port}"
        self._client: httpx2.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx2.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: Any):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx2.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with NexaraClient() as client:' context manager")
        return self._client

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        """Internal request with error handling."""
        url = f"{self._base}{path}"
        try:
            r = await self.client.request(method, url, **kwargs)
            r.raise_for_status()
            return r.json()
        except httpx2.HTTPStatusError as e:
            raise NexaraError(f"HTTP {e.response.status_code}: {e.response.text}", e.response.status_code)
        except httpx2.RequestError as e:
            raise NexaraError(f"Connection failed: {e}")

    # ── Health ──

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    # ── Runtime Overview ──

    async def overview(self) -> RuntimeOverview:
        data = await self._request("GET", "/api/runtime/overview")
        return RuntimeOverview(**data)

    # ── Missions ──

    async def list_missions(self) -> list[Mission]:
        data = await self._request("GET", "/api/missions")
        return [Mission(**m) for m in data]

    async def get_mission(self, mission_id: str) -> Mission:
        data = await self._request("GET", f"/api/missions/{mission_id}")
        return Mission(**data)

    async def create_mission(self, objective: str, source_dir: str | None = None) -> Mission:
        body: dict[str, Any] = {"objective": objective}
        if source_dir:
            body["source_dir"] = source_dir
        data = await self._request("POST", "/api/missions", json=body)
        return Mission(**data)

    # ── Mission Actions ──

    async def plan_mission(self, mission_id: str) -> Mission:
        data = await self._request("POST", f"/api/missions/{mission_id}/plan", json={})
        return Mission(**data)

    async def approve_mission(self, mission_id: str, approved: bool = True) -> Mission:
        body = {"approved": approved, "decision": "approve_mission" if approved else "reject"}
        data = await self._request("POST", f"/api/missions/{mission_id}/approve", json=body)
        return Mission(**data)

    async def run_mission(self, mission_id: str) -> Mission:
        data = await self._request("POST", f"/api/missions/{mission_id}/run", json={})
        return Mission(**data)

    async def pause_mission(self, mission_id: str) -> Mission:
        data = await self._request("POST", f"/api/missions/{mission_id}/pause", json={})
        return Mission(**data)

    async def resume_mission(self, mission_id: str) -> Mission:
        data = await self._request("POST", f"/api/missions/{mission_id}/resume", json={})
        return Mission(**data)

    async def rollback_mission(self, mission_id: str) -> Mission:
        data = await self._request("POST", f"/api/missions/{mission_id}/rollback", json={})
        return Mission(**data)

    async def safe_mode(self, mission_id: str, enabled: bool = True) -> Mission:
        data = await self._request("POST", f"/api/missions/{mission_id}/safe-mode", json={"enabled": enabled})
        return Mission(**data)

    # ── Approvals ──

    async def list_approvals(self) -> list[ApprovalRequest]:
        data = await self._request("GET", "/api/approvals")
        return [ApprovalRequest(**a) for a in data]

    # ── Evidence ──

    async def list_evidence(self, mission_id: str | None = None) -> list[EvidenceArtifact]:
        path = "/api/evidence"
        if mission_id:
            path += f"?mission_id={mission_id}"
        data = await self._request("GET", path)
        return [EvidenceArtifact(**e) for e in data]

    # ── Memory ──

    async def list_memory(self) -> list[MemoryRecord]:
        data = await self._request("GET", "/api/memory")
        return [MemoryRecord(**m) for m in data]

    async def memory_candidates(self) -> list[MemoryRecord]:
        data = await self._request("GET", "/api/memory/candidates")
        return [MemoryRecord(**m) for m in data]

    # ── Events ──

    async def get_events(self, mission_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/api/events/{mission_id}")

    # ── Receipts ──

    async def verify_receipts(self) -> dict[str, Any]:
        return await self._request("GET", "/api/receipts")

    # ── Tools ──

    async def list_tools(self, mission_id: str | None = None) -> list[dict[str, Any]]:
        path = f"/api/missions/{mission_id}/tools" if mission_id else "/api/tools"
        return await self._request("GET", path)

    # ── Recovery ──

    async def recovery_check(self) -> dict[str, Any]:
        return await self._request("POST", "/api/recovery/check", json={})

    # ── Adaptive Runtime ──

    async def adaptive_status(self) -> dict[str, Any]:
        return await self._request("GET", "/adaptive/status")

    async def adaptive_triage(self, mission_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/adaptive/missions/{mission_id}/triage", json={})
