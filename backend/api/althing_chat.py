from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Dict, Mapping
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core.chat_engine import ChatError, run_chat
from backend.core.prompt_builder import build_althing_bridge_system_prompt
from backend.security.trust import classify_request
from backend.workspaces.routing import resolve_workspace_id
from core.config import AlthingBridgeConfig

router = APIRouter(tags=["althing_bridge"])

BRIDGE_SOURCE_HEADER = "X-Friday-Bridge-Source"
BRIDGE_SOURCE_VALUE = "friday_ui_shell"
HANDOFF_HEADER = "X-Althing-Handoff"
_REPO_PATH_HINT_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:py|md|txt|json|ya?ml|toml|ini|cfg|sh|sql|tsx?|jsx?|css|html))(?![A-Za-z0-9_./-])"
)
_ABSOLUTE_PATH_HINT_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])(/(?:[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)/?)(?![A-Za-z0-9_./-])"
)
_REPO_ROOT_FILE_HINTS = (
    "README.md",
    "RUNBOOK.md",
    "PROJECT_MEMORY.md",
    "AGENTS.md",
    "ARCHITECTURE_CHECKPOINT.md",
)


def _error_payload(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "retryable": retryable,
        }
    }


def _is_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _extract_prompt(payload: Dict[str, Any]) -> str:
    prompt = payload.get("prompt") or payload.get("message") or payload.get("text")
    if isinstance(prompt, str):
        return prompt.strip()
    return ""


def _header_value(headers: Mapping[str, str], name: str) -> str:
    direct = headers.get(name)
    if direct is not None:
        return str(direct)
    return str(headers.get(name.lower()) or "")


def _looks_like_handoff(payload: Dict[str, Any], request_headers: Mapping[str, str]) -> bool:
    if _is_truthy(_header_value(request_headers, HANDOFF_HEADER)):
        return True
    source = str(payload.get("source") or "").strip().lower()
    if source in {"althing_handoff", "handoff", "execution_handoff"}:
        return True
    context = payload.get("context")
    if isinstance(context, dict) and "handoff" in context:
        return True
    return False


def _build_althing_payload(payload: Dict[str, Any], prompt: str, model_hint: str) -> tuple[Dict[str, Any], Dict[str, str]]:
    system_prompt, prompt_context = build_althing_bridge_system_prompt(user_prompt=prompt, payload=payload)
    messages = payload.get("messages")
    if isinstance(messages, list) and messages:
        normalized_messages = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "user").strip() or "user"
            content = str(item.get("content") or "").strip()
            if content:
                normalized_messages.append({"role": role, "content": content})
        if normalized_messages:
            built_messages = normalized_messages
        else:
            built_messages = [{"role": "user", "content": prompt}]
    else:
        built_messages = [{"role": "user", "content": prompt}]

    has_system_message = any(
        isinstance(item, dict) and str(item.get("role") or "").strip().lower() == "system"
        for item in built_messages
    )
    if system_prompt and not has_system_message:
        built_messages = [{"role": "system", "content": system_prompt}, *built_messages]

    body: Dict[str, Any] = {
        "model": model_hint,
        "messages": built_messages,
        "stream": False,
    }
    temperature = payload.get("temperature")
    if isinstance(temperature, (int, float)):
        body["temperature"] = float(temperature)
    max_tokens = payload.get("max_tokens")
    if isinstance(max_tokens, int) and max_tokens > 0:
        body["max_tokens"] = max_tokens
    return body, prompt_context


