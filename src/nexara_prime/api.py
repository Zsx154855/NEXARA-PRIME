from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
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

    ui_root = Path(__file__).resolve().parents[2] / "ui"
    if ui_root.exists():
        app.mount("/console", StaticFiles(directory=ui_root, html=True), name="console")

    return app


app = create_app()
