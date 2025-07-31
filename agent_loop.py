"""Core loop that feeds prompts to the Persona model, intercepts tool calls, and stitches results.

This version ensures:
* Current tool list is passed as context on every call.
* Tool calls are extracted via multiple patterns with fuzzy fallback.
* Tool execution results (or errors) are returned to the model as inline messages.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from friday.persona_loader import persona
from friday.persona import PersonaManager
from friday.tools.registry import list_tools
from friday.tools.tool_executor import run_tool

logger = logging.getLogger("friday.agent_loop")

_TOOLCALL_RE = re.compile(
    r"\[TOOLCALL:\s*(?P<name>\w+)\((?P<args>.*?)\)\]"
)

def _extract_json_tool_call(raw: str) -> Optional[Dict[str, Any]]:
    """Try to parse a JSON‑style tool call."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "tool_call" in data:
            return data["tool_call"]
    except json.JSONDecodeError:
        pass
    return None

def extract_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Extract a tool call from model output in any supported format."""
    # JSON format first
    call = _extract_json_tool_call(text)
    if call:
        return call

    # [TOOLCALL: name(args...)]
    m = _TOOLCALL_RE.search(text)
    if m:
        name = m.group("name")
        arg_str = m.group("args").strip()
        # Parse key=value pairs or single positional
        args = {}
        if "," in arg_str or "=" in arg_str:
            for pair in re.split(r",\s*", arg_str):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    args[k.strip()] = v.strip().strip('"')
        elif arg_str:
            args = {"query": arg_str.strip('"')}
        return {"name": name, "args": args}
    return None

def agent_loop(*,
               persona: PersonaManager,
               prompt: str,
               task_type: str = "general",
               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Main reasoning loop with single tool call support (v1)."""
    context = context or {}
    # Inject live tool catalogue for the model's system prompt or memory
    context["toolbox"] = list_tools()

    logger.debug("[AgentLoop] Prompt: %s", prompt)

    # === 1st pass ===
    response = persona.generate_response(prompt, task_type, context)
    raw_output = response.get("raw", "")

    # === Tool call? ===
    call = extract_tool_call(raw_output)
    if call:
        logger.info("[AgentLoop] Detected tool call: %s", call)
        exec_result = run_tool(call["name"], call.get("args", {}))

        # Summarize tool result for persona follow‑up
        tool_summary = json.dumps(exec_result, indent=2, default=str)

        # Second pass: give tool result back to model
        followup_context = context | {"tool_result": tool_summary}
        followup = persona.generate_response(
            prompt="Here is the tool result. Respond accordingly.",
            task_type=task_type,
            context=followup_context
        )
        return {
            "raw": followup.get("raw", ""),
            "cleaned": followup.get("cleaned", followup.get("raw", "")),
            "affect": followup.get("affect", "neutral"),
            "tool_result": exec_result
        }

    # No tool usage
    return response
