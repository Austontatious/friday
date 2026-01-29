from __future__ import annotations

from fastapi import APIRouter

from backend.core.health_checks import is_ok, jobs_status, memory_status, service_status
from backend.core.llm import llm_client

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/readyz")
def readyz():
    llm_status = llm_client.status()
    memory = memory_status()
    jobs = jobs_status()

    services = {
        "llm": llm_status,
        "vision": service_status("FRIDAY_VISION_ENABLED", "VISION_BASE_URL"),
        "stt": service_status("FRIDAY_STT_ENABLED", "STT_BASE_URL"),
        "tts": service_status("FRIDAY_TTS_ENABLED", "TTS_BASE_URL"),
        "avatar": service_status("FRIDAY_AVATAR_ENABLED", "AVATAR_BASE_URL"),
    }

    ok = all(is_ok(status) for status in services.values()) and is_ok(memory) and is_ok(jobs)
    return {
        "ok": ok,
        "services": services,
        "memory": memory,
        "jobs": jobs,
    }
