from __future__ import annotations

import os
from typing import Any, Dict, Tuple

import httpx
from fastapi import APIRouter

from backend.core.llm import llm_client

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/readyz")
def readyz():
    llm_status = llm_client.status()

    services = {
        "llm": llm_status,
        "coder": _service_status("FRIDAY_CODER_ENABLED", "CODER_BASE_URL"),
        "vision": _service_status("FRIDAY_VISION_ENABLED", "VLM_BASE_URL"),
        "omni": _service_status("FRIDAY_OMNI_ENABLED", "OMNI_BASE_URL"),
        "stt": _service_status("FRIDAY_STT_ENABLED", "STT_BASE_URL"),
        "tts": _service_status("FRIDAY_TTS_ENABLED", "TTS_BASE_URL"),
    }

    ok = all(_is_ok(status) for status in services.values())
    return {
        "ok": ok,
        "services": services,
        "memory": True,
    }


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def _service_status(enabled_key: str, url_key: str) -> Dict[str, Any]:
    enabled = _env_bool(enabled_key, "0")
    if not enabled:
        return {"enabled": False, "status": "disabled"}
    url = os.getenv(url_key, "").strip()
    if not url:
        return {"enabled": True, "status": "not_configured"}
    ok, detail = _probe(url)
    return {"enabled": True, "status": "healthy" if ok else "unhealthy", "detail": detail}


def _probe(url: str) -> Tuple[bool, str]:
    timeout = float(os.getenv("FRIDAY_SERVICE_HEALTH_TIMEOUT", "2"))
    try:
        resp = httpx.get(url, timeout=timeout)
        if resp.status_code < 400:
            return True, "reachable"
        return False, f"bad_status_{resp.status_code}"
    except Exception as exc:
        return False, f"unreachable:{exc}"


def _is_ok(status: Dict[str, Any]) -> bool:
    if status.get("enabled") is False:
        return True
    return status.get("status") == "healthy"
