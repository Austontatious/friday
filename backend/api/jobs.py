from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.jobs.store import JobStore, JobStoreError, get_store

router = APIRouter(tags=["jobs"])


def _error_payload(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "retryable": retryable,
        }
    }


def _error_response(status_code: int, code: str, message: str, detail: Any = None, retryable: bool = False) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_error_payload(code, message, detail, retryable),
    )


def _jobs_enabled() -> bool:
    return str(os.getenv("FRIDAY_JOBS_ENABLED", "1")).lower() in {"1", "true", "yes", "on"}


def _require_store() -> Tuple[Optional[JobStore], Optional[JSONResponse]]:
    try:
        return get_store(), None
    except JobStoreError as exc:
        return None, _error_response(503, "jobs_backend_unavailable", "Jobs backend unavailable", str(exc), False)


@router.post("/jobs", summary="Create a new async job")
def create_job(payload: Optional[Dict[str, Any]] = None):
    if not _jobs_enabled():
        return _error_response(503, "jobs_disabled", "Jobs are disabled", "Set FRIDAY_JOBS_ENABLED=1", False)

    store, error = _require_store()
    if error:
        return error

    job = store.create(payload or {})
    return {"job_id": job["job_id"], "status": job["status"]}


@router.get("/jobs/{job_id}", summary="Get job status")
def get_job(job_id: str):
    if not _jobs_enabled():
        return _error_response(503, "jobs_disabled", "Jobs are disabled", "Set FRIDAY_JOBS_ENABLED=1", False)

    store, error = _require_store()
    if error:
        return error

    job = store.get(job_id)
    if not job:
        return _error_response(404, "job_not_found", "Job not found", job_id, False)

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "detail": job.get("detail"),
    }


@router.get("/jobs/{job_id}/result", summary="Get job result")
def get_job_result(job_id: str):
    if not _jobs_enabled():
        return _error_response(503, "jobs_disabled", "Jobs are disabled", "Set FRIDAY_JOBS_ENABLED=1", False)

    store, error = _require_store()
    if error:
        return error

    job = store.get(job_id)
    if not job:
        return _error_response(404, "job_not_found", "Job not found", job_id, False)

    status = job.get("status")
    if status != "done":
        return _error_response(409, "job_not_ready", "Job not complete", status, True)

    return {"job_id": job_id, "result": job.get("result")}
