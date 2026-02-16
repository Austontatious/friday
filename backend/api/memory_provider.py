from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from backend.memory.factory import get_memory_provider, memory_namespace, selected_memory_provider_name
from backend.memory.provider import MemoryProviderError

router = APIRouter(tags=["memory"])


def _error_payload(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "retryable": retryable,
        }
    }


def _str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@router.post("/memory/confirm")
def confirm_memory(request: Request, payload: Dict[str, Any]):
    pending_ids = _str_list(payload.get("pending_ids"))
    decision = str(payload.get("decision") or "").strip().lower()
    note = _optional_text(payload.get("note"))

    if not pending_ids:
        raise HTTPException(
            status_code=400,
            detail=_error_payload(
                "bad_request",
                "Missing pending_ids",
                "Provide 'pending_ids' as a non-empty string array",
                False,
            ),
        )
    if decision not in {"accept", "reject"}:
        raise HTTPException(
            status_code=400,
            detail=_error_payload(
                "bad_request",
                "Invalid decision",
                "Provide 'decision' as 'accept' or 'reject'",
                False,
            ),
        )

    namespace = memory_namespace()
    provider = get_memory_provider()
    user_id = str(getattr(request.state, "user_id", "") or "").strip() or "localweb"
    decided_by = f"user:{user_id}"
    configured_provider = selected_memory_provider_name()

    try:
        result = provider.confirm(
            pending_ids=pending_ids,
            decision=decision,
            decided_by=decided_by,
            note=note,
            namespace=namespace,
        )
    except MemoryProviderError as exc:
        raise HTTPException(
            status_code=502 if exc.retryable else 400,
            detail=_error_payload(exc.code, exc.message, exc.detail, exc.retryable),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_error_payload("memory_confirm_failed", "Memory confirm failed", str(exc), True),
        ) from exc

    if configured_provider not in {"muninn", "legacy", "none"}:
        configured_provider = getattr(provider, "name", "none")
    return {
        "memory": {
            "provider": configured_provider,
            **(result if isinstance(result, dict) else {}),
        }
    }


@router.post("/memory/pending")
def pending_memory(payload: Dict[str, Any]):
    namespace = memory_namespace()
    entity_id = _optional_text(payload.get("entity_id"))
    provider = get_memory_provider()
    configured_provider = selected_memory_provider_name()

    try:
        data = provider.list_pending(namespace=namespace, entity_id=entity_id)
    except MemoryProviderError as exc:
        raise HTTPException(
            status_code=502 if exc.retryable else 400,
            detail=_error_payload(exc.code, exc.message, exc.detail, exc.retryable),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_error_payload("memory_pending_failed", "Memory pending list failed", str(exc), True),
        ) from exc

    items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(items, list):
        items = []
    if configured_provider not in {"muninn", "legacy", "none"}:
        configured_provider = getattr(provider, "name", "none")
    return {
        "memory": {
            "provider": configured_provider,
            "items": items,
        }
    }

