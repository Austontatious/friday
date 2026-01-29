from __future__ import annotations

import inspect
import os
from typing import Any, Dict, List, Optional, Tuple

from backend.audit.logger import log_event
from backend.security.trust import TrustContext, is_safe_tool, require_confirmation

from backend.tools.registry import get_tool, tool_schema


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def _error(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {"code": code, "message": message, "detail": detail, "retryable": retryable}


def _validate_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def validate_args(schema: Dict[str, Any], args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    if schema.get("type") != "object":
        return True, {}
    if not isinstance(args, dict):
        return False, _error("invalid_args", "Args must be an object")

    required = schema.get("required", [])
    for key in required:
        if key not in args:
            return False, _error("missing_arg", f"Missing required arg: {key}")

    properties = schema.get("properties", {})
    for key, value in args.items():
        prop = properties.get(key)
        if not prop:
            continue
        expected = prop.get("type")
        if expected and not _validate_type(value, expected):
            return False, _error("invalid_arg_type", f"Arg {key} must be {expected}")
        if expected == "array" and "items" in prop and isinstance(value, list):
            item_type = prop["items"].get("type")
            if item_type and not all(_validate_type(item, item_type) for item in value):
                return False, _error("invalid_arg_type", f"Arg {key} items must be {item_type}")
    return True, {}


def validate_tool_call(call: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    if not isinstance(call, dict):
        return False, _error("invalid_tool_call", "Tool call must be an object")
    if "id" not in call or not isinstance(call.get("id"), str):
        return False, _error("invalid_tool_call", "Tool call requires string id")
    if "name" not in call or not isinstance(call.get("name"), str):
        return False, _error("invalid_tool_call", "Tool call requires string name")
    if "args" not in call or not isinstance(call.get("args"), dict):
        return False, _error("invalid_tool_call", "Tool call requires args object")
    return True, {}


def _tool_enabled(spec: Dict[str, Any]) -> bool:
    enabled_env = spec.get("enabled_env")
    if not enabled_env:
        return True
    return _env_bool(enabled_env, "0")


def tool_schema_list() -> List[Dict[str, Any]]:
    schema = tool_schema()
    return [{"name": name, **details} for name, details in schema.items()]


def execute_tool_call(
    call: Dict[str, Any],
    context_user_id: Optional[str],
    workspace_id: Optional[str],
    require_confirm: Optional[bool],
    approved: bool = False,
    trust: Optional[TrustContext] = None,
) -> Dict[str, Any]:
    ok, error = validate_tool_call(call)
    if not ok:
        log_event("tool_call_invalid", {"call": call, "error": error}, context_user_id, workspace_id)
        return {"id": call.get("id") if isinstance(call, dict) else None, "name": None, "ok": False, "error": error}

    if not _env_bool("FRIDAY_TOOLS_ENABLED", "0"):
        error = _error("tools_disabled", "Tools are disabled")
        log_event("tool_call_blocked", {"call": call, "error": error}, context_user_id, workspace_id)
        return {"id": call["id"], "name": call["name"], "ok": False, "error": error}

    spec = get_tool(call["name"])
    if not spec:
        error = _error("tool_not_found", "Unknown tool")
        log_event("tool_call_blocked", {"call": call, "error": error}, context_user_id, workspace_id)
        return {"id": call["id"], "name": call["name"], "ok": False, "error": error}

    if not _tool_enabled(spec):
        error = _error("tool_disabled", "Tool is disabled")
        log_event("tool_call_blocked", {"call": call, "error": error}, context_user_id, workspace_id)
        return {"id": call["id"], "name": call["name"], "ok": False, "error": error}

    needs_confirm = require_confirm if require_confirm is not None else _env_bool("FRIDAY_TOOLS_REQUIRE_CONFIRM", "1")
    if trust and require_confirmation(trust) and not is_safe_tool(call["name"]):
        needs_confirm = True
    if spec.get("requires_confirmation"):
        needs_confirm = True

    if needs_confirm and not approved:
        error = _error("requires_confirmation", "Tool call requires confirmation")
        log_event("tool_call_blocked", {"call": call, "error": error}, context_user_id, workspace_id)
        return {
            "id": call["id"],
            "name": call["name"],
            "ok": False,
            "error": error,
        }

    args_schema = spec.get("args_schema", {})
    ok, error = validate_args(args_schema, call["args"])
    if not ok:
        log_event("tool_call_invalid", {"call": call, "error": error}, context_user_id, workspace_id)
        return {"id": call["id"], "name": call["name"], "ok": False, "error": error}

    try:
        args = dict(call["args"])
        params = inspect.signature(spec["fn"]).parameters
        if "user_id" in params and "user_id" not in args:
            if not context_user_id:
                error = _error("missing_context", "user_id is required")
                log_event("tool_call_blocked", {"call": call, "error": error}, context_user_id, workspace_id)
                return {"id": call["id"], "name": call["name"], "ok": False, "error": error}
            args["user_id"] = context_user_id
        if "workspace_id" in params and "workspace_id" not in args:
            if not workspace_id:
                error = _error("missing_context", "workspace_id is required")
                log_event("tool_call_blocked", {"call": call, "error": error}, context_user_id, workspace_id)
                return {"id": call["id"], "name": call["name"], "ok": False, "error": error}
            args["workspace_id"] = workspace_id

        result = spec["fn"](**args)
        log_event("tool_call_ok", {"call": call, "result": result}, context_user_id, workspace_id)
        return {"id": call["id"], "name": call["name"], "ok": True, "result": result}
    except Exception as exc:
        error = _error("tool_failed", "Tool execution failed", str(exc))
        log_event("tool_call_failed", {"call": call, "error": error}, context_user_id, workspace_id)
        return {
            "id": call["id"],
            "name": call["name"],
            "ok": False,
            "error": error,
        }
