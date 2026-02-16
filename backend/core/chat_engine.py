from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

from backend.core.emotion_lite import analyze as analyze_emotion, enabled as emotion_enabled
from backend.core.llm import llm_client, LLMDisabledError, LLMConfigError, LLMRequestError
from backend.core.prompt_builder import build_messages
from backend.security.trust import TrustContext
from backend.audit.logger import log_event
from backend.tools.engine import execute_tool_call
from backend.tools.parser import parse_tool_calls
from backend.memory.factory import get_memory_provider, memory_namespace, memory_profile, selected_memory_provider_name
from backend.memory.provider import extract_memory_candidates, render_system_memory_block
from backend.memory.service import memory_service

logger = logging.getLogger("friday.chat.engine")


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


def _truncate(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "...(truncated)"


def _empty_memory_bundle(recent_turns: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "recent_turns": recent_turns,
        "relevant_facts": [],
        "relevant_summaries": [],
        "open_loops": [],
        "commitments": [],
        "tasks": [],
        "identity": {},
    }


def _base_memory_meta(provider_name: str) -> Dict[str, Any]:
    return {
        "provider": provider_name,
        "accepted_ids": [],
        "pending_ids": [],
        "pending_reasons": [],
        "rejected": {"count": 0, "reasons": []},
    }


async def run_chat(payload: Dict[str, Any], trust: TrustContext, require_confirm: Optional[bool]) -> Dict[str, Any]:
    prompt = str(payload.get("prompt") or payload.get("message") or payload.get("text") or "")
    user_id = _resolve_user_id(payload)
    if not user_id:
        raise ChatError("missing_user_id", "Missing user_id", "user_id is required", False, 400)
    workspace_id = str(payload.get("workspace_id") or "").strip() or "default"
    entity_id = user_id or "ent_user"
    namespace = memory_namespace()
    profile = memory_profile()
    configured_provider = selected_memory_provider_name()
    memory_provider = get_memory_provider()

    recent_turns = memory_service.load_recent_turns(user_id, workspace_id, limit=_history_limit())
    memory_bundle = _empty_memory_bundle(recent_turns)

    system_memory_block = ""
    try:
        rehydrated = memory_provider.rehydrate(
            prompt,
            entity_id,
            namespace=namespace,
            profile=profile,
            k=8,
        )
        cards = rehydrated.get("cards") if isinstance(rehydrated, dict) else []
        if isinstance(cards, list):
            system_memory_block = render_system_memory_block(cards, max_cards=8, max_bullets=3)
    except Exception as exc:
        logger.warning("Memory rehydrate failed; continuing without injected memory (%s)", exc)
        system_memory_block = ""

    if system_memory_block and _env_bool("FRIDAY_DEBUG_MEMORY", "0"):
        logger.info("Injected <SYSTEM_MEMORY> block: %s", _truncate(system_memory_block))

    messages = build_messages(
        prompt,
        memory_bundle,
        tool_schema=None,
        system_memory_block=system_memory_block,
    )

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

    if configured_provider not in {"muninn", "legacy", "none"}:
        configured_provider = getattr(memory_provider, "name", "none")
    memory_meta: Dict[str, Any] = _base_memory_meta(configured_provider)
    candidates = extract_memory_candidates(prompt, entity_id, source_id=user_id)
    if candidates:
        try:
            staged = memory_provider.stage(candidates, namespace=namespace, ttl_seconds=86400)
            if isinstance(staged, dict):
                accepted_ids = staged.get("accepted_ids")
                pending_ids = staged.get("pending_ids")
                pending_reasons = staged.get("pending_reasons")
                reject_reasons = staged.get("reject_reasons")
                if isinstance(accepted_ids, list):
                    memory_meta["accepted_ids"] = [str(item) for item in accepted_ids]
                if isinstance(pending_ids, list):
                    memory_meta["pending_ids"] = [str(item) for item in pending_ids]
                if isinstance(pending_reasons, list):
                    memory_meta["pending_reasons"] = [str(item) for item in pending_reasons]
                rejected_count = staged.get("rejected")
                if isinstance(reject_reasons, list):
                    memory_meta["rejected"]["reasons"] = [str(item) for item in reject_reasons]
                if isinstance(rejected_count, int):
                    memory_meta["rejected"]["count"] = rejected_count
                elif isinstance(memory_meta["rejected"]["reasons"], list):
                    memory_meta["rejected"]["count"] = len(memory_meta["rejected"]["reasons"])
        except Exception as exc:
            logger.warning("Memory stage failed; continuing without staged memory (%s)", exc)

    consolidation_job = memory_service.maybe_consolidate(user_id, workspace_id)

    return {
        "text": reply,
        "tools": tool_results,
        "meta": {"user_id": user_id, "workspace_id": workspace_id, "consolidation_job_id": consolidation_job},
        "memory": memory_meta,
    }
