# ========= friday/memory_core.py =========
"""High‑level memory manager used by backend routes."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .memory_store_json import MemoryStoreJSON
from .memory_types import MemoryShard

logger = logging.getLogger(__name__)

ISO8601 = "%Y-%m-%dT%H:%M:%S.%fZ"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime(ISO8601)


class MemoryManager:
    """Public facade between Friday backend and persistent store."""

    def __init__(self, store: MemoryStoreJSON, *, session_id: str = "default") -> None:
        self.store = store
        self.session_id = session_id

    # ------------------------------------------------------------------
    # Interaction helpers (user ↔ assistant turns)
    # ------------------------------------------------------------------
    def store_context(
        self,
        *,
        prompt: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryShard:
        """Persist one prompt/response pair."""
        shard = MemoryShard(
            id=str(uuid.uuid4()),
            shard_type="interaction",
            session_id=self.session_id,
            prompt=prompt,
            response=response,
            metadata=metadata or {},
            timestamp=_utc_now(),
            last_used=time.time(),
        )
        self.store.insert(shard)
        logger.debug("[Memory] Stored interaction shard %s", shard.id)
        return shard

    def get_context_history(self, *, limit: int = 5) -> List[Dict[str, Any]]:
        shards = self.store.history(session_id=self.session_id, limit=limit, by_timestamp=True)
        logger.debug("[Memory] Loaded %d context shards", len(shards))
        return [s.to_dict() for s in shards]

    # ------------------------------------------------------------------
    # Thread helpers (multi‑message consolidation)
    # ------------------------------------------------------------------
    def store_thread(
        self,
        *,
        thread_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryShard:
        shard = MemoryShard(
            id=str(uuid.uuid4()),
            type="thread",
            session_id=self.session_id,
            thread_id=thread_id,
            text=text,
            metadata=metadata or {},
            timestamp=_utc_now(),
            last_used=time.time(),
        )
        self.store.insert(shard)
        logger.debug("[Memory] Stored thread shard %s", shard.id)
        return shard

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def mark_used(self, shard_id: str) -> None:
        self.store.mark_used(shard_id)

memory_manager = MemoryManager(MemoryStoreJSON("friday/memory/default.jsonl"))
