from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Dict, Optional, Set

from backend.core.emotion_lite import analyze as analyze_emotion, enabled as emotion_enabled
from backend.core.llm import llm_client, LLMDisabledError, LLMConfigError, LLMRequestError
from backend.core.prompt_builder import build_messages
from backend.security.trust import TrustContext
from backend.audit.logger import log_event
from backend.tools.engine import execute_tool_call
from backend.tools.parser import parse_tool_calls
from backend.memory.service import memory_service


@dataclass
class ChatError(Exception):
    code: str
    message: str
    detail: Any = None
    retryable: bool = False
    status_code: int = 500


LLM_DISABLED_MESSAGE = "[LLM disabled] Set FRIDAY_LLM_ENABLED=1 and LLM_BASE_URL to enable chat."


def _resolve_user_id(payload: Dict[str, Any]) -> str:
    return str(payload.get("user_id") or "").strip()


def _history_limit() -> int:
    try:
        limit = int(os.getenv("FRIDAY_CONTEXT_TURNS", "20"))
    except ValueError:
        return 20
    return max(limit, 0)


def _approved_set(value: Any) -> Set[str]:
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


async def run_chat(payload: Dict[str, Any], trust: TrustContext, require_confirm: Optional[bool]) -> Dict[str, Any]:
    prompt = payload.get("prompt") or payload.get("message") or payload.get("text")
    user_id = _resolve_user_id(payload)
    if not user_id:
        raise ChatError("missing_user_id", "Missing user_id", "user_id is required", False, 400)
    workspace_id = str(payload.get("workspace_id") or "").strip() or "default"
    memory_bundle = memory_service.retrieve(user_id, workspace_id, prompt, limit_turns=_history_limit())
    messages = build_messages(prompt, memory_bundle, tool_schema=None)

    try:
        reply = await llm_client.generate_messages(messages)
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

    memory_service.append_turn(user_id, workspace_id, "user", prompt, meta=user_meta)

    tool_results = []
    tool_calls, tool_errors = parse_tool_calls(reply)
    if tool_errors:
        log_event("tool_call_invalid", {"errors": tool_errors, "raw": reply}, user_id, workspace_id)

    debug_tool_errors = _env_bool("FRIDAY_DEBUG_TOOL_ERRORS", "0")
    approved_ids = _approved_set(payload.get("approved_tool_ids"))
    require_confirm_flag = require_confirm
    for call in tool_calls:
        approved = call.get("id") in approved_ids or bool(payload.get("tool_confirmed"))
        result = execute_tool_call(
            call=call,
            context_user_id=user_id,
            workspace_id=workspace_id,
            require_confirm=require_confirm_flag,
            approved=approved,
            trust=trust,
        )
        tool_results.append(result)
        if result.get("ok") or debug_tool_errors:
            tool_payload = json.dumps(result, ensure_ascii=False)
            memory_service.append_turn(user_id, workspace_id, "tool", tool_payload)
            messages.append({"role": "tool", "content": tool_payload})

    if tool_results and any(result.get("ok") for result in tool_results):
        try:
            reply = await llm_client.generate_messages(messages)
        except LLMDisabledError:
            pass

    if tool_results and not any(result.get("ok") for result in tool_results):
        reply = "Tool call requires confirmation or is blocked. Provide approval to proceed."

    memory_service.append_turn(user_id, workspace_id, "assistant", reply)
    consolidation_job = memory_service.maybe_consolidate(user_id, workspace_id)

    return {
        "text": reply,
        "tools": tool_results,
        "meta": {"user_id": user_id, "workspace_id": workspace_id, "consolidation_job_id": consolidation_job},
    }
