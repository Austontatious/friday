from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict

from backend.core.emotion_lite import analyze as analyze_emotion, enabled as emotion_enabled
from backend.core.llm import llm_client, LLMDisabledError, LLMConfigError, LLMRequestError
from backend.memory.memory import MemoryStore


@dataclass
class ChatError(Exception):
    code: str
    message: str
    detail: Any = None
    retryable: bool = False
    status_code: int = 500


_memory = MemoryStore()
LLM_DISABLED_MESSAGE = "[LLM disabled] Set FRIDAY_LLM_ENABLED=1 and LLM_BASE_URL to enable chat."


def _resolve_user_id(payload: Dict[str, Any]) -> str:
    return (
        str(payload.get("user_id") or "")
        or str(payload.get("session_id") or "")
        or "default"
    )


def _history_limit() -> int:
    try:
        limit = int(os.getenv("FRIDAY_CONTEXT_TURNS", "20"))
    except ValueError:
        return 20
    return max(limit, 0)


async def run_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = payload.get("prompt") or payload.get("message") or payload.get("text")
    user_id = _resolve_user_id(payload)
    history = _memory.load_thread(user_id, limit=_history_limit())

    try:
        reply = await llm_client.generate(prompt, history)
    except LLMDisabledError:
        reply = LLM_DISABLED_MESSAGE
    except LLMConfigError as exc:
        raise ChatError("llm_not_configured", "LLM not configured", str(exc), False, 503)
    except LLMRequestError as exc:
        raise ChatError("llm_unhealthy", "LLM request failed", str(exc), True, 502)
    except Exception as exc:
        raise ChatError("chat_failed", "Chat failed", str(exc), True, 500)

    user_meta = None
    if emotion_enabled():
        user_meta = {"affect": analyze_emotion(prompt)}

    _memory.append(user_id, "user", prompt, meta=user_meta)
    _memory.append(user_id, "assistant", reply)

    return {
        "text": reply,
        "tools": [],
        "meta": {"user_id": user_id},
    }
