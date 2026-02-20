from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.emotion_lite import analyze as analyze_emotion, enabled as emotion_enabled
from backend.core.interaction_policy import build_interaction_policy
from backend.core.llm import llm_client, LLMDisabledError, LLMConfigError, LLMRequestError
from backend.core.prompt_builder import build_messages
from backend.core.response_shaper import shape_response
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


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _wants_coder_model(payload: Dict[str, Any]) -> bool:
    profile = str(payload.get("agent_profile") or payload.get("profile") or "").strip().lower()
    if profile in {"coding", "coder", "code"}:
        return True
    return _coerce_bool(payload.get("use_coder_model"))


def _coder_route_config() -> Optional[Dict[str, str]]:
    if not _env_bool("FRIDAY_CODER_ENABLED", "0"):
        return None
    base_url = os.getenv("FRIDAY_CODER_BASE_URL", "").strip()
    model_name = os.getenv("FRIDAY_CODER_MODEL_NAME", "").strip()
    api_key = os.getenv("FRIDAY_CODER_API_KEY", "").strip()
    if not base_url or not model_name:
        return None
    return {
        "base_url": base_url,
        "model_name": model_name,
        "api_key": api_key,
    }


async def _generate_llm_reply(messages: List[Dict[str, str]], payload: Dict[str, Any]) -> Tuple[str, str]:
    if _wants_coder_model(payload):
        coder_cfg = _coder_route_config()
        if coder_cfg:
            try:
                text = await llm_client.generate_messages(
                    messages,
                    base_url_override=coder_cfg["base_url"],
                    model_override=coder_cfg["model_name"],
                    api_key_override=coder_cfg["api_key"],
                )
                return text, "coder"
            except (LLMDisabledError, LLMConfigError, LLMRequestError) as exc:
                logger.warning("Coder model route failed; falling back to primary LLM (%s)", exc)
        elif _env_bool("FRIDAY_DEBUG_TOOL_ERRORS", "0"):
            logger.info("Coder model requested but FRIDAY_CODER_* env is incomplete; using primary LLM.")

    text = await llm_client.generate_messages(messages)
    return text, "primary"


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
        "rejected": 0,
    }


def _log_prompt_debug(messages: List[Dict[str, Any]]) -> None:
    if not _env_bool("FRIDAY_DEBUG_PROMPT", "0"):
        return
    if not messages:
        logger.info("prompt_debug empty_messages=true")
        return
    first = messages[0] if isinstance(messages[0], dict) else {}
    system_prompt = str(first.get("content") or "")
    memory_marker = "\n\n<SYSTEM_MEMORY>"
    marker_index = system_prompt.find(memory_marker)
    memory_appended = marker_index >= 0
    memory_chars = 0
    if memory_appended:
        memory_chars = len(system_prompt[marker_index + 2 :])
    max_chars = _env_int("FRIDAY_DEBUG_PROMPT_MAX_CHARS", 2000)
    tail_chars = min(400, max_chars)
    head = system_prompt[:max_chars]
    tail = system_prompt[-tail_chars:] if system_prompt else ""
    logger.info(
        "prompt_debug length=%s head=%s tail=%s system_memory_appended=%s system_memory_chars=%s",
        len(system_prompt),
        head,
        tail,
        memory_appended,
        memory_chars,
    )


def _count_recent_tool_failures(recent_turns: List[Dict[str, Any]]) -> int:
    markers = (
        "failed because",
        "tool call requires confirmation or is blocked",
        "without fresh tool output",
    )
    count = 0
    for turn in recent_turns[-10:]:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "").lower()
        if role not in {"assistant", "tool"}:
            continue
        content = str(turn.get("content") or "").lower()
        if not content:
            continue
        if any(marker in content for marker in markers):
            count += 1
            continue
        if role == "tool":
            try:
                payload = json.loads(content)
            except Exception:
                payload = {}
            if isinstance(payload, dict) and payload.get("ok") is False:
                count += 1
    return count


def _tool_failure_reason(tool_results: List[Dict[str, Any]]) -> str:
    for result in tool_results:
        if not isinstance(result, dict) or result.get("ok"):
            continue
        error = result.get("error")
        if not isinstance(error, dict):
            continue
        code = str(error.get("code") or "").strip().lower()
        if code == "requires_confirmation":
            return "it needs your confirmation before that action can run"
        if code == "tools_disabled":
            return "tools are disabled in the current configuration"
        if code == "tool_not_found":
            return "the requested tool is not available"
        if code == "tool_failed":
            detail = str(error.get("detail") or "").strip()
            if detail:
                return f"the tool returned an execution error ({detail})"
            return "the tool returned an execution error"
    return "the requested operation was blocked"


