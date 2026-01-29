from __future__ import annotations

import json
import os
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Tiered memory store (Phase 1)."""

    def __init__(self) -> None:
        self._threads: Dict[str, List[dict]] = {}
        self._lock = threading.Lock()
        self._persist_enabled = _env_bool("FRIDAY_MEMORY_PERSIST_ENABLED", "0")
        self._vector_enabled = _env_bool("FRIDAY_MEMORY_VECTOR_ENABLED", "0")
        self._data_dir = os.getenv("FRIDAY_DATA_DIR", "/data")
        self._thread_id = "default"

    def load_thread(self, user_id: str, workspace_id: str, limit: Optional[int] = None) -> List[dict]:
        persisted = self._load_persisted(user_id, workspace_id, limit=limit)
        with self._lock:
            live = list(self._threads.get(self._thread_key(user_id, workspace_id), []))
        combined = persisted + live
        if limit is not None and limit > 0:
            return combined[-limit:]
        return combined

    def append(self, user_id: str, workspace_id: str, role: str, content: str, meta: Optional[Dict[str, Any]] = None) -> None:
        entry: Dict[str, Any] = {
            "ts": _utc_ts(),
            "role": role,
            "content": content,
        }
        if meta:
            entry["meta"] = meta

        with self._lock:
            key = self._thread_key(user_id, workspace_id)
            self._threads.setdefault(key, []).append(entry)

        if self._persist_enabled:
            self._append_persisted(user_id, workspace_id, entry)

    def vector_enabled(self) -> bool:
        return self._vector_enabled

    def persist_enabled(self) -> bool:
        return self._persist_enabled

    def thread_path(self, user_id: str, workspace_id: str) -> Path:
        return self._thread_path(user_id, workspace_id)

    def recall_vector(self, query: str) -> List[dict]:
        if not self._vector_enabled:
            return []
        return []

    def _append_persisted(self, user_id: str, workspace_id: str, entry: Dict[str, Any]) -> None:
        path = self._thread_path(user_id, workspace_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _load_persisted(self, user_id: str, workspace_id: str, limit: Optional[int] = None) -> List[dict]:
        if not self._persist_enabled:
            return []
        path = self._thread_path(user_id, workspace_id)
        if not path.exists():
            return []

        if limit is not None and limit > 0:
            buffer: Deque[dict] = deque(maxlen=limit)
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        buffer.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return list(buffer)

        entries: List[dict] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def _thread_path(self, user_id: str, workspace_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", user_id) or "unknown"
        safe_ws = re.sub(r"[^a-zA-Z0-9_.-]", "_", workspace_id) or "default"
        return Path(self._data_dir) / "users" / safe_id / "workspaces" / safe_ws / "threads" / f"{self._thread_id}.jsonl"

    def _thread_key(self, user_id: str, workspace_id: str) -> str:
        return f"{workspace_id}:{user_id}"
