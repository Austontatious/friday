from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend.core.capabilities import get_capabilities
from backend.tools.engine import tool_schema_list


_PROMPT_PROFILES = {
    "friday_exec": (
        "You are FRIDAY, an executive assistant. Be concise, precise, and action-oriented. "
        "Drive toward completion, keep a calm professional tone, and avoid fluff. "
        "If blocked, ask exactly one clarifying question."
    )
}


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _format_kv(items: List[Dict[str, Any]], label_key: str = "key") -> str:
    if not items:
        return "- (none)"
    lines = []
    for item in items:
        key = item.get(label_key, "")
        value = item.get("value", "")
        conf = item.get("confidence")
        tags = ",".join(item.get("tags") or [])
        if conf is not None:
            lines.append(f"- {key}: {value} (conf {conf:.2f}, tags {tags})")
        else:
            lines.append(f"- {key}: {value} (tags {tags})")
    return "\n".join(lines)


def _format_items(items: List[Dict[str, Any]], label_key: str) -> str:
    if not items:
        return "- (none)"
    lines = []
    for item in items:
        label = item.get(label_key) or item.get("item") or item.get("title") or ""
        lines.append(f"- {label}")
    return "\n".join(lines)


def build_messages(
    user_prompt: str,
    memory_bundle: Dict[str, Any],
    tool_schema: Optional[List[Dict[str, Any]]] = None,
    system_memory_block: Optional[str] = None,
) -> List[Dict[str, str]]:
    profile = _env("FRIDAY_PROMPT_PROFILE", "friday_exec")
    model_class = _env("FRIDAY_MODEL_CLASS", "30b")
    system_policy = _PROMPT_PROFILES.get(profile, _PROMPT_PROFILES["friday_exec"])

    capabilities = get_capabilities()
    identity = memory_bundle.get("identity", {})

    if tool_schema is None:
        tool_schema = tool_schema_list()

    system_sections = [system_policy]
    if system_memory_block:
        system_sections.append(system_memory_block)
    system_sections.extend(
        [
            f"Model class: {model_class}",
            f"Capabilities enabled: {capabilities.get('enabled')}",
            f"Capabilities available: {capabilities.get('available')}",
            "Identity snapshot:",
            "Preferences:\n" + _format_kv(identity.get("preferences", [])),
            "Profile facts:\n" + _format_kv(identity.get("profile", [])),
            "Constraints:\n" + _format_kv(identity.get("constraints", [])),
            "Projects:\n" + _format_kv(identity.get("projects", [])),
            "Goals:\n" + _format_kv(identity.get("goals", [])),
            "Active loops:",
            "Open loops:\n" + _format_items(memory_bundle.get("open_loops", []), "item"),
            "Commitments:\n" + _format_items(memory_bundle.get("commitments", []), "item"),
            "Tasks:\n" + _format_items(memory_bundle.get("tasks", []), "title"),
            "Relevant facts:\n" + _format_kv(memory_bundle.get("relevant_facts", [])),
            "Relevant summaries:\n" + _format_items(memory_bundle.get("relevant_summaries", []), "summary"),
        ]
    )

    if tool_schema:
        system_sections.append("Tools available (call only when necessary):")
        for tool in tool_schema:
            name = tool.get("name")
            desc = tool.get("description", "")
            args = tool.get("args_schema", {})
            system_sections.append(f"- {name}: {desc} args={args}")
        system_sections.append(
            "Tool call format (JSON): {\"id\": string, \"name\": string, \"args\": object}"
        )

    system_sections.append("Response format: plain text only.")
    system_prompt = "\n\n".join(system_sections)

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in memory_bundle.get("recent_turns", []):
        role = turn.get("role", "user")
        content = str(turn.get("content", ""))
        if not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})
    return messages
