# friday/memory.py (with semantic search fallback)

import os
import json
import time
import logging
from typing import List, Optional, Dict, Any
from collections import deque
from uuid import uuid4

from friday.model_loader_core import ModelLoader
from friday.model_types import TaskType
from friday.memory.vector_store import archive_context_to_chroma, semantic_search

logger = logging.getLogger("friday")


class MemoryManager:
    def __init__(self, model_loader: Optional[ModelLoader] = None, memory_dir: str = "./memory_logs"):
        self.model_loader = model_loader
        self.context_window = deque(maxlen=20)
        self.session_store = []
        self.memory_dir = memory_dir
        self.session_memory_size = 0
        self.history = []

        os.makedirs(self.memory_dir, exist_ok=True)

    def _get_log_path(self, session_id: str) -> str:
        return os.path.join(self.memory_dir, f"{session_id}.jsonl")

    def store_context(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: str = "default",
        thread_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> str:
        context_id = str(uuid4())
        now = time.time()
        entry = {
            "id": context_id,
            "text": text,
            "metadata": metadata or {},
            "timestamp": now,
            "last_used": now,
            "session_id": session_id,
            "thread_id": thread_id,
            "project_id": project_id
        }

        entry_str = json.dumps(entry)
        entry_bytes = entry_str.encode("utf-8")
        self.session_memory_size += len(entry_bytes)

        self.context_window.append(entry)
        self.session_store.append(entry)

        log_path = self._get_log_path(session_id)
        with open(log_path, "a") as f:
            f.write(entry_str + "\n")

        logger.debug(f"[MemoryManager] Stored context: {context_id}")

        if self.session_memory_size > 100 * 1024 * 1024:
            logger.info(f"💾 Memory exceeded 100MB for session '{session_id}' — archiving.")
            self.flush_old_entries_to_chroma(session_id)

        return context_id

    def flush_old_entries_to_chroma(self, session_id: str):
        to_archive = self.session_store[:]
        self.session_store.clear()
        self.session_memory_size = 0

        archive_context_to_chroma(entries=to_archive, session_id=session_id)

    def retrieve_context(
        self,
        query: str,
        k: int = 5,
        session_id: str = "default"
    ) -> List[Dict[str, Any]]:
        results = list(self.context_window)[-k:]
        results = sorted(results, key=lambda x: x["last_used"], reverse=True)

        if len(results) < k:
            logger.info(f"[MemoryManager] Not enough results in window, searching Chroma.")
            additional = semantic_search(query=query, k=k - len(results))
            for match in additional:
                match["last_used"] = time.time()
                self.context_window.append(match)
                self.session_store.append(match)
            results.extend(additional)

        for result in results:
            result["last_used"] = time.time()
            try:
                self.session_store.remove(result)
            except ValueError:
                continue
            self.session_store.append(result)

        logger.info(f"[MemoryManager] Retrieved {len(results)} context entries.")
        return results

    def get_context_history(
        self,
        limit: int = 10,
        session_id: str = "default"
    ) -> List[Dict[str, Any]]:
        return [entry for entry in reversed(self.session_store) if entry["session_id"] == session_id][:limit]

    def clear(self, session_id: str = "default"):
        self.context_window.clear()
        self.session_store = [e for e in self.session_store if e["session_id"] != session_id]
        self.session_memory_size = sum(len(json.dumps(e).encode("utf-8")) for e in self.session_store)

        path = self._get_log_path(session_id)
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"[MemoryManager] Cleared disk memory for session '{session_id}'")

    async def process(self, input_text: str, task_type: Optional[TaskType] = None) -> str:
        self.history.append(input_text)
        logger.info(f"[MemoryManager] Processing task: {task_type or 'default'}")

        model_key = self._get_model_key_for_task(task_type)
        model = self.model_loader.get_model(model_key)

        if model is None:
            logger.error(f"❌ Model '{model_key}' not available.")
            return f"❌ Model '{model_key}' not available."

        try:
            response = await model.chat(input_text)
            return response
        except Exception as e:
            logger.exception("Model inference failed")
            return f"❌ Inference error: {str(e)}"

    def _get_model_key_for_task(self, task_type: Optional[TaskType]) -> str:
        if task_type == TaskType.BUG_FIX or task_type == TaskType.EXPLANATION or task_type == TaskType.TEST_GENERATION:
            return "deepseek"
        elif task_type == TaskType.GENERAL or task_type is None:
            return "friday"
        elif task_type == TaskType.REASONING:
            return "friday"
        return "friday"

    def get_statistics(self):
        return {
            "prompt_count": len(self.history),
            "last_prompt": self.history[-1] if self.history else None
        }

    def get_context(self, query: str) -> List[str]:
        return [c["text"] for c in self.retrieve_context(query)]

    def retrieve_contexts(self, query: str) -> List[str]:
        return self.get_context(query)

