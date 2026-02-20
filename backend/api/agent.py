from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.agentic.service import agent_run_service
from backend.security.trust import classify_request
from backend.workspaces.routing import resolve_workspace_id

router = APIRouter(tags=["agent"])


def _error_payload(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "retryable": retryable,
        }
    }


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


@router.post("/agent", summary="Submit an async agent run")
async def submit_agent_run(request: Request, payload: Dict[str, Any]):
    prompt = payload.get("prompt") or payload.get("message") or payload.get("text")
    if not prompt or not isinstance(prompt, str):
        raise HTTPException(
            status_code=400,
            detail=_error_payload("bad_request", "Missing prompt", "Provide 'prompt' as a string", False),
        )

    user_id = getattr(request.state, "user_id", "") or ""
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("missing_user_id", "Missing user_id", "Identity middleware required", False),
        )
    workspace_id = resolve_workspace_id(payload, request.headers)
    request_payload = dict(payload)
    request_payload["user_id"] = user_id
    request_payload["workspace_id"] = workspace_id

    trust = classify_request(request_payload, request.headers)
    require_confirm_raw = request_payload.get("tool_require_confirm")
    if require_confirm_raw is None:
        require_confirm = None
    else:
        require_confirm = _coerce_bool(require_confirm_raw)

    run_id = str(payload.get("run_id") or payload.get("runId") or "").strip() or None
    idempotency_key = (
        str(payload.get("idempotency_key") or payload.get("idempotencyKey") or "").strip() or None
    )
    lane = str(payload.get("lane") or "main").strip() or "main"
    session_key = str(payload.get("session_key") or payload.get("sessionKey") or "").strip()
    if not session_key:
        session_key = f"user:{user_id}:workspace:{workspace_id}"

    accepted = await agent_run_service.submit_run(
        payload=request_payload,
        trust=trust,
        require_confirm=require_confirm,
        session_key=session_key,
        lane=lane,
        run_id=run_id,
        idempotency_key=idempotency_key,
    )
    return accepted


@router.post("/agent/wait", summary="Wait for an async agent run")
async def wait_agent_run(payload: Dict[str, Any]):
    run_id = str(payload.get("run_id") or payload.get("runId") or "").strip()
    if not run_id:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("bad_request", "Missing run_id", "Provide run_id as a string", False),
        )
    raw_timeout = payload.get("timeout_ms", payload.get("timeoutMs", 30_000))
    try:
        timeout_ms = max(int(raw_timeout), 0)
    except Exception:
        timeout_ms = 30_000
    include_result = _coerce_bool(payload.get("include_result", payload.get("includeResult", False)))

    snapshot = await agent_run_service.wait_for_run(run_id, timeout_ms=timeout_ms, include_result=include_result)
    if snapshot is None:
        return {
            "run_id": run_id,
            "status": "timeout",
        }
    return snapshot


@router.get("/agent/{run_id}", summary="Get async agent run status")
async def get_agent_run(run_id: str, include_result: bool = False):
    status = await agent_run_service.get_run_status(run_id, include_result=include_result)
    if status is None:
        return JSONResponse(
            status_code=404,
            content=_error_payload("run_not_found", "Run not found", run_id, False),
        )
    return status
