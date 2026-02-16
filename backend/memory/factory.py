from __future__ import annotations

import logging
import os
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
        try:
            return fn(*args, **kwargs)
        except MemoryProviderError as exc:
            if self.fallback_name == "none":
                fallback_label = "no memory"
            else:
                fallback_label = self.fallback_name
            logger.warning(
                "Muninn unavailable; falling back to %s (%s: %s)",
                fallback_label,
                exc.code,
                exc.message,
            )
        except Exception as exc:
            if self.fallback_name == "none":
                fallback_label = "no memory"
            else:
                fallback_label = self.fallback_name
            logger.warning("Muninn unavailable; falling back to %s (%s)", fallback_label, exc)
        return getattr(self._fallback, method)(*args, **kwargs)

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


def _legacy_fallback_or_none() -> MemoryProvider:
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
    logger.info("Memory provider: muninn base_url=%s namespace=%s profile=%s", base_url, namespace, profile)
    primary = MuninnMemoryProvider(base_url=base_url, namespace=namespace, profile=profile)
    fallback = _legacy_fallback_or_none()
    return _FallbackMemoryProvider(primary, fallback)


def reset_memory_provider_cache() -> None:
    get_memory_provider.cache_clear()

