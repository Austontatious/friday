from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional

from backend.memory.muninn_provider import MuninnMemoryProvider
from backend.memory.provider import LegacyMemoryProvider, MemoryProvider, MemoryProviderError, NullMemoryProvider

logger = logging.getLogger("friday.memory.factory")


def memory_namespace() -> str:
    return (os.getenv("MUNINN_NAMESPACE", "friday").strip() or "friday")


def memory_profile() -> str:
    return (os.getenv("MUNINN_PROFILE", "friday").strip() or "friday")


def selected_memory_provider_name() -> str:
    raw = os.getenv("FRIDAY_MEMORY_PROVIDER", "muninn").strip().lower()
    return raw or "muninn"


class _FallbackMemoryProvider:
    def __init__(self, primary: MemoryProvider, fallback: MemoryProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self.name = getattr(primary, "name", "muninn")
        self.fallback_name = getattr(fallback, "name", "none")

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        fn = getattr(self._primary, method)
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return _with_provider_name(result, provider=getattr(self._primary, "name", "muninn"), latency_ms=latency_ms)
        except MemoryProviderError as exc:
            logger.warning(
                "memory_provider_fallback method=%s primary=%s fallback=%s error_code=%s retryable=%s",
                method,
                getattr(self._primary, "name", "muninn"),
                self.fallback_name,
                exc.code,
                exc.retryable,
            )
            fallback_reason = exc.code
        except Exception as exc:
            logger.warning(
                "memory_provider_fallback method=%s primary=%s fallback=%s error_type=%s",
                method,
                getattr(self._primary, "name", "muninn"),
                self.fallback_name,
                type(exc).__name__,
            )
            fallback_reason = type(exc).__name__
        fallback_started = time.perf_counter()
        fallback_result = getattr(self._fallback, method)(*args, **kwargs)
        latency_ms = int((time.perf_counter() - fallback_started) * 1000)
        return _with_provider_name(
            fallback_result,
            provider=self.fallback_name,
            fallback_reason=fallback_reason,
            latency_ms=latency_ms,
        )

    def rehydrate(
        self,
        user_text: str,
        entity_id: str,
        *,
        namespace: str,
        profile: str,
        k: int = 8,
    ) -> Dict[str, Any]:
        return self._call("rehydrate", user_text, entity_id, namespace=namespace, profile=profile, k=k)

    def stage(
        self,
        candidates: List[Dict[str, Any]],
        *,
        namespace: str,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._call("stage", candidates, namespace=namespace, ttl_seconds=ttl_seconds)

    def confirm(
        self,
        pending_ids: List[str],
        decision: str,
        decided_by: str,
        note: Optional[str] = None,
        *,
        namespace: str,
    ) -> Dict[str, Any]:
        return self._call(
            "confirm",
            pending_ids,
            decision,
            decided_by,
            note=note,
            namespace=namespace,
        )

    def list_pending(self, *, namespace: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
        return self._call("list_pending", namespace=namespace, entity_id=entity_id)


def _fallback_provider() -> MemoryProvider:
    configured = (os.getenv("FRIDAY_MEMORY_FALLBACK_PROVIDER", "legacy").strip().lower() or "legacy")
    if configured not in {"legacy", "none"}:
        logger.warning("Unknown FRIDAY_MEMORY_FALLBACK_PROVIDER=%s; defaulting to legacy", configured)
        configured = "legacy"
    if configured == "none":
        return NullMemoryProvider()
    try:
        return LegacyMemoryProvider()
    except Exception as exc:
        logger.warning("Legacy memory provider unavailable; using no memory (%s)", exc)
        return NullMemoryProvider()


@lru_cache(maxsize=1)
def get_memory_provider() -> MemoryProvider:
    selected = selected_memory_provider_name()
    if selected == "none":
        logger.info("Memory provider: none")
        return NullMemoryProvider()
    if selected == "legacy":
        logger.info("Memory provider: legacy")
        return LegacyMemoryProvider()

    if selected != "muninn":
        logger.warning("Unknown FRIDAY_MEMORY_PROVIDER=%s; defaulting to muninn", selected)

    base_url = (os.getenv("MUNINN_BASE_URL", "http://127.0.0.1:8000").strip() or "http://127.0.0.1:8000").rstrip("/")
    namespace = memory_namespace()
    profile = memory_profile()
    logger.info("Memory provider selected=muninn base_url=%s namespace=%s profile=%s", base_url, namespace, profile)
    primary = MuninnMemoryProvider(base_url=base_url, namespace=namespace, profile=profile)
    fallback = _fallback_provider()
    return _FallbackMemoryProvider(primary, fallback)


def reset_memory_provider_cache() -> None:
    get_memory_provider.cache_clear()


def _with_provider_name(
    value: Any,
    *,
    provider: str,
    fallback_reason: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> Dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    out = dict(data)
    out["provider"] = provider
    if fallback_reason:
        out.setdefault("fallback_reason", fallback_reason)
    if isinstance(latency_ms, int):
        out.setdefault("latency_ms", latency_ms)
    return out
