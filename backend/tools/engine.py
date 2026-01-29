from __future__ import annotations

import inspect
import os
from typing import Any, Dict, List, Tuple, Optional

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


def execute_tool_call(call: Dict[str, Any], approved: bool = False, context_user_id: Optional[str] = None) -> Dict[str, Any]:
    ok, error = validate_tool_call(call)
    if not ok:
        return {"id": call.get("id") if isinstance(call, dict) else None, "name": None, "ok": False, "error": error}

    if not _env_bool("FRIDAY_TOOLS_ENABLED", "0"):
        return {"id": call["id"], "name": call["name"], "ok": False, "error": _error("tools_disabled", "Tools are disabled")}

    spec = get_tool(call["name"])
    if not spec:
        return {"id": call["id"], "name": call["name"], "ok": False, "error": _error("tool_not_found", "Unknown tool")}

    if not _tool_enabled(spec):
        return {"id": call["id"], "name": call["name"], "ok": False, "error": _error("tool_disabled", "Tool is disabled")}

    if spec.get("requires_confirmation") or _env_bool("FRIDAY_TOOLS_REQUIRE_CONFIRM", "1"):
        if not approved:
            return {
                "id": call["id"],
                "name": call["name"],
                "ok": False,
                "error": _error("requires_confirmation", "Tool call requires confirmation"),
            }

    args_schema = spec.get("args_schema", {})
    ok, error = validate_args(args_schema, call["args"])
    if not ok:
        return {"id": call["id"], "name": call["name"], "ok": False, "error": error}

    try:
        args = dict(call["args"])
        if context_user_id:
            params = inspect.signature(spec["fn"]).parameters
            if "user_id" in params and "user_id" not in args:
                args["user_id"] = context_user_id
        result = spec["fn"](**args)
        return {"id": call["id"], "name": call["name"], "ok": True, "result": result}
    except Exception as exc:
        return {
            "id": call["id"],
            "name": call["name"],
            "ok": False,
            "error": _error("tool_failed", "Tool execution failed", str(exc)),
        }
