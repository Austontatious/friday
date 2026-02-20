from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from backend.memory.muninn_client import MuninnClient
from backend.memory.provider import MemoryProviderError

logger = logging.getLogger("friday.memory.muninn")


class MuninnMemoryProvider:
    name = "muninn"

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        namespace: Optional[str] = None,
        profile: Optional[str] = None,
        client: Optional[MuninnClient] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("MUNINN_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.default_namespace = namespace or os.getenv("MUNINN_NAMESPACE", "friday")
        self.default_profile = profile or os.getenv("MUNINN_PROFILE", "friday")
        self.readonly = str(os.getenv("MUNINN_READONLY", "0")).strip().lower() in {"1", "true", "yes", "on"}
        self._client = client or MuninnClient(base_url=self.base_url)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._client.post(path, payload)
        if not isinstance(data, dict):
            raise MemoryProviderError(
                code="muninn_invalid_response",
                message="Muninn response has invalid format",
                detail={"type": type(data).__name__},
                retryable=True,
            )
        return {"provider": self.name, **data}

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
        if self.readonly:
            return {
                "provider": self.name,
                "accepted": 0,
                "pending": 0,
                "rejected": len(candidates or []),
                "accepted_ids": [],
                "pending_ids": [],
                "pending_reasons": [],
                "reject_reasons": ["muninn_readonly"] if candidates else [],
            }
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
        if self.readonly:
            return {
                "provider": self.name,
                "namespace": namespace or self.default_namespace,
                "decision": decision,
                "processed": len(pending_ids or []),
                "accepted_writes": 0,
                "rejected": len(pending_ids or []) if decision == "reject" else 0,
                "missing": len(pending_ids or []) if decision == "accept" else 0,
                "expired": 0,
                "accepted_ids": [],
                "reasons": ["muninn_readonly"] if pending_ids else [],
            }
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
            "limit": max(int(os.getenv("MUNINN_LIST_PENDING_LIMIT", "50")), 1),
        }
        if entity_id:
            body["entity_id"] = entity_id
        return self._post("/v0/memory/list_pending", body)
