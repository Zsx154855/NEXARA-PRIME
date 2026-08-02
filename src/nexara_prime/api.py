from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Settings
try:
    from .knowledge_universe import scan_vault
except ImportError:
    scan_vault = None
from .runtime import NexaraRuntime
from .sovereign_coordinator import (
    ControlAction, ControlRequest, SovereignExecutionCoordinator,
)


class MissionCreateRequest(BaseModel):
    objective: str
    source_dir: str | None = None
    risk: str | None = "R0"


class ApprovalRequestBody(BaseModel):
    approved: bool | None = True
    actor: str = "human"
    note: str = "Approved by human operator."
    decision: str | None = None
    scope: str | None = None


class SafeModeBody(BaseModel):
    enabled: bool = True


class ControlRequestBody(BaseModel):
    """Phase C control request body — action/actor/reason/scope."""
    action: str = ""
    actor_id: str = "human"
    reason: str = ""
    scope: str = "local"


def create_app(runtime: NexaraRuntime | None = None) -> FastAPI:
    runtime = runtime or NexaraRuntime(Settings.from_env(Path.cwd()))
    app = FastAPI(title="NEXARA PRIME", version="0.1.0")
    app.state.runtime = runtime
    default_vault = Path(__file__).resolve().parents[2] / "docs"
    app.state.knowledge_vault = Path(os.environ.get("NEXARA_VAULT_PATH", default_vault))

    # Phase C: Sovereign Execution Coordinator (bridges brain→runtime)
    coordinator = SovereignExecutionCoordinator(runtime)
    app.state.coordinator = coordinator

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
        data = runtime.overview()
        # Enrich with inspect_mission snapshots; SDK compatibility fields
        enriched = []
        for m in runtime.list_missions()[-20:]:
            try:
                snap = runtime.inspect_mission(m["mission_id"])
                snap["state"] = snap.get("current_state", "Intent")
                enriched.append(snap)
            except KeyError:
                enriched.append(m)
        data["missions"] = enriched
        return data

    @app.get("/api/missions")
    def list_missions() -> list[dict[str, Any]]:
        return runtime.list_missions()

    @app.post("/api/missions")
    def create_mission(body: MissionCreateRequest) -> dict[str, Any]:
        try:
            mission = runtime.create_mission(body.objective, body.source_dir)
            return runtime.inspect_mission(mission.mission_id)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}")
    def status(mission_id: str) -> dict[str, Any]:
        try:
            return runtime.inspect_mission(mission_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/plan")
    def plan(mission_id: str) -> dict[str, Any]:
        try:
            runtime.plan_mission(mission_id)
            return runtime.inspect_mission(mission_id)
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/approve")
    def approve(mission_id: str, body: ApprovalRequestBody) -> dict[str, Any]:
        try:
            runtime.approve_mission(mission_id, bool(body.approved), body.actor, body.note, body.decision, body.scope)
            return runtime.inspect_mission(mission_id)
        except (KeyError, ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/run")
    def run(mission_id: str) -> dict[str, Any]:
        try:
            runtime.run_mission(mission_id)
            return runtime.inspect_mission(mission_id)
        except (KeyError, ValueError, RuntimeError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/pause")
    def pause(mission_id: str) -> dict[str, Any]:
        runtime.pause(mission_id)
        return runtime.inspect_mission(mission_id)

    @app.post("/api/missions/{mission_id}/resume")
    def resume(mission_id: str) -> dict[str, Any]:
        runtime.resume(mission_id)
        return runtime.inspect_mission(mission_id)

    @app.post("/api/missions/{mission_id}/rollback")
    def rollback(mission_id: str) -> dict[str, Any]:
        try:
            runtime.rollback(mission_id)
            return runtime.inspect_mission(mission_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/safe-mode")
    def safe_mode(mission_id: str, body: SafeModeBody) -> dict[str, Any]:
        runtime.safe_mode(mission_id, body.enabled)
        return runtime.inspect_mission(mission_id)

    @app.get("/api/approvals")
    def approvals(mission_id: str | None = None) -> list[dict[str, Any]]:
        return runtime.approvals.list(mission_id)

    @app.get("/api/receipts")
    def receipts(mission_id: str | None = None) -> dict[str, Any]:
        if mission_id:
            return runtime.evidence.verify_receipt_chain(mission_id)
        missions = runtime.list_missions()
        results = {}
        for m in missions:
            mid = m["mission_id"]
            invocations = runtime.store.list_records("tool", mid)
            if invocations:
                results[mid] = runtime.evidence.verify_receipt_chain(mid)
        return {"missions": results, "total": len(results)}

    @app.get("/api/tools")
    def tools(mission_id: str | None = None) -> list[dict[str, Any]]:
        return runtime.tools.list_invocations(mission_id)

    @app.get("/api/missions/{mission_id}/tools")
    def mission_tools(mission_id: str) -> list[dict[str, Any]]:
        return runtime.tools.list_invocations(mission_id)

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

    # ═══ Phase C: Sovereign Control API ═══════════════════════════════════════

    @app.get("/api/control/overview")
    def control_overview() -> dict[str, Any]:
        return coordinator.runtime_overview()

    @app.get("/api/missions/{mission_id}/control")
    def mission_control(mission_id: str) -> dict[str, Any]:
        return coordinator.mission_control_status(mission_id)

    @app.post("/api/missions/{mission_id}/cancel")
    def cancel_mission(mission_id: str, body: ControlRequestBody) -> dict[str, Any]:
        req = ControlRequest(
            request_id=f"req_{os.urandom(8).hex()}",
            actor_id=body.actor_id, mission_id=mission_id, project_id="nexara",
            trace_id=f"tr_{os.urandom(8).hex()}",
            action=ControlAction.CANCEL, reason=body.reason, scope=body.scope,
        )
        result = coordinator.handle_control(req)
        if not result.ok:
            raise HTTPException(status_code=409, detail=result.reason_message)
        return result.__dict__

    @app.post("/api/missions/{mission_id}/takeover")
    def takeover_mission(mission_id: str, body: ControlRequestBody) -> dict[str, Any]:
        req = ControlRequest(
            request_id=f"req_{os.urandom(8).hex()}",
            actor_id=body.actor_id, mission_id=mission_id, project_id="nexara",
            trace_id=f"tr_{os.urandom(8).hex()}",
            action=ControlAction.TAKEOVER, reason=body.reason, scope=body.scope,
        )
        result = coordinator.handle_control(req)
        if not result.ok:
            raise HTTPException(status_code=409, detail=result.reason_message)
        return result.__dict__

    @app.post("/api/missions/{mission_id}/release-takeover")
    def release_takeover(mission_id: str, body: ControlRequestBody) -> dict[str, Any]:
        req = ControlRequest(
            request_id=f"req_{os.urandom(8).hex()}",
            actor_id=body.actor_id, mission_id=mission_id, project_id="nexara",
            trace_id=f"tr_{os.urandom(8).hex()}",
            action=ControlAction.RELEASE_TAKEOVER, reason=body.reason, scope=body.scope,
        )
        result = coordinator.handle_control(req)
        if not result.ok:
            raise HTTPException(status_code=409, detail=result.reason_message)
        return result.__dict__

    @app.post("/api/missions/{mission_id}/recover")
    def recover_mission(mission_id: str, body: ControlRequestBody) -> dict[str, Any]:
        req = ControlRequest(
            request_id=f"req_{os.urandom(8).hex()}",
            actor_id=body.actor_id, mission_id=mission_id, project_id="nexara",
            trace_id=f"tr_{os.urandom(8).hex()}",
            action=ControlAction.RECOVER, reason=body.reason, scope=body.scope,
        )
        result = coordinator.handle_control(req)
        if not result.ok:
            raise HTTPException(status_code=404, detail=result.reason_message)
        return result.__dict__

    @app.get("/api/approvals/pending")
    def pending_approvals() -> list[dict[str, Any]]:
        return coordinator.pending_approvals()

    @app.post("/api/approvals/{decision_id}/decision")
    def approval_decision(decision_id: str, body: ApprovalRequestBody) -> dict[str, Any]:
        d = body.decision or ("approved" if body.approved else "rejected")
        result = coordinator.decide_approval(decision_id, d, body.actor)
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result.get("reason", "unknown"))
        return result

    @app.post("/api/approvals/{decision_id}/revoke")
    def revoke_approval(decision_id: str) -> dict[str, Any]:
        result = coordinator.revoke_approval(decision_id)
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result.get("reason", "unknown"))
        return result

    @app.get("/api/knowledge-universe")
    def knowledge_universe() -> dict[str, Any]:
        if scan_vault is None:
            raise HTTPException(status_code=503, detail="knowledge_universe module not available")
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

    ui_root = runtime.settings.ui_root or (Path(__file__).resolve().parents[2] / "ui")
    if ui_root.exists():
        # Serve only the built Next.js static export. Missing builds should be
        # visible instead of silently falling back to legacy UI assets.
        out_root = ui_root / "out"
        if out_root.exists() and (out_root / "index.html").exists():
            app.mount("/console", StaticFiles(directory=out_root, html=True), name="console")
        universe_root = ui_root / "knowledge-universe"
        if universe_root.exists():
            app.mount("/knowledge-universe", StaticFiles(directory=universe_root, html=True), name="knowledge-universe")
        truth_root = ui_root / "runtime-truth"
        if truth_root.exists():
            app.mount("/runtime-truth", StaticFiles(directory=truth_root, html=True), name="runtime-truth")

    return app


app = create_app()
