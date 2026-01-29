from __future__ import annotations

from typing import Dict, List


class MemoryStore:
    """Ephemeral in-memory thread store (Phase 0)."""

    def __init__(self) -> None:
        self._threads: Dict[str, List[dict]] = {}

    def load_thread(self, user_id: str) -> List[dict]:
        return list(self._threads.get(user_id, []))

    def append(self, user_id: str, role: str, content: str) -> None:
        self._threads.setdefault(user_id, []).append({
            "role": role,
            "content": content,
        })
