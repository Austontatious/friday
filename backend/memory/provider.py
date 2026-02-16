from __future__ import annotations

import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from backend.memory.service import memory_service

logger = logging.getLogger("friday.memory.provider")

_SENSITIVE_HINTS = (
    "password",
    "passcode",
    "ssn",
    "social security",
    "credit card",
    "debit card",
    "bank account",
    "routing number",
    "cvv",
    "date of birth",
    "dob",
)

_CANDIDATE_PATTERNS = (
    (r"\bcall me (?P<value>[^.?!\n]+)", "fact", "preferred_name", ["profile"], 0.95),
    (r"\bi (?:really )?prefer (?P<value>[^.?!\n]+)", "preference", "preference", ["preference"], 0.90),
    (r"\bi (?:really )?like (?P<value>[^.?!\n]+)", "preference", "likes", ["preference"], 0.88),
)


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _clean_text(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text).strip(" \"'.,;:()[]{}")
    if len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


def _is_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in _SENSITIVE_HINTS)


def _as_tag_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        text = _clean_text(item, limit=40)
        if text:
            result.append(text)
    return result


@runtime_checkable
class MemoryProvider(Protocol):
    name: str

    def rehydrate(
        self,
        user_text: str,
        entity_id: str,
        *,
        namespace: str,
        profile: str,
        k: int = 8,
    ) -> Dict[str, Any]:
        ...

    def stage(
        self,
        candidates: List[Dict[str, Any]],
        *,
        namespace: str,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        ...

    def confirm(
        self,
        pending_ids: List[str],
        decision: str,
        decided_by: str,
        note: Optional[str] = None,
        *,
        namespace: str,
    ) -> Dict[str, Any]:
        ...

    def list_pending(self, *, namespace: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
        ...


@dataclass
class MemoryProviderError(Exception):
    code: str
    message: str
    detail: Any = None
    retryable: bool = True

    def as_payload(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "retryable": self.retryable,
        }


class NullMemoryProvider:
    name = "none"

    def rehydrate(
        self,
        user_text: str,
        entity_id: str,
        *,
        namespace: str,
        profile: str,
        k: int = 8,
    ) -> Dict[str, Any]:
        return {"cards": [], "items": []}

    def stage(
        self,
        candidates: List[Dict[str, Any]],
        *,
        namespace: str,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "accepted": 0,
            "pending": 0,
            "rejected": len(candidates or []),
            "accepted_ids": [],
            "pending_ids": [],
            "reject_reasons": ["memory_disabled"] if candidates else [],
            "pending_reasons": [],
        }

    def confirm(
        self,
        pending_ids: List[str],
        decision: str,
        decided_by: str,
        note: Optional[str] = None,
        *,
        namespace: str,
    ) -> Dict[str, Any]:
        return {
            "namespace": namespace,
            "decision": decision,
            "processed": 0,
            "accepted_writes": 0,
            "rejected": 0,
            "missing": len(pending_ids or []),
            "expired": 0,
            "accepted_ids": [],
            "reasons": ["memory_disabled"] if pending_ids else [],
        }

    def list_pending(self, *, namespace: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
        return {"items": []}


class LegacyMemoryProvider:
    name = "legacy"

    def __init__(self) -> None:
        self._history_limit = max(_env_int("FRIDAY_CONTEXT_TURNS", 20), 1)

    def rehydrate(
        self,
        user_text: str,
        entity_id: str,
        *,
        namespace: str,
        profile: str,
        k: int = 8,
    ) -> Dict[str, Any]:
        bundle = memory_service.retrieve(
            user_id=entity_id,
            workspace_id=namespace,
            prompt=user_text,
            limit_turns=self._history_limit,
        )
        return {"cards": _legacy_cards(bundle, max(1, k)), "items": []}

    def stage(
        self,
        candidates: List[Dict[str, Any]],
        *,
        namespace: str,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        accepted_ids: List[str] = []
        reject_reasons: List[str] = []
        for candidate in candidates or []:
            payload = candidate.get("payload") if isinstance(candidate, dict) else {}
            payload = payload if isinstance(payload, dict) else {}
            kind = _clean_text(candidate.get("kind") if isinstance(candidate, dict) else "", limit=24) or "fact"
            key = _clean_text(payload.get("key"), limit=64) or kind
            value = _clean_text(payload.get("value") or payload.get("text"), limit=220)
            if not value:
                reject_reasons.append("missing_value")
                continue

            tags = _as_tag_list(payload.get("tags"))
            if not tags:
                if kind == "preference":
                    tags = ["preference"]
                elif key == "preferred_name":
                    tags = ["profile"]

            confidence_raw = candidate.get("confidence") if isinstance(candidate, dict) else None
            confidence: Optional[float] = None
            if isinstance(confidence_raw, (int, float)):
                confidence = float(confidence_raw)

            try:
                created = memory_service.remember_fact(
                    user_id=_entity_from_candidate(candidate) or "ent_user",
                    workspace_id=namespace,
                    key=key,
                    value=value,
                    tags=tags,
                    confidence=confidence,
                    source="legacy_provider",
                )
                accepted_ids.append(str(created.get("id") or created.get("key") or uuid.uuid4().hex))
            except Exception as exc:
                reject_reasons.append(f"legacy_store_failed:{exc}")

        return {
            "accepted": len(accepted_ids),
            "pending": 0,
            "rejected": len(reject_reasons),
            "accepted_ids": accepted_ids,
            "pending_ids": [],
            "reject_reasons": reject_reasons,
            "pending_reasons": [],
        }

    def confirm(
        self,
        pending_ids: List[str],
        decision: str,
        decided_by: str,
        note: Optional[str] = None,
        *,
        namespace: str,
    ) -> Dict[str, Any]:
        if decision == "accept":
            reasons = ["legacy_provider_has_no_pending_queue"]
            return {
                "namespace": namespace,
                "decision": decision,
                "processed": len(pending_ids),
                "accepted_writes": 0,
                "rejected": 0,
                "missing": len(pending_ids),
                "expired": 0,
                "accepted_ids": [],
                "reasons": reasons if pending_ids else [],
            }
        return {
            "namespace": namespace,
            "decision": decision,
            "processed": len(pending_ids),
            "accepted_writes": 0,
            "rejected": len(pending_ids),
            "missing": 0,
            "expired": 0,
            "accepted_ids": [],
            "reasons": [],
        }

    def list_pending(self, *, namespace: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
        return {"items": []}


def _entity_from_candidate(candidate: Any) -> str:
    if not isinstance(candidate, dict):
        return ""
    entity = candidate.get("entity")
    if isinstance(entity, dict):
        entity_id = _clean_text(entity.get("id"), limit=96)
        if entity_id:
            return entity_id
    return ""


def _legacy_cards(bundle: Dict[str, Any], max_cards: int) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    identity = bundle.get("identity") if isinstance(bundle, dict) else {}
    identity = identity if isinstance(identity, dict) else {}

    card_specs = (
        ("preferences", "Preferences", "preference"),
        ("profile", "Profile", "fact"),
        ("constraints", "Constraints", "constraint"),
        ("projects", "Projects", "project"),
        ("goals", "Goals", "goal"),
    )
    for field, title, card_type in card_specs:
        rows = identity.get(field) if isinstance(identity.get(field), list) else []
        bullets: List[str] = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            key = _clean_text(row.get("key"), limit=48)
            value = _clean_text(row.get("value"), limit=160)
            if not value:
                continue
            bullets.append(f"{key}: {value}" if key else value)
        if bullets:
            cards.append({"card_type": card_type, "title": title, "bullets": bullets})

    relevant_facts = bundle.get("relevant_facts") if isinstance(bundle.get("relevant_facts"), list) else []
    fact_bullets: List[str] = []
    for fact in relevant_facts[:4]:
        if not isinstance(fact, dict):
            continue
        key = _clean_text(fact.get("key"), limit=48)
        value = _clean_text(fact.get("value"), limit=160)
        if not value:
            continue
        fact_bullets.append(f"{key}: {value}" if key else value)
    if fact_bullets:
        cards.append({"card_type": "fact", "title": "Relevant facts", "bullets": fact_bullets})

    relevant_summaries = bundle.get("relevant_summaries") if isinstance(bundle.get("relevant_summaries"), list) else []
    summary_bullets: List[str] = []
    for item in relevant_summaries[:2]:
        if not isinstance(item, dict):
            continue
        summary = _clean_text(item.get("summary"), limit=180)
        if summary:
            summary_bullets.append(summary)
    if summary_bullets:
        cards.append({"card_type": "summary", "title": "Relevant summaries", "bullets": summary_bullets})

    return cards[:max_cards]


def render_system_memory_block(cards: List[Dict[str, Any]], max_cards: int = 8, max_bullets: int = 3) -> str:
    if not cards:
        return ""

    lines = ["<SYSTEM_MEMORY>"]
    card_count = 0
    for card in cards:
        if card_count >= max_cards:
            break
        if not isinstance(card, dict):
            continue
        title = _clean_text(card.get("title"), limit=80) or "Memory"
        card_type = _clean_text(card.get("card_type") or card.get("kind"), limit=24) or "memory"
        bullets_raw = card.get("bullets")
        bullets = bullets_raw if isinstance(bullets_raw, list) else []
        clean_bullets = [_clean_text(item, limit=180) for item in bullets]
        clean_bullets = [item for item in clean_bullets if item]
        if not clean_bullets:
            continue

        lines.append(f"- {title} [{card_type}]")
        for bullet in clean_bullets[:max_bullets]:
            lines.append(f"  - {bullet}")
        card_count += 1

    lines.append("</SYSTEM_MEMORY>")
    if card_count == 0:
        return ""
    return "\n".join(lines)


def extract_memory_candidates(user_text: str, entity_id: str, *, source_id: str) -> List[Dict[str, Any]]:
    if not user_text or not isinstance(user_text, str):
        return []
    text = user_text.strip()
    if not text:
        return []

    seen: set[str] = set()
    candidates: List[Dict[str, Any]] = []
    for pattern, kind, key, tags, confidence in _CANDIDATE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _clean_text(match.group("value"), limit=180)
        if not value or _is_sensitive(value):
            continue
        marker = f"{kind}:{key}:{value.lower()}"
        if marker in seen:
            continue
        seen.add(marker)
        candidates.append(
            {
                "kind": kind,
                "entity": {"id": entity_id or "ent_user", "type": "user"},
                "payload": {
                    "key": key,
                    "value": value,
                    "tags": tags,
                },
                "confidence": confidence,
                "provenance": {
                    "source_type": "user",
                    "source_id": source_id,
                    "note": "friday_heuristic_v1",
                    "ts": time.time(),
                },
            }
        )

    if len(candidates) > 3:
        return candidates[:3]
    return candidates
