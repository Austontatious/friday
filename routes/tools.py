"""FastAPI routes for tool introspection and health checks."""
from __future__ import annotations

import logging
from fastapi import APIRouter
from friday.tools.registry import list_tools, get_tool
from friday.tools.tool_executor import run_tool

router = APIRouter(prefix="/tools", tags=["tools"])
logger = logging.getLogger("friday.routes.tools")

@router.get("/", summary="List available tools")
async def list_available_tools():
    return {"tools": list_tools()}

@router.get("/health", summary="Run health checks on all tools")
async def tools_health():
    """Attempt to import each tool and call with empty args to ensure import success."""
    results = {}
    for meta in list_tools():
        name = meta["name"]
        exec_result = run_tool(name, {})
        results[name] = exec_result["success"]
    global_status = all(results.values())
    return {"status": "ok" if global_status else "degraded", "details": results}
