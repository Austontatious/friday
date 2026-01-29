from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import httpx


def env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def service_status(enabled_key: str, url_key: str) -> Dict[str, Any]:
    enabled = env_bool(enabled_key, "0")
    if not enabled:
        return {"enabled": False, "status": "disabled"}
    url = os.getenv(url_key, "").strip()
    if not url:
        return {"enabled": True, "status": "not_configured"}
    ok, detail = probe(url)
    return {"enabled": True, "status": "healthy" if ok else "unhealthy", "detail": detail}


def memory_status() -> Dict[str, Any]:
    enabled = env_bool("FRIDAY_MEMORY_PERSIST_ENABLED", "0")
    if not enabled:
        return {"enabled": False, "status": "disabled"}

    data_dir = os.getenv("FRIDAY_DATA_DIR", "/data")
    ok, detail = probe_dir(data_dir)
    return {"enabled": True, "status": "healthy" if ok else "unhealthy", "detail": detail}


def jobs_status() -> Dict[str, Any]:
    enabled = env_bool("FRIDAY_JOBS_ENABLED", "0")
    if not enabled:
        return {"enabled": False, "status": "disabled"}

    backend = os.getenv("FRIDAY_QUEUE_BACKEND", "memory").strip().lower() or "memory"
    if backend == "memory":
        return {"enabled": True, "status": "healthy", "detail": "memory"}
    if backend == "redis":
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            return {"enabled": True, "status": "not_configured", "detail": "missing_redis_url"}
        ok, detail = probe_redis(redis_url)
        return {"enabled": True, "status": "healthy" if ok else "unhealthy", "detail": detail}
    return {"enabled": True, "status": "not_configured", "detail": f"unsupported_backend:{backend}"}


def normalize_url(url: str) -> str:
    base = url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    if "/v1/" in base:
        prefix = base.split("/v1", 1)[0] + "/v1"
        return f"{prefix}/models"
    return base


def probe_dir(path: str) -> Tuple[bool, str]:
    try:
        candidate = Path(path)
        candidate.mkdir(parents=True, exist_ok=True)
        test_file = candidate / ".friday_write_check"
        with test_file.open("w", encoding="utf-8") as handle:
            handle.write("ok")
        test_file.unlink(missing_ok=True)
        return True, "writable"
    except Exception as exc:
        return False, f"unwritable:{exc}"


def probe_redis(url: str) -> Tuple[bool, str]:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 6379
    if not host:
        return False, "invalid_redis_url"
    try:
        with socket.create_connection((host, port), timeout=2):
            return True, "reachable"
    except Exception as exc:
        return False, f"unreachable:{exc}"


def probe(url: str) -> Tuple[bool, str]:
    timeout = float(os.getenv("FRIDAY_SERVICE_HEALTH_TIMEOUT", "2"))
    target = normalize_url(url)
    try:
        resp = httpx.get(target, timeout=timeout)
        if resp.status_code < 400:
            return True, "reachable"
        return False, f"bad_status_{resp.status_code}"
    except Exception as exc:
        return False, f"unreachable:{exc}"


def is_ok(status: Dict[str, Any]) -> bool:
    if status.get("enabled") is False:
        return True
    return status.get("status") == "healthy"
