from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .knowledge_universe import scan_vault
from .runtime import NexaraRuntime


class MissionCreateRequest(BaseModel):
    objective: str
    source_dir: str | None = None


class ApprovalRequestBody(BaseModel):
    approved: bool | None = True
    actor: str = "human"
    note: str = "Approved by human operator."
    decision: str | None = None
    scope: str | None = None


class SafeModeBody(BaseModel):
    enabled: bool = True


def create_app(runtime: NexaraRuntime | None = None) -> FastAPI:
    runtime = runtime or NexaraRuntime(Settings.from_env(Path.cwd()))
    app = FastAPI(title="NEXARA PRIME", version="0.1.0")
    app.state.runtime = runtime
    default_vault = Path(__file__).resolve().parents[2] / "docs"
    app.state.knowledge_vault = Path(os.environ.get("NEXARA_VAULT_PATH", default_vault))

    def get_mission(mission_id: str):
        try:
            return runtime.get_mission(mission_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/health")
    def health() -> dict[str, Any]:
        return runtime.health()

    @app.get("/api/runtime/overview")
    def overview() -> dict[str, Any]:
        return runtime.overview()

    @app.get("/api/missions")
    def list_missions() -> list[dict[str, Any]]:
        return runtime.list_missions()

    @app.post("/api/missions")
    def create_mission(body: MissionCreateRequest) -> dict[str, Any]:
        try:
            return runtime.create_mission(body.objective, body.source_dir).model_dump(mode="json")
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}")
    def status(mission_id: str) -> dict[str, Any]:
        return get_mission(mission_id).model_dump(mode="json")

    @app.post("/api/missions/{mission_id}/plan")
    def plan(mission_id: str) -> dict[str, Any]:
        try:
            return runtime.plan_mission(mission_id).model_dump(mode="json")
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/approve")
    def approve(mission_id: str, body: ApprovalRequestBody) -> dict[str, Any]:
        try:
            return runtime.approve_mission(mission_id, bool(body.approved), body.actor, body.note, body.decision, body.scope).model_dump(mode="json")
        except (KeyError, ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/run")
    def run(mission_id: str) -> dict[str, Any]:
        try:
            return runtime.run_mission(mission_id).model_dump(mode="json")
        except (KeyError, ValueError, RuntimeError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/pause")
    def pause(mission_id: str) -> dict[str, Any]:
        return runtime.pause(mission_id).model_dump(mode="json")

    @app.post("/api/missions/{mission_id}/resume")
    def resume(mission_id: str) -> dict[str, Any]:
        return runtime.resume(mission_id).model_dump(mode="json")

    @app.post("/api/missions/{mission_id}/rollback")
    def rollback(mission_id: str) -> dict[str, Any]:
        try:
            return runtime.rollback(mission_id).model_dump(mode="json")
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/safe-mode")
    def safe_mode(mission_id: str, body: SafeModeBody) -> dict[str, Any]:
        return runtime.safe_mode(mission_id, body.enabled).model_dump(mode="json")

    @app.get("/api/approvals")
    def approvals(mission_id: str | None = None) -> list[dict[str, Any]]:
        return runtime.approvals.list(mission_id)

    @app.get("/api/evidence")
    def evidence(mission_id: str | None = None) -> list[dict[str, Any]]:
        return runtime.evidence.list(mission_id)

    @app.get("/api/memory")
    def memory(mission_id: str | None = None) -> list[dict[str, Any]]:
        return runtime.memory.inspect(mission_id)

    @app.get("/api/memory/candidates")
    def memory_candidates(mission_id: str | None = None) -> list[dict[str, Any]]:
        return runtime.memory.candidates(mission_id)

    @app.get("/api/events/{mission_id}")
    def events(mission_id: str) -> list[dict[str, Any]]:
        return runtime.events.replay(mission_id)

    @app.post("/api/recovery/check")
    def recovery_check() -> dict[str, Any]:
        return runtime.recover().__dict__

    @app.get("/api/knowledge-universe")
    def knowledge_universe() -> dict[str, Any]:
        try:
            return scan_vault(app.state.knowledge_vault)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    # ── Adaptive Runtime API ──

    @app.get("/adaptive/status")
    def adaptive_status() -> dict[str, Any]:
        return runtime.adaptive_status()

    @app.get("/adaptive/missions/{mission_id}")
    def adaptive_mission(mission_id: str) -> dict[str, Any]:
        return runtime.adaptive_explain(mission_id)

    @app.get("/adaptive/missions/{mission_id}/explain")
    def adaptive_explain(mission_id: str) -> dict[str, Any]:
        return runtime.adaptive_explain(mission_id)

    @app.get("/adaptive/missions/{mission_id}/budget")
    def adaptive_budget(mission_id: str) -> dict[str, Any]:
        return runtime.adaptive_budget(mission_id)

    @app.get("/adaptive/missions/{mission_id}/agents")
    def adaptive_agents(mission_id: str) -> dict[str, Any]:
        return runtime.adaptive_agents(mission_id)

    @app.get("/adaptive/missions/{mission_id}/routing")
    def adaptive_routing(mission_id: str) -> dict[str, Any]:
        return runtime.adaptive_route(mission_id)

    @app.post("/adaptive/missions/{mission_id}/triage")
    def adaptive_triage(mission_id: str) -> dict[str, Any]:
        return runtime.adaptive_triage(mission_id)

    ui_root = Path(__file__).resolve().parents[2] / "ui"
    if ui_root.exists():
        app.mount("/console", StaticFiles(directory=ui_root, html=True), name="console")
        universe_root = ui_root / "knowledge-universe"
        if universe_root.exists():
            app.mount("/knowledge-universe", StaticFiles(directory=universe_root, html=True), name="knowledge-universe")
        truth_root = ui_root / "runtime-truth"
        if truth_root.exists():
            app.mount("/runtime-truth", StaticFiles(directory=truth_root, html=True), name="runtime-truth")

    return app


app = create_app()
