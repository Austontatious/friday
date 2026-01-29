"""Friday Tool Registry with fuzzy lookup, schema validation, and structured logging."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from difflib import get_close_matches

logger = logging.getLogger("friday.tools.registry")

@dataclass
class Tool:
    name: str
    description: str
    usage_hint: str
    entrypoint: Callable[..., Any]
    parameters: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Capture the parameter names from the entrypoint signature for validation
        sig = inspect.signature(self.entrypoint)
        self.parameters = [p.name for p in sig.parameters.values()
                           if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]

# Internal registry
_TOOL_REGISTRY: Dict[str, Tool] = {}

def _normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_")

# Public API
def register_tool(name: str,
                  description: str,
                  usage_hint: str,
                  entrypoint: Callable[..., Any]) -> None:
    """Register a tool at import‑time. Raises ValueError if duplicate."""
    key = _normalize(name)
    if key in _TOOL_REGISTRY:
        raise ValueError(f"Tool '{name}' already registered.")
    _TOOL_REGISTRY[key] = Tool(name=key,
                               description=description.strip(),
                               usage_hint=usage_hint.strip(),
                               entrypoint=entrypoint)
    logger.debug("Registered tool '%s' (%s)", key, entrypoint)

def get_tool(name: str) -> Tool:
    """Resolve a tool with canonical or fuzzy match. Raises KeyError if not found."""
    key = _normalize(name)
    if key in _TOOL_REGISTRY:
        return _TOOL_REGISTRY[key]

    # Fuzzy match
    candidates = get_close_matches(key, _TOOL_REGISTRY.keys(), n=1, cutoff=0.7)
    if candidates:
        logger.warning("Tool '%s' not found, using closest match '%s'", key, candidates[0])
        return _TOOL_REGISTRY[candidates[0]]
    raise KeyError(f"Tool '{name}' not registered.")


def list_tools() -> List[Dict[str, Any]]:
    """Return a list of metadata for all tools."""
    return [{"name": t.name,
             "description": t.description,
             "usage_hint": t.usage_hint,
             "parameters": t.parameters}
            for t in _TOOL_REGISTRY.values()]

def validate_tool_args(tool: Tool, args: Dict[str, Any]) -> None:
    """Validate supplied args against tool parameters, raising ValueError on mismatch."""
    missing = [p for p in tool.parameters
               if p not in args and _param_required(tool.entrypoint, p)]
    if missing:
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")
    extra = [k for k in args.keys() if k not in tool.parameters]
    if extra:
        raise ValueError(f"Unexpected parameters for tool '{tool.name}': {', '.join(extra)}")

def _param_required(func: Callable[..., Any], param_name: str) -> bool:
    return inspect.signature(func).parameters[param_name].default is inspect._empty