def _collect_repo_hints(prompt: str, payload: Dict[str, Any]) -> list[str]:
    text = str(prompt or "")
    lowered = text.lower()
    hints: list[str] = []
    seen: set[str] = set()
    specific_basenames: set[str] = set()

    def _add(value: Any) -> None:
        normalized = str(value or "").strip().strip("`'\"()[]{}.,:;")
        if not normalized or "://" in normalized or normalized in seen:
            return
        basename = normalized.rstrip("/").split("/")[-1].lower()
        is_specific = "/" in normalized
        if not is_specific and basename in specific_basenames:
            return
        seen.add(normalized)
        hints.append(normalized)
        if is_specific and basename:
            specific_basenames.add(basename)

    for match in _ABSOLUTE_PATH_HINT_RE.finditer(text):
        _add(match.group(1))

    for match in _REPO_PATH_HINT_RE.finditer(text):
        _add(match.group(1))

    for name in _REPO_ROOT_FILE_HINTS:
        if name.lower() in lowered:
            _add(name)

    def _scan(value: Any) -> None:
        if isinstance(value, str):
            if value.strip():
                _add(value)
            return
        if isinstance(value, dict):
            for key in ("path", "file_path", "filepath", "name", "uri"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    _add(candidate)
            return
        if isinstance(value, list):
            for item in value:
                _scan(item)

    for key in ("attachments", "files", "file_paths", "documents"):
        _scan(payload.get(key))
    context = payload.get("context")
    if isinstance(context, dict):
        for key in ("attachments", "files", "documents"):
            _scan(context.get(key))

    return hints


def _should_use_direct_friday_fallback(prompt: str, payload: Dict[str, Any], prompt_context: Dict[str, str]) -> bool:
    if _collect_repo_hints(prompt, payload):
        return True
    return str(prompt_context.get("route") or "") == "retrieval_or_file"


async def _run_direct_friday(
    request: Request,
    payload: Dict[str, Any],
    *,
    user_id: str,
    workspace_id: str,
) -> Dict[str, Any]:
    request_payload = dict(payload)
    request_payload["user_id"] = user_id
    request_payload["workspace_id"] = workspace_id
    request_payload["mode"] = "direct_friday"
    trust = classify_request(request_payload, request.headers)
    require_confirm_raw = request_payload.get("tool_require_confirm")
    if require_confirm_raw is None:
        require_confirm = None
    else:
        require_confirm = str(require_confirm_raw).lower() in {"1", "true", "yes", "on"}
    return await run_chat(request_payload, trust=trust, require_confirm=require_confirm)


def _normalize_althing_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    content = ""
    choices = parsed.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = str(message.get("content") or "").strip()

    route = parsed.get("route")
    mode = None
    harness_id = None
    if isinstance(route, dict):
        mode = route.get("mode")
        harness_id = route.get("harness_id")

    return {
        "assistant_text": content,
        "text": content,
        "meta": {
            "llm_route": "althing_bridge",
            "bridge_mode": "althing",
            "bridge_source": "friday_ui",
            "althing_mode": mode,
            "althing_harness_id": harness_id,
        },
    }


def _detect_lane_unavailable_reason(payload: Any) -> str:
    try:
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    except Exception:
        serialized = str(payload)
    lowered = serialized.lower()
    if "no_routable_lane_available" in lowered:
        return "no_routable_lane_available"
    if "state_unavailable" in lowered:
        return "state_unavailable"
    return ""


def _annotate_bridge_meta(
    adapted: Dict[str, Any],
    prompt_context: Dict[str, str],
    *,
    fallback: str | None = None,
    fallback_reason: str | None = None,
) -> Dict[str, Any]:
    adapted_meta = adapted.get("meta")
    if isinstance(adapted_meta, dict):
        adapted_meta["bridge_mode"] = "althing"
        adapted_meta["bridge_source"] = "friday_ui"
        adapted_meta["bridge_prompt_mode"] = prompt_context.get("mode")
        adapted_meta["bridge_prompt_lane"] = prompt_context.get("lane_class")
        adapted_meta["bridge_task_overlay"] = prompt_context.get("task_overlay")
        if fallback:
            adapted_meta["bridge_fallback"] = fallback
        if fallback_reason:
            adapted_meta["bridge_fallback_reason"] = fallback_reason
    return adapted


async def _post_json(
    *,
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout_s: float,
) -> tuple[int, Dict[str, Any], int]:
    def _run() -> tuple[int, Dict[str, Any], int]:
        started = time.perf_counter()
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        request = urllib.request.Request(url=url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw_body = response.read().decode("utf-8")
            status_code = int(response.getcode() or 200)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        parsed = json.loads(raw_body)
        if not isinstance(parsed, dict):
            raise ValueError("Althing response was not a JSON object")
        return status_code, parsed, elapsed_ms

    return await asyncio.to_thread(_run)


@router.post("/althing/chat", summary="Bridge Friday UI chat to Althing orchestration")
async def althing_chat(request: Request, payload: Dict[str, Any]):
    prompt = _extract_prompt(payload)
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("bad_request", "Missing prompt", "Provide 'prompt' as a string", False),
        )

    if _looks_like_handoff(payload, request.headers):
        return JSONResponse(
            status_code=409,
            content=_error_payload(
                "recursion_guard",
                "Rejected potential recursion into Althing bridge route",
                "Execution handoff requests must use dedicated Friday handoff endpoint",
                False,
            ),
        )

    user_id = getattr(request.state, "user_id", "") or ""
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("missing_user_id", "Missing user_id", "Identity middleware required", False),
        )
    workspace_id = resolve_workspace_id(payload, request.headers)

    config = AlthingBridgeConfig.from_env()
    if not config.enabled:
        return JSONResponse(
            status_code=503,
            content=_error_payload(
                "althing_bridge_disabled",
                "Althing bridge mode is disabled",
                "Set FRIDAY_ALTHING_BRIDGE_ENABLED=1 to enable UI->Althing routing",
                False,
            ),
        )

    route_payload, prompt_context = _build_althing_payload(payload, prompt, config.model_hint)
    if _should_use_direct_friday_fallback(prompt, payload, prompt_context):
        try:
            adapted = await _run_direct_friday(
                request,
                payload,
                user_id=user_id,
                workspace_id=str(workspace_id),
            )
        except ChatError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=_error_payload(exc.code, exc.message, exc.detail, exc.retryable),
            )
        _annotate_bridge_meta(
            adapted,
            prompt_context,
            fallback="direct_friday_read_only",
            fallback_reason="repo_context",
        )
        reply = JSONResponse(content=adapted)
        reply.headers["X-Friday-User"] = user_id
        reply.headers["X-Friday-Workspace"] = str(workspace_id)
        reply.headers["X-Friday-Mode"] = "althing"
        reply.headers["X-Friday-Bridge-Fallback"] = "direct_friday_read_only"
        return reply

    url = f"{config.althing_base_url.rstrip('/')}{config.althing_route_path}"
    headers = {
        "Content-Type": "application/json",
        BRIDGE_SOURCE_HEADER: BRIDGE_SOURCE_VALUE,
        "X-Friday-Session": user_id,
        "X-Friday-Workspace": str(workspace_id),
    }
    device_id = (request.headers.get("X-Friday-Device") or "").strip()
    if device_id:
        headers["X-Friday-Device"] = device_id

    try:
        _, parsed, _ = await _post_json(
            url=url,
            payload=route_payload,
            headers=headers,
            timeout_s=config.timeout_ms / 1000.0,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        fallback_reason = _detect_lane_unavailable_reason({"code": exc.code, "detail": detail})
        if fallback_reason:
            try:
                adapted = await _run_direct_friday(
                    request,
                    payload,
                    user_id=user_id,
                    workspace_id=str(workspace_id),
                )
            except ChatError as chat_exc:
                return JSONResponse(
                    status_code=chat_exc.status_code,
                    content=_error_payload(chat_exc.code, chat_exc.message, chat_exc.detail, chat_exc.retryable),
                )
            _annotate_bridge_meta(
                adapted,
                prompt_context,
                fallback="direct_friday_runtime_fallback",
                fallback_reason=fallback_reason,
            )
            reply = JSONResponse(content=adapted)
            reply.headers["X-Friday-User"] = user_id
            reply.headers["X-Friday-Workspace"] = str(workspace_id)
            reply.headers["X-Friday-Mode"] = "althing"
            reply.headers["X-Friday-Bridge-Fallback"] = "direct_friday_runtime_fallback"
            return reply
        return JSONResponse(
            status_code=502,
            content=_error_payload(
                "althing_upstream_http_error",
                f"Althing upstream HTTP error: {exc.code}",
                detail,
                True,
            ),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content=_error_payload(
                "althing_upstream_unavailable",
                f"Althing upstream request failed: {type(exc).__name__}",
                str(exc),
                True,
            ),
        )

    fallback_reason = _detect_lane_unavailable_reason(parsed)
    if fallback_reason:
        try:
            adapted = await _run_direct_friday(
                request,
                payload,
                user_id=user_id,
                workspace_id=str(workspace_id),
            )
        except ChatError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=_error_payload(exc.code, exc.message, exc.detail, exc.retryable),
            )
        _annotate_bridge_meta(
            adapted,
            prompt_context,
            fallback="direct_friday_runtime_fallback",
            fallback_reason=fallback_reason,
        )
        reply = JSONResponse(content=adapted)
        reply.headers["X-Friday-User"] = user_id
        reply.headers["X-Friday-Workspace"] = str(workspace_id)
        reply.headers["X-Friday-Mode"] = "althing"
        reply.headers["X-Friday-Bridge-Fallback"] = "direct_friday_runtime_fallback"
        return reply

    try:
        adapted = _normalize_althing_response(parsed)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content=_error_payload(
                "althing_bad_response",
                "Althing response could not be normalized",
                str(exc),
                True,
            ),
        )
    _annotate_bridge_meta(adapted, prompt_context)

    reply = JSONResponse(content=adapted)
    reply.headers["X-Friday-User"] = user_id
    reply.headers["X-Friday-Workspace"] = str(workspace_id)
    reply.headers["X-Friday-Mode"] = "althing"
    return reply
