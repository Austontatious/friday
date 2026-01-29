from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

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


def _resolve_user_id(payload: Dict[str, Any]) -> str:
    return (
        str(payload.get("user_id") or "")
        or str(payload.get("session_id") or "")
        or "default"
    )


async def run_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = payload.get("prompt") or payload.get("message") or payload.get("text")
    user_id = _resolve_user_id(payload)
    history = _memory.load_thread(user_id)

    try:
        reply = await llm_client.generate(prompt, history)
    except LLMDisabledError as exc:
        raise ChatError("llm_disabled", "LLM is disabled", str(exc), False, 503)
    except LLMConfigError as exc:
        raise ChatError("llm_not_configured", "LLM not configured", str(exc), False, 503)
    except LLMRequestError as exc:
        raise ChatError("llm_error", "LLM request failed", str(exc), True, 502)
    except Exception as exc:
        raise ChatError("chat_failed", "Chat failed", str(exc), True, 500)

    _memory.append(user_id, "user", prompt)
    _memory.append(user_id, "assistant", reply)

    return {
        "text": reply,
        "tools": [],
        "meta": {"user_id": user_id},
    }
