from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.memory.facts_store import FactsStore
from backend.memory.summaries_store import SummariesStore
from backend.memory.memory import MemoryStore


def build_identity_snapshot(facts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    snapshot = {
        "preferences": [],
        "profile": [],
        "constraints": [],
        "projects": [],
        "goals": [],
    }
    for fact in facts:
        tags = set((fact.get("tags") or []))
        if "preference" in tags:
            snapshot["preferences"].append(fact)
        if "profile" in tags:
            snapshot["profile"].append(fact)
        if "constraint" in tags:
            snapshot["constraints"].append(fact)
        if "project" in tags:
            snapshot["projects"].append(fact)
        if "goal" in tags:
            snapshot["goals"].append(fact)
    return snapshot


def retrieve_bundle(
    user_id: str,
    workspace_id: str,
    prompt: str,
    memory: MemoryStore,
    facts: FactsStore,
    summaries: SummariesStore,
    limit_turns: int,
    facts_limit: int = 10,
    summaries_limit: int = 5,
) -> Dict[str, Any]:
    recent_turns = memory.load_thread(user_id, workspace_id, limit=limit_turns)
    relevant_facts = facts.search(user_id, workspace_id, prompt, limit=facts_limit)
    relevant_summaries = summaries.search(user_id, workspace_id, prompt, limit=summaries_limit)
    open_loops = summaries.list_open_loops(user_id, workspace_id)
    commitments = summaries.list_commitments(user_id, workspace_id)
    tasks = summaries.list_tasks(user_id, workspace_id, status="open")
    identity = build_identity_snapshot(facts.list_facts(user_id, workspace_id, limit=50))

    return {
        "recent_turns": recent_turns,
        "relevant_facts": relevant_facts,
        "relevant_summaries": relevant_summaries,
        "open_loops": open_loops,
        "commitments": commitments,
        "tasks": tasks,
        "identity": identity,
    }
