from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from backend.memory.provider import MemoryProviderError

logger = logging.getLogger("friday.memory.muninn")


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class MuninnMemoryProvider:
    name = "muninn"

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        namespace: Optional[str] = None,
        profile: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("MUNINN_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.default_namespace = namespace or os.getenv("MUNINN_NAMESPACE", "friday")
        self.default_profile = profile or os.getenv("MUNINN_PROFILE", "friday")
        self.timeout_seconds = _env_float("MUNINN_HTTP_TIMEOUT_SECONDS", 2.5)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.post(url, json=payload, timeout=self.timeout_seconds)
        except Exception as exc:
            raise MemoryProviderError(
                code="muninn_unavailable",
                message="Muninn request failed",
                detail=str(exc),
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            detail = {
                "status_code": response.status_code,
                "body": response.text[:600],
                "url": url,
            }
            raise MemoryProviderError(
                code="muninn_http_error",
                message=f"Muninn returned HTTP {response.status_code}",
                detail=detail,
                retryable=response.status_code >= 500,
            )

        try:
            data = response.json()
        except Exception as exc:
            raise MemoryProviderError(
                code="muninn_invalid_response",
                message="Muninn returned non-JSON response",
                detail=str(exc),
                retryable=True,
            ) from exc
        if not isinstance(data, dict):
            raise MemoryProviderError(
                code="muninn_invalid_response",
                message="Muninn response has invalid format",
                detail={"type": type(data).__name__},
                retryable=True,
            )
        return data

    def rehydrate(
        self,
        user_text: str,
        entity_id: str,
        *,
        namespace: str,
        profile: str,
        k: int = 8,
    ) -> Dict[str, Any]:
        body = {
            "namespace": namespace or self.default_namespace,
            "query": user_text,
            "entity_id": entity_id or None,
            "k": max(int(k or 8), 1),
            "profile": profile or self.default_profile,
        }
        return self._post("/v0/memory/rehydrate", body)

    def stage(
        self,
        candidates: List[Dict[str, Any]],
        *,
        namespace: str,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "namespace": namespace or self.default_namespace,
            "candidates": candidates,
        }
        if ttl_seconds is not None:
            body["ttl_seconds"] = int(ttl_seconds)
        return self._post("/v0/memory/stage_candidates", body)

    def confirm(
        self,
        pending_ids: List[str],
        decision: str,
        decided_by: str,
        note: Optional[str] = None,
        *,
        namespace: str,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "namespace": namespace or self.default_namespace,
            "pending_ids": [str(item) for item in pending_ids],
            "decision": decision,
            "decided_by": decided_by,
        }
        if note:
            body["note"] = note
        return self._post("/v0/memory/confirm_candidates", body)

    def list_pending(self, *, namespace: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "namespace": namespace or self.default_namespace,
            "status": "pending",
            "limit": 50,
        }
        if entity_id:
            body["entity_id"] = entity_id
        return self._post("/v0/memory/list_pending", body)

