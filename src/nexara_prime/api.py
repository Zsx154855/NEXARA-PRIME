from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Settings
from .experience_api import build_experience_router
try:
    from .knowledge_universe import scan_vault
except ImportError:
    scan_vault = None
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


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationMessageRequest(BaseModel):
    content: str
    execution_mode: Literal["chat", "auto", "mission"] = "chat"
    # Backward-compatible bridge for older clients. New clients must use the
    # explicit execution_mode contract.
    execute_mission: bool | None = None
    idempotency_key: str | None = None


def create_app(runtime: NexaraRuntime | None = None) -> FastAPI:
    runtime = runtime or NexaraRuntime(Settings.from_env(Path.cwd()))
    app = FastAPI(title="NEXARA PRIME", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "https://nexara-prime.pages.dev",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.runtime = runtime
    default_vault = Path(__file__).resolve().parents[2] / "docs"
    app.state.knowledge_vault = Path(os.environ.get("NEXARA_VAULT_PATH", default_vault))

    app.include_router(build_experience_router(runtime))

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

    @app.get("/api/runtime/stats")
    def stats() -> dict[str, Any]:
        return runtime.stats()

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

    @app.post("/api/conversations")
    def create_conversation(body: ConversationCreateRequest) -> dict[str, Any]:
        try:
            conversation = runtime.conversations.create(body.title)
            return {**conversation, "messages": []}
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/conversations")
    def list_conversations() -> list[dict[str, Any]]:
        return [
            {
                **conversation,
                "messages": runtime.conversations.messages(
                    conversation["conversation_id"]
                ),
            }
            for conversation in runtime.conversations.list()
        ]

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(conversation_id: str) -> dict[str, Any]:
        try:
            conversation = runtime.conversations.get(conversation_id)
            return {
                **conversation,
                "messages": runtime.conversations.messages(conversation_id),
            }
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/conversations/{conversation_id}/messages")
    def list_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
        try:
            return runtime.conversations.messages(conversation_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/conversations/{conversation_id}/messages")
    def send_conversation_message(
        conversation_id: str,
        body: ConversationMessageRequest,
        idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        try:
            return runtime.answer_conversation(
                conversation_id,
                body.content,
                execution_mode=("mission" if body.execute_mission is True else body.execution_mode),
                idempotency_key=body.idempotency_key or idempotency_header,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            status = 409 if "idempotency" in str(exc) else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/conversations/{conversation_id}/close")
    def close_conversation(conversation_id: str) -> dict[str, Any]:
        try:
            conversation = runtime.conversations.close(conversation_id)
            return {
                **conversation,
                "messages": runtime.conversations.messages(conversation_id),
            }
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/conversations/{conversation_id}/reopen")
    def reopen_conversation(conversation_id: str) -> dict[str, Any]:
        try:
            conversation = runtime.conversations.reopen(conversation_id)
            return {
                **conversation,
                "messages": runtime.conversations.messages(conversation_id),
            }
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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

    @app.get("/api/memory/stats")
    def memory_stats() -> dict[str, Any]:
        """Aggregated memory statistics grouped by MemoryLayer.

        Response:
            {
              "total": int,
              "layers": {
                "working": int,      # short_term + temporary_context
                "episodic": int,     # decision + failure + experience
                "semantic": int,     # fact + user_fact + project_fact + preference
                "procedural": int    # patch + skill_improvement + system_rule
              }
            }
        """
        return runtime.memory_layers.stats()

    @app.get("/api/events/{mission_id}")
    def events(mission_id: str) -> list[dict[str, Any]]:
        return runtime.events.replay(mission_id)

    @app.post("/api/recovery/check")
    def recovery_check() -> dict[str, Any]:
        return runtime.recover().__dict__

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
