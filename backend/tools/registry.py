from __future__ import annotations

from typing import Any, Callable, Dict, Optional

ToolFn = Callable[..., Any]
ToolSpec = Dict[str, Any]

TOOLS: Dict[str, ToolSpec] = {}


def register(
    name: str,
    description: Optional[str] = None,
    args_schema: Optional[Dict[str, Any]] = None,
    enabled_env: Optional[str] = None,
    requires_confirmation: bool = False,
):
    def decorator(fn: ToolFn) -> ToolFn:
        TOOLS[name] = {
            "name": name,
            "fn": fn,
            "description": description or (fn.__doc__ or ""),
            "args_schema": args_schema or {},
            "enabled_env": enabled_env,
            "requires_confirmation": requires_confirmation,
        }
        return fn
    return decorator


def get_tool(name: str) -> Optional[ToolSpec]:
    return TOOLS.get(name)


def list_tools() -> Dict[str, str]:
    return {name: spec.get("description", "") for name, spec in TOOLS.items()}


def tool_schema() -> Dict[str, Dict[str, Any]]:
    return {name: {"description": spec.get("description", ""), "args_schema": spec.get("args_schema", {})} for name, spec in TOOLS.items()}


def run_tool(name: str, args: Dict[str, Any]):
    spec = get_tool(name)
    if not spec:
        raise ValueError(f"Unknown tool: {name}")
    return spec["fn"](**args)