def _blame_free_tool_fallback(tool_results: List[Dict[str, Any]]) -> str:
    reason = _tool_failure_reason(tool_results)
    return (
        f"That failed because {reason}. "
        "I will continue with a direct response instead. "
        "If you want, we can skip tools entirely and do this manually."
    )


def _iter_values(value: Any) -> List[Any]:
    values = [value]
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for item in current.values():
                values.append(item)
                stack.append(item)
        elif isinstance(current, list):
            for item in current:
                values.append(item)
                stack.append(item)
    return values


def _has_verification_signal(tool_results: List[Dict[str, Any]]) -> bool:
    for result in tool_results:
        if not isinstance(result, dict):
            continue
        payload = result.get("result")
        if payload is None:
            continue
        for item in _iter_values(payload):
            if isinstance(item, dict):
                lowered = {str(k).lower(): v for k, v in item.items()}
                for key in ("exit_code", "exitcode", "return_code", "returncode"):
                    value = lowered.get(key)
                    if isinstance(value, int) and value == 0:
                        return True
                status = lowered.get("status")
                if isinstance(status, str) and status.lower() in {"passed", "pass", "ok", "success", "succeeded"}:
                    return True
                tests_passed = lowered.get("tests_passed")
                if isinstance(tests_passed, bool) and tests_passed:
                    return True
                if isinstance(tests_passed, int) and tests_passed > 0:
                    return True
            elif isinstance(item, str):
                low = item.lower()
                if "tests passed" in low or "all checks passed" in low:
                    return True
    return False


def _derive_certainty(
    *,
    tool_results: List[Dict[str, Any]],
    prompt: str,
    tool_calls_present: bool,
) -> str:
    any_success = any(isinstance(result, dict) and result.get("ok") for result in tool_results)
    if any_success:
        return "high"
    if _has_verification_signal(tool_results):
        return "high"
    if tool_calls_present and not any_success:
        return "low"

    if re.search(r"\b(maybe|guess|not sure|unsure|unclear|approximately)\b", prompt, re.IGNORECASE):
        return "low"
    return "medium"


def _apply_confidence_calibration(reply: str, *, certainty: str, tool_calls_present: bool) -> str:
    text = str(reply or "").strip()
    if not text:
        return text
    if certainty != "low":
        return text
    lowered = text.lower()
    if "here's what i'm assuming" not in lowered and "here is what i'm assuming" not in lowered:
        text = (
            "Here's what I'm assuming: you want a best-effort answer from the current context.\n\n"
            f"{text}"
        )
    if tool_calls_present and "quick check" not in lowered and "verify" not in lowered:
        text = f"{text}\n\nIf you want, I can run a quick verification check."
    return text


