"""NEXARA Runtime Truth API client."""
from __future__ import annotations

from typing import Any

import httpx2

from .models import Mission, RuntimeOverview

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


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
        self._client = httpx2.AsyncClient()
        return self

    async def __aexit__(self, *args: Any):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx2.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with NexaraClient() as client:' context manager")
        return self._client

    # ── Health ──

    async def health(self) -> dict[str, Any]:
        r = await self.client.get(f"{self._base}/health")
        r.raise_for_status()
        return r.json()

    # ── Runtime Overview ──

    async def overview(self) -> RuntimeOverview:
        r = await self.client.get(f"{self._base}/api/runtime/overview")
        r.raise_for_status()
        return RuntimeOverview(**r.json())

    # ── Missions ──

    async def list_missions(self) -> list[Mission]:
        r = await self.client.get(f"{self._base}/api/missions")
        r.raise_for_status()
        return [Mission(**m) for m in r.json()]

    async def get_mission(self, mission_id: str) -> Mission:
        r = await self.client.get(f"{self._base}/api/missions/{mission_id}")
        r.raise_for_status()
        return Mission(**r.json())

    async def create_mission(self, objective: str, source_dir: str | None = None) -> Mission:
        body: dict[str, Any] = {"objective": objective}
        if source_dir:
            body["source_dir"] = source_dir
        r = await self.client.post(f"{self._base}/api/missions", json=body)
        r.raise_for_status()
        return Mission(**r.json())

    # ── Actions ──

    async def plan_mission(self, mission_id: str) -> Mission:
        r = await self.client.post(f"{self._base}/api/missions/{mission_id}/plan", json={})
        r.raise_for_status()
        return Mission(**r.json())

    async def approve_mission(self, mission_id: str, approved: bool = True) -> Mission:
        body = {"approved": approved, "decision": "approve_mission" if approved else "reject"}
        r = await self.client.post(f"{self._base}/api/missions/{mission_id}/approve", json=body)
        r.raise_for_status()
        return Mission(**r.json())

    async def run_mission(self, mission_id: str) -> Mission:
        r = await self.client.post(f"{self._base}/api/missions/{mission_id}/run", json={})
        r.raise_for_status()
        return Mission(**r.json())

    async def pause_mission(self, mission_id: str) -> Mission:
        r = await self.client.post(f"{self._base}/api/missions/{mission_id}/pause", json={})
        r.raise_for_status()
        return Mission(**r.json())
