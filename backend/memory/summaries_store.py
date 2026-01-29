from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_user(user_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", user_id) or "unknown"


def _default_summary(thread_id: str) -> Dict[str, Any]:
    return {
        "thread_id": thread_id,
        "summary": "",
        "open_loops": [],
        "commitments": [],
        "tasks": [],
        "turns_since_summary": 0,
        "updated_at": None,
    }


class SummariesStore:
    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir

    def load(self, user_id: str, thread_id: str = "default") -> Dict[str, Any]:
        path = self._path(user_id, thread_id)
        if not path.exists():
            return _default_summary(thread_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _default_summary(thread_id)
        if not isinstance(data, dict):
            return _default_summary(thread_id)
        data.setdefault("thread_id", thread_id)
        data.setdefault("summary", "")
        data.setdefault("open_loops", [])
        data.setdefault("commitments", [])
        data.setdefault("tasks", [])
        data.setdefault("turns_since_summary", 0)
        data.setdefault("updated_at", None)
        return data

    def save(self, user_id: str, data: Dict[str, Any], thread_id: str = "default") -> None:
        path = self._path(user_id, thread_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def increment_turns(self, user_id: str, count: int = 1, thread_id: str = "default") -> None:
        data = self.load(user_id, thread_id)
        data["turns_since_summary"] = int(data.get("turns_since_summary", 0)) + count
        self.save(user_id, data, thread_id)

    def update_summary(
        self,
        user_id: str,
        summary: str,
        open_loops: Optional[List[Dict[str, Any]]] = None,
        commitments: Optional[List[Dict[str, Any]]] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
        thread_id: str = "default",
    ) -> Dict[str, Any]:
        data = self.load(user_id, thread_id)
        data["summary"] = summary
        data["open_loops"] = open_loops if open_loops is not None else data.get("open_loops", [])
        data["commitments"] = commitments if commitments is not None else data.get("commitments", [])
        data["tasks"] = tasks if tasks is not None else data.get("tasks", [])
        data["turns_since_summary"] = 0
        data["updated_at"] = _utc_ts()
        self.save(user_id, data, thread_id)
        return data

    def add_open_loop(self, user_id: str, item: str, thread_id: str = "default") -> Dict[str, Any]:
        data = self.load(user_id, thread_id)
        loop = {
            "id": self._new_id(),
            "item": item,
            "status": "open",
            "created_at": _utc_ts(),
            "resolved_at": None,
        }
        data.setdefault("open_loops", []).append(loop)
        self.save(user_id, data, thread_id)
        return loop

    def resolve_open_loop(self, user_id: str, loop_id: str, thread_id: str = "default") -> bool:
        data = self.load(user_id, thread_id)
        updated = False
        for loop in data.get("open_loops", []):
            if loop.get("id") == loop_id and loop.get("status") != "resolved":
                loop["status"] = "resolved"
                loop["resolved_at"] = _utc_ts()
                updated = True
        if updated:
            self.save(user_id, data, thread_id)
        return updated

    def add_task(self, user_id: str, title: str, notes: Optional[str] = None, thread_id: str = "default") -> Dict[str, Any]:
        data = self.load(user_id, thread_id)
        task = {
            "id": self._new_id(),
            "title": title,
            "notes": notes or "",
            "status": "open",
            "created_at": _utc_ts(),
            "completed_at": None,
        }
        data.setdefault("tasks", []).append(task)
        self.save(user_id, data, thread_id)
        return task

    def list_open_loops(self, user_id: str, thread_id: str = "default") -> List[Dict[str, Any]]:
        data = self.load(user_id, thread_id)
        return [loop for loop in data.get("open_loops", []) if loop.get("status") != "resolved"]

    def list_tasks(self, user_id: str, status: Optional[str] = None, thread_id: str = "default") -> List[Dict[str, Any]]:
        data = self.load(user_id, thread_id)
        tasks = data.get("tasks", [])
        if status:
            return [task for task in tasks if task.get("status") == status]
        return tasks

    def list_commitments(self, user_id: str, thread_id: str = "default") -> List[Dict[str, Any]]:
        data = self.load(user_id, thread_id)
        return data.get("commitments", [])

    def search(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        data = self.load(user_id)
        query_lower = query.lower()
        results = []
        summary_text = data.get("summary", "")
        if query_lower in summary_text.lower() and summary_text:
            results.append({
                "thread_id": data.get("thread_id", "default"),
                "summary": summary_text,
                "updated_at": data.get("updated_at"),
            })
        for loop in data.get("open_loops", []):
            if query_lower in loop.get("item", "").lower():
                results.append({
                    "thread_id": data.get("thread_id", "default"),
                    "summary": loop.get("item"),
                    "updated_at": loop.get("created_at"),
                })
        return results[:limit]

    def _path(self, user_id: str, thread_id: str) -> Path:
        safe_id = _sanitize_user(user_id)
        safe_thread = re.sub(r"[^a-zA-Z0-9_.-]", "_", thread_id) or "default"
        return Path(self._data_dir) / "users" / safe_id / "summaries" / f"{safe_thread}.json"

    def _new_id(self) -> str:
        return re.sub(r"[^a-z0-9]", "", _utc_ts().lower())
