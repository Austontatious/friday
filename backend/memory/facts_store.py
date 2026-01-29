from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_tags(tags: Optional[Sequence[str]]) -> List[str]:
    if not tags:
        return []
    cleaned = []
    for tag in tags:
        tag = str(tag).strip().lower()
        if tag:
            cleaned.append(tag)
    return sorted(set(cleaned))


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _score(query_tokens: Sequence[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    tokens = set(_tokenize(text))
    if not tokens:
        return 0.0
    overlap = len(tokens.intersection(query_tokens))
    return overlap / max(len(tokens), 1)


class FactsStore:
    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir
        self._max_facts = _env_int("FRIDAY_MEMORY_MAX_FACTS", 500)

    def list_facts(self, user_id: str, tag: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        facts = self._load(user_id)
        if tag:
            tag = tag.lower()
            facts = [fact for fact in facts if tag in (fact.get("tags") or [])]
        facts.sort(key=lambda fact: fact.get("confidence", 0.0), reverse=True)
        if limit:
            return facts[:limit]
        return facts

    def search(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        facts = self._load(user_id)
        query_tokens = _tokenize(query)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for fact in facts:
            text = f"{fact.get('key','')} {fact.get('value','')} {' '.join(fact.get('tags') or [])}"
            score = _score(query_tokens, text)
            if score > 0:
                scored.append((score, fact))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [fact for _, fact in scored[:limit]]

    def upsert_fact(
        self,
        user_id: str,
        key: str,
        value: str,
        tags: Optional[Sequence[str]] = None,
        confidence: Optional[float] = None,
        source: str = "user",
        pinned: bool = False,
    ) -> Dict[str, Any]:
        key = str(key).strip()
        value = str(value).strip()
        if not key or not value:
            raise ValueError("key and value are required")

        facts = self._load(user_id)
        now = _utc_ts()
        tags_list = _normalize_tags(tags)
        confidence_value = self._normalize_confidence(confidence)

        matching = [fact for fact in facts if fact.get("key") == key]
        if matching:
            updated = None
            for fact in matching:
                if str(fact.get("value", "")) == value:
                    updated = fact
                    break
            if updated:
                updated["updated_at"] = now
                updated["confidence"] = min(1.0, float(updated.get("confidence", 0.6)) + 0.1)
                updated["source"] = source
                updated["tags"] = _normalize_tags((updated.get("tags") or []) + tags_list)
                if pinned:
                    updated["pinned"] = True
            else:
                for fact in matching:
                    if fact.get("pinned"):
                        continue
                    fact["confidence"] = max(0.1, float(fact.get("confidence", 0.6)) - 0.2)
                    fact["updated_at"] = now
                new_fact = {
                    "key": key,
                    "value": value,
                    "confidence": confidence_value,
                    "source": source,
                    "updated_at": now,
                    "tags": tags_list,
                    "pinned": pinned,
                }
                facts.append(new_fact)
                updated = new_fact
        else:
            updated = {
                "key": key,
                "value": value,
                "confidence": confidence_value,
                "source": source,
                "updated_at": now,
                "tags": tags_list,
                "pinned": pinned,
            }
            facts.append(updated)

        self._prune(facts)
        self._save(user_id, facts)
        return updated

    def delete_fact(self, user_id: str, key: str) -> int:
        facts = self._load(user_id)
        before = len(facts)
        facts = [fact for fact in facts if fact.get("key") != key]
        removed = before - len(facts)
        if removed:
            self._save(user_id, facts)
        return removed

    def _load(self, user_id: str) -> List[Dict[str, Any]]:
        path = self._path(user_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return data
        return []

    def _save(self, user_id: str, facts: List[Dict[str, Any]]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")

    def _path(self, user_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", user_id) or "unknown"
        return Path(self._data_dir) / "users" / safe_id / "facts.json"

    def _prune(self, facts: List[Dict[str, Any]]) -> None:
        if self._max_facts <= 0:
            return
        if len(facts) <= self._max_facts:
            return

        pinned = [fact for fact in facts if fact.get("pinned")]
        unpinned = [fact for fact in facts if not fact.get("pinned")]
        unpinned.sort(key=lambda fact: fact.get("confidence", 0.0))
        allowed = max(self._max_facts - len(pinned), 0)
        trimmed = unpinned[-allowed:] if allowed else []
        facts[:] = pinned + trimmed

    def _normalize_confidence(self, confidence: Optional[float]) -> float:
        if confidence is None:
            return 0.7
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return 0.7
        return max(0.0, min(value, 1.0))
