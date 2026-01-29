from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

from backend.audit.logger import log_event
from backend.memory.facts_store import FactsStore
from backend.memory.memory import MemoryStore
from backend.memory.summaries_store import SummariesStore

_FACT_PATTERNS: Sequence[Tuple[str, str, List[str]]] = (
    (r"\bmy name is (?P<value>[^.?!]+)", "name", ["profile"]),
    (r"\bi am (?P<value>[^.?!]+)", "profile", ["profile"]),
    (r"\bi like (?P<value>[^.?!]+)", "likes", ["preference"]),
    (r"\bi prefer (?P<value>[^.?!]+)", "preference", ["preference"]),
    (r"\bmy favorite (?P<value>[^.?!]+)", "favorite", ["preference"]),
    (r"\bi don't like (?P<value>[^.?!]+)", "dislike", ["constraint"]),
    (r"\bi do not want (?P<value>[^.?!]+)", "constraint", ["constraint"]),
)

_OPEN_LOOP_PATTERNS: Sequence[str] = (
    r"\bneed to (?P<item>[^.?!]+)",
    r"\bremember to (?P<item>[^.?!]+)",
    r"\bfollow up on (?P<item>[^.?!]+)",
    r"\btodo:? (?P<item>[^.?!]+)",
)


def summarize_turns(turns: List[Dict[str, Any]], max_chars: int = 800) -> str:
    if not turns:
        return ""
    lines = []
    for turn in turns[-12:]:
        role = turn.get("role", "user")
        content = str(turn.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    summary = " | ".join(lines)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3] + "..."
    return summary


def extract_facts(turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    for turn in turns:
        if turn.get("role") != "user":
            continue
        text = str(turn.get("content", ""))
        for pattern, key, tags in _FACT_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group("value").strip()
                facts.append({"key": key, "value": value, "tags": tags})
    return facts


def extract_open_loops(turns: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []
    for turn in turns:
        if turn.get("role") != "user":
            continue
        text = str(turn.get("content", ""))
        for pattern in _OPEN_LOOP_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                item = match.group("item").strip()
                if item:
                    items.append(item)
    return items


def consolidate(
    user_id: str,
    workspace_id: str,
    thread_id: str,
    conversation: MemoryStore,
    facts: FactsStore,
    summaries: SummariesStore,
) -> Dict[str, Any]:
    turns = conversation.load_thread(user_id, workspace_id, limit=40)
    summary_text = summarize_turns(turns)
    existing = summaries.load(user_id, workspace_id, thread_id)
    open_loops = existing.get("open_loops", [])

    new_open = extract_open_loops(turns)
    open_items = {loop.get("item") for loop in open_loops}
    for item in new_open:
        if item in open_items:
            continue
        summaries.add_open_loop(user_id, workspace_id, item, thread_id)
        open_items.add(item)

    facts_added = 0
    for fact in extract_facts(turns):
        facts.upsert_fact(user_id, workspace_id, fact["key"], fact["value"], tags=fact.get("tags"), source="consolidation")
        facts_added += 1

    summaries.update_summary(user_id, workspace_id, summary_text, thread_id=thread_id)

    result = {
        "summary": summary_text,
        "facts_added": facts_added,
        "open_loops_added": len(new_open),
    }
    log_event("memory_consolidation", result, user_id, workspace_id)
    return result
