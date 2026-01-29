from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core.chat_engine import run_chat, ChatError

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

    user_id = getattr(request.state, "user_id", "default")
    request_payload = dict(payload)
    request_payload["user_id"] = user_id

    try:
        response = await run_chat(request_payload)
    except ChatError as exc:
        return JSONResponse(status_code=exc.status_code, content=_error_payload(exc.code, exc.message, exc.detail, exc.retryable))

    return JSONResponse(content=response)
