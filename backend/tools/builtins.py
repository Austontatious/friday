from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.memory.service import memory_service
from backend.tools.registry import register


def _require_context(user_id: str, workspace_id: str) -> None:
    if not user_id or not workspace_id:
        raise ValueError("user_id and workspace_id are required")


@register(
    name="remember_fact",
    description="Store or update a user fact or preference.",
    args_schema={
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "value": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
            "pinned": {"type": "boolean"},
        },
        "required": ["key", "value"],
    },
    enabled_env="FRIDAY_MEMORY_FACTS_ENABLED",
)
def remember_fact(
    key: str,
    value: str,
    user_id: str,
    workspace_id: str,
    tags: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    pinned: bool = False,
) -> Dict[str, Any]:
    """Remember a fact about the user."""
    _require_context(user_id, workspace_id)
    return memory_service.remember_fact(
        user_id=user_id,
        workspace_id=workspace_id,
        key=key,
        value=value,
        tags=tags,
        confidence=confidence,
        source="tool",
        pinned=pinned,
    )


@register(
    name="forget_fact",
    description="Remove a fact by key.",
    args_schema={
        "type": "object",
        "properties": {"key": {"type": "string"}},
        "required": ["key"],
    },
    enabled_env="FRIDAY_MEMORY_FACTS_ENABLED",
)
def forget_fact(key: str, user_id: str, workspace_id: str) -> Dict[str, Any]:
    """Forget a fact by key."""
    _require_context(user_id, workspace_id)
    removed = memory_service.forget_fact(user_id=user_id, workspace_id=workspace_id, key=key)
    return {"removed": removed}


@register(
    name="list_facts",
    description="List stored facts, optionally filtered by tag.",
    args_schema={
        "type": "object",
        "properties": {
            "tag": {"type": "string"},
            "limit": {"type": "integer"},
        },
    },
    enabled_env="FRIDAY_MEMORY_FACTS_ENABLED",
)
def list_facts(user_id: str, workspace_id: str, tag: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List facts for the user."""
    _require_context(user_id, workspace_id)
    return memory_service.list_facts(user_id=user_id, workspace_id=workspace_id, tag=tag, limit=limit)


@register(
    name="create_task",
    description="Create a lightweight task item.",
    args_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["title"],
    },
    enabled_env="FRIDAY_MEMORY_SUMMARIES_ENABLED",
)
def create_task(title: str, user_id: str, workspace_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """Create a task in memory."""
    _require_context(user_id, workspace_id)
    return memory_service.add_task(user_id=user_id, workspace_id=workspace_id, title=title, notes=notes)


@register(
    name="open_loop_add",
    description="Add an open loop item.",
    args_schema={
        "type": "object",
        "properties": {"item": {"type": "string"}},
        "required": ["item"],
    },
    enabled_env="FRIDAY_MEMORY_SUMMARIES_ENABLED",
)
def open_loop_add(item: str, user_id: str, workspace_id: str) -> Dict[str, Any]:
    """Add an open loop item."""
    _require_context(user_id, workspace_id)
    return memory_service.add_open_loop(user_id=user_id, workspace_id=workspace_id, item=item)


@register(
    name="open_loop_resolve",
    description="Resolve an open loop by id.",
    args_schema={
        "type": "object",
        "properties": {"loop_id": {"type": "string"}},
        "required": ["loop_id"],
    },
    enabled_env="FRIDAY_MEMORY_SUMMARIES_ENABLED",
)
def open_loop_resolve(loop_id: str, user_id: str, workspace_id: str) -> Dict[str, Any]:
    """Resolve an open loop by id."""
    _require_context(user_id, workspace_id)
    resolved = memory_service.resolve_open_loop(user_id=user_id, workspace_id=workspace_id, loop_id=loop_id)
    return {"resolved": resolved}


@register(
    name="search_local_logs",
    description="Search local conversation logs for a query.",
    args_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    },
    enabled_env="FRIDAY_MEMORY_PERSIST_ENABLED",
)
def search_local_logs(query: str, user_id: str, workspace_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Search persisted conversation logs."""
    _require_context(user_id, workspace_id)
    return memory_service.search_logs(user_id=user_id, workspace_id=workspace_id, query=query, limit=limit or 5)
