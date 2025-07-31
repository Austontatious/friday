# memory_store_json.py
"""
Lightweight JSONL persistence backend.

Each line in the file is a single JSON object produced by
`MemoryShard.to_json()`.

Thread‑safe for CPython thanks to the GIL + a process‑level Lock.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import List

from .memory_types import MemoryShard

_LOCK = threading.Lock()


class MemoryStoreJSON:
    def __init__(self, filepath: str, max_entries: int = 10000):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries

    # ------------ Core helpers ------------ #

    def load(self) -> List[MemoryShard]:
        if not self.filepath.exists():
            return []
        with self.filepath.open("r", encoding="utf-8") as f:
            return [MemoryShard.from_json(line) for line in f if line.strip()]

    def _write_all(self, shards: List[MemoryShard]) -> None:
        tmp = self.filepath.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for shard in shards[-self.max_entries :]:
                f.write(shard.to_json() + "\n")
        tmp.replace(self.filepath)

    # ------------ Public API ------------ #

    def insert(self, shard: MemoryShard) -> None:
        with _LOCK:
            shards = self.load()
            shards.append(shard)
            self._write_all(shards)

    def history(self, *, session_id: str = "default", limit: int = 10, by_timestamp: bool = True) -> List[MemoryShard]:
        shards = [s for s in self.load() if s.session_id == session_id]
        key = (lambda s: s.timestamp) if by_timestamp else (lambda s: s.last_used)
        shards.sort(key=key, reverse=True)
        return shards[:limit]

    def mark_used(self, shard_id: str) -> None:
        with _LOCK:
            shards = self.load()
            for shard in shards:
                if shard.id == shard_id:
                    shard.touch()
                    break
            self._write_all(shards)
            
    def query(self, query: str, top_k: int = 5, session_id="default") -> List[MemoryShard]:
        """Simple substring query over text or response fields."""
        shards = [s for s in self.load() if s.session_id == session_id]
        matches = []
        for s in shards:
            content = (s.prompt or "") + " " + (s.response or "") + " " + (s.text or "")
            if query.lower() in content.lower():
                matches.append(s)
        matches.sort(key=lambda s: s.last_used, reverse=True)
        return matches[:top_k]

    def clear(self, session_id: str = "default") -> None:
        """
        Delete **all** shards for the given session_id.
        """
        with _LOCK:
            shards = [s for s in self.load() if s.session_id != session_id]
            self._write_all(shards)