async def _generate_llm_reply_with_retry(
    messages: List[Dict[str, str]],
    payload: Dict[str, Any],
    runtime_events: List[Dict[str, Any]],
) -> Tuple[str, str]:
    try:
        return await _generate_llm_reply(messages, payload)
    except LLMRequestError:
        runtime_events.append({"type": "retry_attempted", "reason": "llm_request_error"})
        try:
            return await _generate_llm_reply(messages, payload)
        except LLMRequestError:
            runtime_events.append({"type": "fallback_used", "reason": "llm_request_error"})
            raise


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
    active_provider = configured_provider if configured_provider in {"muninn", "legacy", "none"} else getattr(memory_provider, "name", "none")

    recent_turns = memory_service.load_recent_turns(user_id, workspace_id, limit=_history_limit())
    memory_bundle = _empty_memory_bundle(recent_turns)
    runtime_events: List[Dict[str, Any]] = []
    interaction_policy = build_interaction_policy(
        prompt=prompt,
        recent_turns=recent_turns,
        tool_failure_loop_count=_count_recent_tool_failures(recent_turns),
    )
    runtime_events.append(
        {
            "type": "policy_selected",
            "mode": interaction_policy.get("mode"),
            "source": interaction_policy.get("mode_source"),
        }
    )

    system_memory_block = ""
    rehydrate_status = "ok"
    rehydrate_latency_ms = 0
    rehydrate_cards = 0
    try:
        rehydrate_started = time.perf_counter()
        rehydrated = memory_provider.rehydrate(
            prompt,
            entity_id,
            namespace=namespace,
            profile=profile,
            k=8,
        )
        rehydrate_latency_ms = int((time.perf_counter() - rehydrate_started) * 1000)
        if isinstance(rehydrated, dict) and isinstance(rehydrated.get("provider"), str):
            active_provider = str(rehydrated.get("provider"))
        cards = rehydrated.get("cards") if isinstance(rehydrated, dict) else []
        if isinstance(cards, list):
            system_memory_block = render_system_memory_block(cards, max_cards=8, max_bullets=3)
            rehydrate_cards = len(cards)
    except Exception as exc:
        rehydrate_status = "error"
        logger.warning("Memory rehydrate failed; continuing without injected memory (%s)", exc)
        system_memory_block = ""

    logger.info(
        "memory_rehydrate provider=%s status=%s latency_ms=%s cards=%s",
        active_provider,
        rehydrate_status,
        rehydrate_latency_ms,
        rehydrate_cards,
    )

    if system_memory_block and _env_bool("FRIDAY_DEBUG_MEMORY", "0"):
        logger.info("Injected <SYSTEM_MEMORY> block: %s", _truncate(system_memory_block))

    messages = build_messages(
        prompt,
        memory_bundle,
        tool_schema=None,
        system_memory_block=system_memory_block,
        interaction_policy=interaction_policy,
    )
    _log_prompt_debug(messages)
    llm_route = "primary"

    try:
        reply, llm_route = await _generate_llm_reply_with_retry(messages, payload, runtime_events)
    except LLMDisabledError:
        reply = LLM_DISABLED_MESSAGE
        llm_route = "disabled"
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
            reply, llm_route = await _generate_llm_reply_with_retry(messages, payload, runtime_events)
        except (LLMDisabledError, LLMConfigError, LLMRequestError):
            runtime_events.append({"type": "fallback_used", "reason": "post_tool_regen_failed"})
            reply = (
                "Tool execution succeeded, but I could not complete the final synthesis pass. "
                "If you want, I can retry immediately."
            )

    if tool_results and not any(result.get("ok") for result in tool_results):
        runtime_events.append({"type": "fallback_used", "reason": "tool_calls_failed"})
        reply = _blame_free_tool_fallback(tool_results)

    certainty_level = _derive_certainty(
        tool_results=tool_results,
        prompt=prompt,
        tool_calls_present=bool(tool_calls),
    )
    reply = _apply_confidence_calibration(
        reply,
        certainty=certainty_level,
        tool_calls_present=bool(tool_calls),
    )
    reply = shape_response(reply, interaction_policy)

    memory_service.append_turn(user_id, workspace_id, "assistant", reply)

    memory_meta: Dict[str, Any] = _base_memory_meta(active_provider)
    candidates = extract_memory_candidates(prompt, entity_id, source_id=user_id)
    if candidates:
        try:
            stage_started = time.perf_counter()
            staged = memory_provider.stage(candidates, namespace=namespace, ttl_seconds=86400)
            stage_latency_ms = int((time.perf_counter() - stage_started) * 1000)
            if isinstance(staged, dict):
                provider_name = staged.get("provider")
                if isinstance(provider_name, str) and provider_name:
                    memory_meta["provider"] = provider_name
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
                if isinstance(rejected_count, int):
                    memory_meta["rejected"] = rejected_count
                elif isinstance(reject_reasons, list):
                    memory_meta["rejected"] = len(reject_reasons)
                logger.info(
                    "memory_stage provider=%s latency_ms=%s candidates=%s accepted=%s pending=%s rejected=%s",
                    memory_meta.get("provider"),
                    stage_latency_ms,
                    len(candidates),
                    len(memory_meta["accepted_ids"]),
                    len(memory_meta["pending_ids"]),
                    memory_meta["rejected"],
                )
        except Exception as exc:
            logger.warning("Memory stage failed; continuing without staged memory (%s)", exc)

    consolidation_job = memory_service.maybe_consolidate(user_id, workspace_id)

    return {
        "assistant_text": reply,
        "text": reply,
        "tools": tool_results,
        "meta": {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "consolidation_job_id": consolidation_job,
            "llm_route": llm_route,
            "interaction_mode": interaction_policy.get("mode"),
            "interaction_mode_source": interaction_policy.get("mode_source"),
            "interaction_override": interaction_policy.get("explicit_override"),
            "certainty_level": certainty_level,
            "runtime_events": runtime_events,
        },
        "memory": memory_meta,
    }
