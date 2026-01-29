from __future__ import annotations

from typing import Any, Dict

from backend.audit.logger import log_event
from backend.core.health_checks import env_bool, jobs_status, memory_status, service_status
from backend.core.llm import llm_client


def _available_from_status(status: Dict[str, Any]) -> bool:
    return status.get("enabled") is True and status.get("status") == "healthy"


_LAST_SNAPSHOT: Dict[str, Any] = {}


def get_capabilities() -> Dict[str, Any]:
    enabled = {
        "llm": env_bool("FRIDAY_LLM_ENABLED", "0"),
        "stt": env_bool("FRIDAY_STT_ENABLED", "0"),
        "tts": env_bool("FRIDAY_TTS_ENABLED", "0"),
        "vision": env_bool("FRIDAY_VISION_ENABLED", "0"),
        "gesture": env_bool("FRIDAY_GESTURE_ENABLED", "0"),
        "avatar": env_bool("FRIDAY_AVATAR_ENABLED", "0"),
        "jobs": env_bool("FRIDAY_JOBS_ENABLED", "0"),
        "memory_persist": env_bool("FRIDAY_MEMORY_PERSIST_ENABLED", "0"),
        "memory_vector": env_bool("FRIDAY_MEMORY_VECTOR_ENABLED", "0"),
        "memory_facts": env_bool("FRIDAY_MEMORY_FACTS_ENABLED", "0"),
        "memory_summaries": env_bool("FRIDAY_MEMORY_SUMMARIES_ENABLED", "0"),
    }

    llm_status = llm_client.status()
    stt_status = service_status("FRIDAY_STT_ENABLED", "STT_BASE_URL")
    tts_status = service_status("FRIDAY_TTS_ENABLED", "TTS_BASE_URL")
    vision_status = service_status("FRIDAY_VISION_ENABLED", "VISION_BASE_URL")
    avatar_status = service_status("FRIDAY_AVATAR_ENABLED", "AVATAR_BASE_URL")
    memory = memory_status()
    jobs = jobs_status()

    available = {
        "llm": _available_from_status(llm_status),
        "stt": _available_from_status(stt_status),
        "tts": _available_from_status(tts_status),
        "vision": _available_from_status(vision_status),
        "gesture": False,
        "avatar": _available_from_status(avatar_status),
        "jobs": _available_from_status(jobs),
        "memory_persist": _available_from_status(memory),
        "memory_vector": False,
        "memory_facts": enabled.get("memory_facts", False),
        "memory_summaries": enabled.get("memory_summaries", False),
    }

    snapshot = {"enabled": enabled, "available": available}
    global _LAST_SNAPSHOT
    if _LAST_SNAPSHOT != snapshot:
        log_event("capabilities_snapshot_changed", {"snapshot": snapshot})
        _LAST_SNAPSHOT = snapshot
    return snapshot
