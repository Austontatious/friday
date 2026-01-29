from __future__ import annotations

import os
from pathlib import Path
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
    memory_status = _memory_status()

    services = {
        "llm": llm_status,
        "vision": _service_status("FRIDAY_VISION_ENABLED", "VISION_BASE_URL"),
        "stt": _service_status("FRIDAY_STT_ENABLED", "STT_BASE_URL"),
        "tts": _service_status("FRIDAY_TTS_ENABLED", "TTS_BASE_URL"),
        "avatar": _service_status("FRIDAY_AVATAR_ENABLED", "AVATAR_BASE_URL"),
    }

    ok = all(_is_ok(status) for status in services.values()) and _is_ok(memory_status)
    return {
        "ok": ok,
        "services": services,
        "memory": memory_status,
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


def _memory_status() -> Dict[str, Any]:
    enabled = _env_bool("FRIDAY_MEMORY_PERSIST_ENABLED", "0")
    if not enabled:
        return {"enabled": False, "status": "disabled"}

    data_dir = os.getenv("FRIDAY_DATA_DIR", "/data")
    ok, detail = _probe_dir(data_dir)
    return {"enabled": True, "status": "healthy" if ok else "unhealthy", "detail": detail}


def _normalize_url(url: str) -> str:
    base = url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    if "/v1/" in base:
        prefix = base.split("/v1", 1)[0] + "/v1"
        return f"{prefix}/models"
    return base


def _probe_dir(path: str) -> Tuple[bool, str]:
    try:
        candidate = Path(path)
        candidate.mkdir(parents=True, exist_ok=True)
        test_file = candidate / ".friday_write_check"
        with test_file.open("w", encoding="utf-8") as handle:
            handle.write("ok")
        test_file.unlink(missing_ok=True)
        return True, "writable"
    except Exception as exc:
        return False, f"unwritable:{exc}"


def _probe(url: str) -> Tuple[bool, str]:
    timeout = float(os.getenv("FRIDAY_SERVICE_HEALTH_TIMEOUT", "2"))
    target = _normalize_url(url)
    try:
        resp = httpx.get(target, timeout=timeout)
        if resp.status_code < 400:
            return True, "reachable"
        return False, f"bad_status_{resp.status_code}"
    except Exception as exc:
        return False, f"unreachable:{exc}"


def _is_ok(status: Dict[str, Any]) -> bool:
    if status.get("enabled") is False:
        return True
    return status.get("status") == "healthy"
