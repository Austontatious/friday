from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel
from .memory import MemoryManager

logger = logging.getLogger("context")

context_router = APIRouter(prefix="/context", tags=["context"])

# Global memory manager reference; initialized via initialize_context_router
memory_manager: Optional[MemoryManager] = None

def get_memory_manager() -> MemoryManager:
    if memory_manager is None:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")
    return memory_manager

# ─── MODELS ───────────────────────────────────────────────────────────────

class ContextItem(BaseModel):
    session_id: Optional[str] = None
    text: str
    metadata: Optional[Dict[str, Any]] = None

class ContextResponse(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any]
    timestamp: str
    score: Optional[float] = None

# ─── ROUTES ───────────────────────────────────────────────────────────────

@context_router.post("/store", response_model=Dict[str, str])
async def store_context(
    item: ContextItem,
    memory: MemoryManager = Depends(get_memory_manager)
):
    """
    Store a piece of context (text + metadata) in memory.
    """
    session_id = item.session_id or "default"
    try:
        context_id = memory.store_context(item.text, item.metadata, session_id=session_id)
        return {"id": context_id, "status": "success"}
    except Exception as e:
        logger.error(f"[store_context] {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store context: {str(e)}")

@context_router.get("/retrieve", response_model=List[ContextResponse])
async def retrieve_context(
    query: str,
    session_id: str = Query("default", description="Session identifier"),
    k: int = Query(5, description="Number of context entries to retrieve"),
    memory: MemoryManager = Depends(get_memory_manager)
):
    """
    Retrieve top-k relevant context items.
    """
    try:
        results = memory.retrieve_context(query, k, session_id=session_id)
        return results
    except Exception as e:
        logger.error(f"[retrieve_context] {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve context: {str(e)}")

@context_router.delete("/clear", response_model=Dict[str, str])
async def clear_context(
    session_id: str = Query("default", description="Session identifier"),
    memory: MemoryManager = Depends(get_memory_manager)
):
    """
    Clear all context for a given session.
    """
    try:
        memory.clear(session_id=session_id)
        return {"status": "cleared"}
    except Exception as e:
        logger.error(f"[clear_context] {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear context: {str(e)}")

@context_router.get("/history", response_model=List[ContextResponse])
async def get_context_history(
    session_id: str = Query("default", description="Session identifier"),
    limit: int = Query(10, description="Max history items"),
    memory: MemoryManager = Depends(get_memory_manager)
):
    """
    Return recent context history.
    """
    try:
        history = memory.get_context_history(limit, session_id=session_id)
        return history
    except Exception as e:
        logger.error(f"[get_context_history] {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve context history: {str(e)}")

# ─── INIT ─────────────────────────────────────────────────────────────────

def initialize_context_router(memory: MemoryManager):
    global memory_manager
    memory_manager = memory
    logger.info("✅ Context router initialized with memory manager")

