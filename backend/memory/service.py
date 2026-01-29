from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.jobs.store import JobStoreError, get_store
from backend.memory.consolidation import consolidate
from backend.memory.facts_store import FactsStore
from backend.memory.memory import MemoryStore
from backend.memory.retrieval import retrieve_bundle
from backend.memory.summaries_store import SummariesStore


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class MemoryService:
    def __init__(self) -> None:
        self._conversation = MemoryStore()
        self._data_dir = os.getenv("FRIDAY_DATA_DIR", "/data")
        self._facts_enabled = _env_bool("FRIDAY_MEMORY_FACTS_ENABLED", "0")
        self._summaries_enabled = _env_bool("FRIDAY_MEMORY_SUMMARIES_ENABLED", "0")
        self._facts_store = FactsStore(self._data_dir)
        self._summaries_store = SummariesStore(self._data_dir)
        self._facts_limit = _env_int("FRIDAY_MEMORY_FACTS_RETRIEVAL_LIMIT", 10)
        self._summaries_limit = _env_int("FRIDAY_MEMORY_SUMMARIES_RETRIEVAL_LIMIT", 5)
        self._consolidation_enabled = _env_bool("FRIDAY_MEMORY_CONSOLIDATION_ENABLED", "0")
        self._summary_every_n = _env_int("FRIDAY_MEMORY_SUMMARY_EVERY_N_TURNS", 20)

    def append_turn(self, user_id: str, role: str, content: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._conversation.append(user_id, role, content, meta=meta)
        if self._summaries_enabled:
            self._summaries_store.increment_turns(user_id, count=1)

    def load_recent_turns(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        return self._conversation.load_thread(user_id, limit=limit)

    def retrieve(self, user_id: str, prompt: str, limit_turns: int) -> Dict[str, Any]:
        return retrieve_bundle(
            user_id=user_id,
            prompt=prompt,
            memory=self._conversation,
            facts=self._facts_store,
            summaries=self._summaries_store,
            limit_turns=limit_turns,
            facts_limit=self._facts_limit,
            summaries_limit=self._summaries_limit,
        )

    def remember_fact(
        self,
        user_id: str,
        key: str,
        value: str,
        tags: Optional[List[str]] = None,
        confidence: Optional[float] = None,
        source: str = "user",
        pinned: bool = False,
    ) -> Dict[str, Any]:
        if not self._facts_enabled:
            raise ValueError("Facts store disabled")
        return self._facts_store.upsert_fact(
            user_id=user_id,
            key=key,
            value=value,
            tags=tags,
            confidence=confidence,
            source=source,
            pinned=pinned,
        )

    def forget_fact(self, user_id: str, key: str) -> int:
        if not self._facts_enabled:
            raise ValueError("Facts store disabled")
        return self._facts_store.delete_fact(user_id, key)

    def list_facts(self, user_id: str, tag: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self._facts_enabled:
            return []
        return self._facts_store.list_facts(user_id, tag=tag, limit=limit)

    def add_open_loop(self, user_id: str, item: str) -> Dict[str, Any]:
        if not self._summaries_enabled:
            raise ValueError("Summaries disabled")
        return self._summaries_store.add_open_loop(user_id, item)

    def resolve_open_loop(self, user_id: str, loop_id: str) -> bool:
        if not self._summaries_enabled:
            raise ValueError("Summaries disabled")
        return self._summaries_store.resolve_open_loop(user_id, loop_id)

    def add_task(self, user_id: str, title: str, notes: Optional[str] = None) -> Dict[str, Any]:
        if not self._summaries_enabled:
            raise ValueError("Summaries disabled")
        return self._summaries_store.add_task(user_id, title, notes)

    def list_open_loops(self, user_id: str) -> List[Dict[str, Any]]:
        if not self._summaries_enabled:
            return []
        return self._summaries_store.list_open_loops(user_id)

    def list_tasks(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._summaries_enabled:
            return []
        return self._summaries_store.list_tasks(user_id, status=status)

    def list_commitments(self, user_id: str) -> List[Dict[str, Any]]:
        if not self._summaries_enabled:
            return []
        return self._summaries_store.list_commitments(user_id)

    def search_logs(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        query_lower = query.lower()

        if self._conversation.persist_enabled():
            path = self._conversation.thread_path(user_id)
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line:
                        continue
                    if query_lower in line.lower():
                        results.append({"line": line})
                        if len(results) >= limit:
                            return results

        for entry in self._conversation.load_thread(user_id, limit=200):
            content = str(entry.get("content", ""))
            if query_lower in content.lower():
                results.append({"role": entry.get("role"), "content": content})
                if len(results) >= limit:
                    break

        return results

    def maybe_consolidate(self, user_id: str, thread_id: str = "default") -> Optional[str]:
        if not (self._summaries_enabled and self._facts_enabled and self._consolidation_enabled):
            return None
        summary_state = self._summaries_store.load(user_id, thread_id)
        turns_since = int(summary_state.get("turns_since_summary", 0))
        if turns_since < max(self._summary_every_n, 1):
            return None

        try:
            store = get_store()
        except JobStoreError:
            consolidate(user_id, thread_id, self._conversation, self._facts_store, self._summaries_store)
            return None

        job = store.create({"type": "memory_consolidation", "user_id": user_id, "thread_id": thread_id})
        job_id = job["job_id"]

        def _run() -> None:
            store.set_status(job_id, "running")
            try:
                result = consolidate(user_id, thread_id, self._conversation, self._facts_store, self._summaries_store)
                store.set_result(job_id, result)
            except Exception as exc:
                store.set_error(job_id, str(exc))

        threading.Thread(target=_run, daemon=True).start()
        return job_id


memory_service = MemoryService()
