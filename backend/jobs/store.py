from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _queue_backend() -> str:
    return os.getenv("FRIDAY_QUEUE_BACKEND", "memory").strip().lower() or "memory"


class JobStoreError(Exception):
    pass


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = _utc_ts()
        job = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "payload": payload,
        }
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def set_status(self, job_id: str, status: str, detail: Optional[str] = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = status
            job["updated_at"] = _utc_ts()
            if detail:
                job["detail"] = detail

    def set_result(self, job_id: str, result: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "done"
            job["updated_at"] = _utc_ts()
            job["result"] = result

    def set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "error"
            job["updated_at"] = _utc_ts()
            job["error"] = error


_memory_store = JobStore()


def get_store() -> JobStore:
    backend = _queue_backend()
    if backend == "memory":
        return _memory_store
    raise JobStoreError(f"Unsupported queue backend: {backend}")
