from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.memory.service import memory_service
from backend.workspaces.routing import resolve_workspace_id

router = APIRouter(tags=["memory-debug"])


def _env_bool(key: str, default: str = "0") -> bool:
    import os
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def _ensure_enabled() -> None:
    if not _env_bool("FRIDAY_DEBUG_APIS_ENABLED", "0"):
        raise HTTPException(status_code=403, detail=_error("debug_disabled", "Debug APIs are disabled", "Set FRIDAY_DEBUG_APIS_ENABLED=1"))


def _error(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {"error": {"code": code, "message": message, "detail": detail, "retryable": retryable}}


def _context(request: Request) -> Dict[str, str]:
    user_id = getattr(request.state, "user_id", "")
    workspace_id = resolve_workspace_id({}, request.headers)
    if not user_id:
        raise HTTPException(status_code=400, detail=_error("missing_user_id", "Missing user_id", "user_id is required"))
    return {"user_id": user_id, "workspace_id": workspace_id}


@router.get("/memory/facts")
def list_facts(request: Request, tag: Optional[str] = None, limit: Optional[int] = None):
    _ensure_enabled()
    ctx = _context(request)
    return memory_service.list_facts(ctx["user_id"], ctx["workspace_id"], tag=tag, limit=limit)


@router.post("/memory/facts")
def add_fact(request: Request, payload: Dict[str, Any]):
    _ensure_enabled()
    ctx = _context(request)
    try:
        fact = memory_service.remember_fact(
            ctx["user_id"],
            ctx["workspace_id"],
            payload.get("key", ""),
            payload.get("value", ""),
            tags=payload.get("tags"),
            confidence=payload.get("confidence"),
            pinned=bool(payload.get("pinned")),
            source="debug",
        )
    except Exception as exc:
        return JSONResponse(status_code=400, content=_error("fact_error", "Failed to add fact", str(exc)))
    return fact


@router.delete("/memory/facts/{key}")
def delete_fact(request: Request, key: str):
    _ensure_enabled()
    ctx = _context(request)
    removed = memory_service.forget_fact(ctx["user_id"], ctx["workspace_id"], key)
    return {"removed": removed}


@router.get("/memory/summaries")
def get_summary(request: Request):
    _ensure_enabled()
    ctx = _context(request)
    return memory_service.get_summary(ctx["user_id"], ctx["workspace_id"])


@router.post("/memory/consolidate")
def consolidate(request: Request):
    _ensure_enabled()
    ctx = _context(request)
    try:
        result = memory_service.consolidate_now(ctx["user_id"], ctx["workspace_id"])
    except Exception as exc:
        return JSONResponse(status_code=400, content=_error("consolidation_error", "Consolidation failed", str(exc)))
    return result
