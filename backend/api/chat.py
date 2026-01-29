from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core.chat_engine import run_chat, ChatError
from backend.security.trust import classify_request
from backend.workspaces.routing import resolve_workspace_id

router = APIRouter(tags=["chat"])


def _error_payload(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "retryable": retryable,
        }
    }


@router.post("/chat", summary="Text-only chat (Phase 0)")
async def chat(request: Request, payload: Dict[str, Any]):
    prompt = payload.get("prompt") or payload.get("message") or payload.get("text")
    if not prompt or not isinstance(prompt, str):
        raise HTTPException(status_code=400, detail=_error_payload("bad_request", "Missing prompt", "Provide 'prompt' as a string", False))

    user_id = getattr(request.state, "user_id", "") or ""
    if not user_id:
        raise HTTPException(status_code=400, detail=_error_payload("missing_user_id", "Missing user_id", "Identity middleware required", False))
    workspace_id = resolve_workspace_id(payload, request.headers)
    request_payload = dict(payload)
    request_payload["user_id"] = user_id
    request_payload["workspace_id"] = workspace_id

    try:
        trust = classify_request(request_payload, request.headers)
        require_confirm_raw = request_payload.get("tool_require_confirm")
        if require_confirm_raw is None:
            require_confirm = None
        else:
            require_confirm = str(require_confirm_raw).lower() in {"1", "true", "yes", "on"}
        response = await run_chat(request_payload, trust=trust, require_confirm=require_confirm)
    except ChatError as exc:
        return JSONResponse(status_code=exc.status_code, content=_error_payload(exc.code, exc.message, exc.detail, exc.retryable))

    reply = JSONResponse(content=response)
    reply.headers["X-Friday-User"] = user_id
    reply.headers["X-Friday-Workspace"] = str(workspace_id)
    return reply
