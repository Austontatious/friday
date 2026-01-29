from __future__ import annotations

from typing import Any, Callable, Dict

TOOLS: Dict[str, Callable[..., Any]] = {}


def register(name: str):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        TOOLS[name] = fn
        return fn
    return decorator


def list_tools() -> Dict[str, str]:
    return {name: fn.__doc__ or "" for name, fn in TOOLS.items()}


def run_tool(name: str, args: Dict[str, Any]):
    if name not in TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    return TOOLS[name](**args)
