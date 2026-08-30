"""Experience API V1.0 适配层：把 NexaraRuntime 真实状态映射为产品体验层契约。

契约权威：NEXARA-PRODUCT/MockAPI/NEXARA-Experience-API-契约.md（MP-01，V1.0）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

_PLANNING_STATES = {
    "Intent",
    "Context",
    "Contract",
    "Plan",
    "Simulation",
    "Approval",
    "Created",
    "Triaged",
    "Contracted",
    "Planned",
    "Scheduled",
    "AwaitingApproval",
}
_EXECUTING_STATES = {
    "Execution",
    "Verification",
    "Evidence",
    "MemoryPatch",
    "Evaluation",
    "Running",
    "Verifying",
    "Degraded",
    "RollingBack",
}
_PAUSED_STATES = {"Paused", "Blocked"}
_COMPLETED_STATES = {"Completed", "Failed", "RolledBack", "Cancelled"}


def map_mission_state(state: str) -> str:
    if state in _EXECUTING_STATES:
        return "executing"
    if state in _PAUSED_STATES:
        return "paused"
    if state in _COMPLETED_STATES:
        return "completed"
    return "planning"


def envelope(data: Any, **meta_extra: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat()}
    meta.update(meta_extra)
    return {"success": True, "data": data, "error": None, "meta": meta}


def paginate(items: list[Any], page: int, limit: int) -> tuple[list[Any], dict[str, int]]:
    page = max(page, 1)
    limit = max(limit, 1)
    start = (page - 1) * limit
    return items[start : start + limit], {"total": len(items), "page": page, "limit": limit}


def _experience_mission(record: dict[str, Any]) -> dict[str, Any]:
    spec = record.get("spec", {})
    state = record.get("state", "Intent")
    steps = (record.get("plan") or {}).get("steps", [])
    subtasks = [
        {
            "id": step.get("step_id", f"step-{index}"),
            "title": step.get("title", ""),
            "done": step.get("status") == "completed",
        }
        for index, step in enumerate(steps)
    ]
    if steps:
        progress = round(sum(1 for s in subtasks if s["done"]) / len(steps), 2)
    else:
        progress = {"planning": 0.1, "executing": 0.5, "paused": 0.5, "completed": 1.0}[map_mission_state(state)]
    next_pending = next((s["title"] for s in subtasks if not s["done"]), "")
    if map_mission_state(state) == "completed":
        next_step = "已归档"
    else:
        next_step = next_pending or "等待下一步指令"
    return {
        "id": record.get("mission_id", ""),
        "title": spec.get("title") or spec.get("objective", ""),
        "goal": spec.get("objective", ""),
        "status": map_mission_state(state),
        "progress": progress,
        "nextStep": next_step,
        "subtasks": subtasks,
        "updatedText": relative_time_text(spec.get("created_at", "")),
    }


def relative_time_text(iso_timestamp: str, now: datetime | None = None) -> str:
    if not iso_timestamp:
        return "刚刚"
    now = now or datetime.now(timezone.utc)
    try:
        moment = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return "刚刚"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    seconds = max(0, int((now - moment).total_seconds()))
    if seconds < 60:
        return "刚刚"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} 小时前"
    days = hours // 24
    if days == 1:
        return "昨天"
    return f"{days} 天前"


def build_experience_router(runtime: Any) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["experience"])

    @router.get("/missions")
    def missions(page: int = 1, limit: int = 20) -> dict[str, Any]:
        items = [_experience_mission(record) for record in runtime.list_missions()]
        items.reverse()
        page_items, page_meta = paginate(items, page, limit)
        return envelope(page_items, **page_meta)

    return router
