from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["stubs"])


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def _disabled(service: str, flag: str) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "message": f"[{service} disabled] Set {flag}=1",
    }


def _not_implemented(service: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "code": "not_implemented",
                "message": "Service enabled but not implemented",
                "detail": service,
                "retryable": False,
            }
        },
    )


@router.post("/stt")
def stt_stub():
    if not _env_bool("FRIDAY_STT_ENABLED", "0"):
        return _disabled("STT", "FRIDAY_STT_ENABLED")
    return _not_implemented("stt")


@router.post("/tts")
def tts_stub():
    if not _env_bool("FRIDAY_TTS_ENABLED", "0"):
        return _disabled("TTS", "FRIDAY_TTS_ENABLED")
    return _not_implemented("tts")


@router.post("/vision")
def vision_stub():
    if not _env_bool("FRIDAY_VISION_ENABLED", "0"):
        return _disabled("Vision", "FRIDAY_VISION_ENABLED")
    return _not_implemented("vision")


@router.post("/avatar")
def avatar_stub():
    if not _env_bool("FRIDAY_AVATAR_ENABLED", "0"):
        return _disabled("Avatar", "FRIDAY_AVATAR_ENABLED")
    return _not_implemented("avatar")
