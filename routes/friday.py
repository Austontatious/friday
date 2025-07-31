"""Primary Friday chat processing route."""
from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from friday.memory.memory_core import MemoryManager
from friday.agent_loop import agent_loop
from friday.persona_loader import persona

logger = logging.getLogger("friday.routes.friday")
router = APIRouter(tags=["chat"])

# --- Managers ---
from friday.memory.memory_store_json import MemoryStoreJSON
memory_manager = MemoryManager(MemoryStoreJSON("/workspace/ai-lab/memory_logs/default.jsonl"))


class TaskRequest(BaseModel):
    prompt: str
    task_type: Optional[str] = "general"

@router.post("/process", summary="Process a chat prompt with Friday")
async def process_task(request: TaskRequest):
    start = time.perf_counter()
    # Pull last few messages for context (simplified)
    context: Dict[str, Any] = {"history": memory_manager.get_context_history(limit=5)}

    result = agent_loop(
        persona=persona,
        prompt=request.prompt,
        task_type=request.task_type,
        context=context
    )

    duration = time.perf_counter() - start
    logger.info("/process completed in %.2fs", duration)

    # Persist conversation snip to memory
    memory_manager.store_context(prompt=request.prompt, response=result.get("cleaned", ""))

    return JSONResponse(content={"result": result, "latency": duration})
