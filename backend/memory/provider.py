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

_SECRET_HINTS = (
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

_CONFIRM_REQUIRED_KINDS = {"email", "phone", "address", "ssn_like", "medical"}

_CANDIDATE_PATTERNS = (
    (r"\bcall me (?P<value>[^.?!\n]+)", "fact", "preferred_name", ["profile"], 0.95),
    (r"\bi (?:really )?prefer (?P<value>[^.?!\n]+)", "preference", "preference", ["preference"], 0.90),
    (r"\bi (?:really )?like (?P<value>[^.?!\n]+)", "preference", "likes", ["preference"], 0.88),
)

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?:\+?1[\s.-]*)?(?:\(?\d{3}\)?[\s.-]*)\d{3}[\s.-]*\d{4}")


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _inject_budget_chars(default_chars: int = 1800, default_tokens: int = 450) -> int:
    max_chars = max(_env_int("FRIDAY_MEMORY_MAX_INJECT_CHARS", default_chars), 256)
    max_tokens = max(_env_int("FRIDAY_MEMORY_MAX_INJECT_TOKENS", default_tokens), 64)
    token_budget_chars = max_tokens * 4
    return min(max_chars, token_budget_chars)


def _clean_text(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text).strip(" \"'.,;:()[]{}")
    if len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


def _is_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in _SECRET_HINTS)


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
        return {"provider": self.name, "cards": [], "items": []}

    def stage(
        self,
        candidates: List[Dict[str, Any]],
        *,
        namespace: str,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "provider": self.name,
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
            "provider": self.name,
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
        return {"provider": self.name, "items": []}


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
        return {"provider": self.name, "cards": _legacy_cards(bundle, max(1, k)), "items": []}

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
            "provider": self.name,
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
                "provider": self.name,
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
            "provider": self.name,
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
        return {"provider": self.name, "items": []}


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

    max_cards = max(_env_int("FRIDAY_MEMORY_MAX_INJECT_CARDS", max_cards), 1)
    max_bullets = max(_env_int("FRIDAY_MEMORY_MAX_INJECT_BULLETS", max_bullets), 1)
    budget_chars = _inject_budget_chars()

    lines = ["<SYSTEM_MEMORY>"]
    used_chars = len(lines[0]) + 1
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

        header_line = f"- {title} [{card_type}]"
        projected = used_chars + len(header_line) + 1
        if projected > budget_chars:
            break
        lines.append(header_line)
        used_chars = projected
        for bullet in clean_bullets[:max_bullets]:
            bullet_line = f"  - {bullet}"
            projected = used_chars + len(bullet_line) + 1
            if projected > budget_chars:
                break
            lines.append(bullet_line)
            used_chars = projected
        card_count += 1

    if card_count == 0:
        return ""
    closing_line = "</SYSTEM_MEMORY>"
    if used_chars + len(closing_line) + 1 <= budget_chars:
        lines.append(closing_line)
    else:
        lines.append("</SYSTEM_MEMORY>")
    return "\n".join(lines)


def _requires_confirmation(kind: str, value: str) -> tuple[bool, Optional[str]]:
    if kind in _CONFIRM_REQUIRED_KINDS:
        return True, f"sensitive_kind:{kind}"
    if _EMAIL_PATTERN.search(value):
        return True, "sensitive_pattern:email"
    if _PHONE_PATTERN.search(value):
        return True, "sensitive_pattern:phone"
    return False, None


def _build_candidate(
    *,
    kind: str,
    key: str,
    value: str,
    tags: List[str],
    confidence: float,
    entity_id: str,
    source_id: str,
    note: str = "friday_heuristic_v1",
) -> Dict[str, Any]:
    candidate: Dict[str, Any] = {
        "kind": kind,
        "entity": {"id": entity_id or "ent_local_user", "type": "user"},
        "payload": {
            "key": key,
            "value": value,
            "tags": tags,
        },
        "confidence": confidence,
        "provenance": {
            "source_type": "user",
            "source_id": source_id,
            "note": note,
            "ts": time.time(),
        },
    }
    needs_confirm, reason = _requires_confirmation(kind, value)
    if needs_confirm:
        candidate["policy"] = {"requires_confirmation": True}
        if reason:
            candidate["policy"]["reason"] = reason
    return candidate


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
            _build_candidate(
                kind=kind,
                key=key,
                value=value,
                tags=tags,
                confidence=confidence,
                entity_id=entity_id,
                source_id=source_id,
            )
        )

    email_match = _EMAIL_PATTERN.search(text)
    if email_match:
        email = _clean_text(email_match.group(0), limit=180)
        if email and not _is_sensitive(email):
            marker = f"email:email:{email.lower()}"
            if marker not in seen:
                seen.add(marker)
                candidates.append(
                    _build_candidate(
                        kind="email",
                        key="email",
                        value=email,
                        tags=["contact", "sensitive"],
                        confidence=0.99,
                        entity_id=entity_id,
                        source_id=source_id,
                        note="friday_sensitive_regex_v1",
                    )
                )

    phone_match = _PHONE_PATTERN.search(text)
    if phone_match:
        phone = _clean_text(phone_match.group(0), limit=64)
        if phone and not _is_sensitive(phone):
            marker = f"phone:phone:{phone.lower()}"
            if marker not in seen:
                seen.add(marker)
                candidates.append(
                    _build_candidate(
                        kind="phone",
                        key="phone",
                        value=phone,
                        tags=["contact", "sensitive"],
                        confidence=0.99,
                        entity_id=entity_id,
                        source_id=source_id,
                        note="friday_sensitive_regex_v1",
                    )
                )

    max_candidates = max(_env_int("FRIDAY_MEMORY_MAX_CANDIDATES_PER_TURN", 6), 1)
    if len(candidates) > max_candidates:
        return candidates[:max_candidates]
    return candidates
