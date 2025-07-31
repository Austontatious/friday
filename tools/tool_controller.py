# friday/tools/tool_controller.py

import json
import re
import logging
from friday.tools.registry import get_tool, list_tools
from friday.tools.tool_executor import run_tool as simple_run_tool

logger = logging.getLogger("friday.tool_controller")

def extract_tool_call(output: str):
    """
    Extracts a tool call from model output.
    Supports JSON { "tool_call": {...} }, [TOOLCALL: name(args)], <tool>name args.
    """
    try:
        data = json.loads(output)
        if "tool_call" in data:
            return data["tool_call"]
    except Exception:
        pass

    m = re.search(r"\[TOOLCALL:\s*(\w+)\((.*?)\)\]", output)
    if m:
        tool_name = m.group(1)
        arg_str = m.group(2)
        args = dict(re.findall(r'(\w+)\s*=\s*"([^"]+)"', arg_str)) or {}
        return {"name": tool_name, "args": args}

    m2 = re.search(r"<tool>(\w+)\s*(.*)", output)
    if m2:
        tool_name = m2.group(1)
        args = dict(re.findall(r'(\w+)="([^"]*)"', m2.group(2)))
        return {"name": tool_name, "args": args}

    return None

def handle_tool_call(tool_call: dict) -> str:
    """
    Executes a tool call and returns result.
    """
    tool_name = tool_call.get("name")
    args = tool_call.get("args", {})

    if tool_name in list_tools():
        try:
            result = simple_run_tool(tool_name, **args)
            return result
        except Exception as e:
            logger.error(f"[ToolController] Tool {tool_name} failed: {e}")
            return f"❌ Tool {tool_name} error: {str(e)}"
    else:
        logger.warning(f"[ToolController] Unknown tool: {tool_name}")
        return f"❌ Unknown tool: {tool_name}"

def process_output(model_output: str) -> str:
    """
    Processes model output: extract tool calls, run them, inject results.
    """
    tool_call = extract_tool_call(model_output)
    if tool_call:
        result = handle_tool_call(tool_call)
        # Inject result back into context or return immediately
        return f"🤖 Tool [{tool_call['name']}] result:\n{result}"
    else:
        return model_output  # No tool call, return as-is

