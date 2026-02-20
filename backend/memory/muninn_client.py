from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

import httpx

from backend.memory.provider import MemoryProviderError

logger = logging.getLogger("friday.memory.muninn.client")


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


class MuninnClient:
    def __init__(
        self,
        *,
        base_url: str,
        require_api_key: bool | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.require_api_key = _env_bool("MUNINN_REQUIRE_API_KEY", "0") if require_api_key is None else require_api_key
        self.api_key = (api_key if api_key is not None else os.getenv("MUNINN_API_KEY", "")).strip()
        self.retries = _env_int("MUNINN_HTTP_RETRIES", 1)
        self.retry_backoff_seconds = _env_float("MUNINN_HTTP_RETRY_BACKOFF_SECONDS", 0.2)
        self.connect_timeout = _env_float("MUNINN_CONNECT_TIMEOUT_SECONDS", 2.0)
        self.read_timeout = _env_float("MUNINN_READ_TIMEOUT_SECONDS", 5.0)
        self.overall_timeout = _env_float("MUNINN_HTTP_OVERALL_TIMEOUT_SECONDS", 7.0)

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._headers()
        timeout = httpx.Timeout(
            timeout=self.overall_timeout,
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.read_timeout,
            pool=self.connect_timeout,
        )

        attempts = self.retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            start = time.perf_counter()
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                latency_ms = int((time.perf_counter() - start) * 1000)
                if response.status_code >= 400:
                    retryable = response.status_code >= 500
                    detail = {
                        "status_code": response.status_code,
                        "body": response.text[:600],
                        "url": url,
                        "attempt": attempt,
                        "latency_ms": latency_ms,
                    }
                    if retryable and attempt < attempts:
                        logger.warning(
                            "muninn_http_retry path=%s attempt=%s latency_ms=%s status=%s",
                            path,
                            attempt,
                            latency_ms,
                            response.status_code,
                        )
                        self._sleep_before_retry()
                        continue
                    raise MemoryProviderError(
                        code="muninn_http_error",
                        message=f"Muninn returned HTTP {response.status_code}",
                        detail=detail,
                        retryable=retryable,
                    )

                try:
                    data = response.json()
                except Exception as exc:
                    raise MemoryProviderError(
                        code="muninn_invalid_response",
                        message="Muninn returned non-JSON response",
                        detail={"url": url, "attempt": attempt, "error": str(exc)},
                        retryable=True,
                    ) from exc
                if not isinstance(data, dict):
                    raise MemoryProviderError(
                        code="muninn_invalid_response",
                        message="Muninn response has invalid format",
                        detail={"url": url, "type": type(data).__name__},
                        retryable=True,
                    )
                return data
            except MemoryProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts:
                    raise
                logger.warning(
                    "muninn_retryable_error path=%s attempt=%s code=%s",
                    path,
                    attempt,
                    exc.code,
                )
                self._sleep_before_retry()
            except httpx.TimeoutException as exc:
                last_error = exc
                latency_ms = int((time.perf_counter() - start) * 1000)
                if attempt >= attempts:
                    logger.warning(
                        "muninn_timeout path=%s url=%s attempts=%s latency_ms=%s connect_timeout=%s read_timeout=%s overall_timeout=%s error=%s",
                        path,
                        url,
                        attempts,
                        latency_ms,
                        self.connect_timeout,
                        self.read_timeout,
                        self.overall_timeout,
                        type(exc).__name__,
                    )
                    raise MemoryProviderError(
                        code="muninn_timeout",
                        message="Muninn request timed out",
                        detail={
                            "url": url,
                            "attempt": attempt,
                            "latency_ms": latency_ms,
                            "connect_timeout": self.connect_timeout,
                            "read_timeout": self.read_timeout,
                            "overall_timeout": self.overall_timeout,
                        },
                        retryable=True,
                    ) from exc
                self._sleep_before_retry()
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                logger.warning(
                    "muninn_transport_retry path=%s attempt=%s error=%s",
                    path,
                    attempt,
                    type(exc).__name__,
                )
                self._sleep_before_retry()

        raise MemoryProviderError(
            code="muninn_unavailable",
            message="Muninn request failed",
            detail=str(last_error) if last_error is not None else "unknown_error",
            retryable=True,
        )

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.require_api_key:
            if not self.api_key:
                raise MemoryProviderError(
                    code="muninn_auth_missing",
                    message="MUNINN_REQUIRE_API_KEY=1 but MUNINN_API_KEY is empty",
                    retryable=False,
                )
            headers["X-API-Key"] = self.api_key
            return headers
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _sleep_before_retry(self) -> None:
        if self.retry_backoff_seconds <= 0:
            return
        time.sleep(self.retry_backoff_seconds)
