from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from backend.core.capabilities import get_capabilities
from backend.core.interaction_policy import render_policy_block
from backend.tools.engine import tool_schema_list


_PROMPT_PROFILES = {
    "friday_exec": """You are FRIDAY, an executive assistant and systems operator.

Tone & style
- Be concise, precise, and action-oriented.
- Keep a calm, professional tone.
- Prefer short paragraphs and bullet points.
- Avoid filler, excessive disclaimers, and performative politeness.

Operating mode (30B-class model)
- You can handle complex multi-step reasoning, long-context documents, and nuanced tradeoffs.
- Use this strength to produce correct, practical outputs: plans, checklists, decisions, drafts, and implementations.
- When the user asks for execution steps, produce a concrete sequence with verification points.

Truthfulness & epistemics (non-negotiable)
- Never claim you performed an action unless the system/tool output confirms it.
- Never fabricate tool results, memory contents, files, metrics, logs, or external facts.
- If a detail is unknown, say it is unknown and proceed with best-effort assumptions labeled as assumptions.
- When you notice contradictions in the prompt/context, call them out and choose the safest interpretation.

Clarification discipline
- If blocked, ask exactly ONE clarifying question.
- If not blocked, do not ask questions-make a reasonable assumption and continue.
- Only ask a clarifying question when the answer would materially change.

Primary goal
Drive tasks to completion:
1) Identify objective and constraints
2) Produce an actionable plan or output
3) Track open loops and commitments
4) Propose next actions with the smallest possible user burden

Reasoning & planning expectations
- For complex tasks: outline a plan first (3-7 steps), then execute.
- Include explicit acceptance criteria when implementing systems.
- Offer a checkpoint summary when the task spans many changes or multiple subsystems.

Error handling
- Prefer graceful degradation over failure.
- If a dependency is down (e.g., memory service), continue operating and explain the fallback behavior briefly.
- Provide a recovery or next-step path.

Security & privacy posture
- Treat user data as sensitive by default.
- Do not store secrets (API keys, passwords) in memory.
- Do not persist sensitive personal data without explicit user intent/confirmation.
- If a request involves risky actions, recommend safer alternatives.

Model class
- 30B full precision (fp16) via vLLM.
- You may use deeper reasoning than a small model, but keep outputs tight and usable.

Capabilities enabled (source of truth for behavior)
{{CAPABILITIES_ENABLED_JSON}}

Memory behavior (Muninn-integrated when enabled)
- Memory is provided as injected <SYSTEM_MEMORY> cards. Use them as context, not as absolute truth.
- Do not reference raw transcripts or internal memory item IDs unless the UI explicitly displays them.
- After responding, you may propose MemoryCandidate items for staging.
- Sensitive candidates require user confirmation. Treat them as PENDING until confirmed.
- If memory is unavailable or errors:
  - proceed without memory
  - do not degrade user experience beyond a brief note
  - do not repeatedly retry in a way that harms latency

Identity snapshot
(Use this to personalize and keep continuity. It may be empty.)
Preferences:
{{PREFERENCES_BLOCK}}

Profile facts:
{{PROFILE_FACTS_BLOCK}}

Constraints:
{{CONSTRAINTS_BLOCK}}

Projects:
{{PROJECTS_BLOCK}}

Goals:
{{GOALS_BLOCK}}

Active loops:
{{ACTIVE_LOOPS_BLOCK}}

Open loops:
{{OPEN_LOOPS_BLOCK}}

Commitments:
{{COMMITMENTS_BLOCK}}

Tasks:
{{TASKS_BLOCK}}

Relevant facts:
{{RELEVANT_FACTS_BLOCK}}

Relevant summaries:
{{RELEVANT_SUMMARIES_BLOCK}}

Tools available (call only when necessary)
{{TOOLS_SCHEMA_BLOCK}}

Tool call format (JSON only):
{"id": "<string>", "name": "<tool_name>", "args": { ... }}

Response format
- plain text only
- default structure:
  1) Direct answer / output
  2) (optional) bullets: rationale, assumptions, next actions"""
}


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _format_kv(items: List[Dict[str, Any]], label_key: str = "key") -> str:
    if not items:
        return "- (none)"
    lines = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get(label_key, "")).strip()
        value = str(item.get("value", "")).strip()
        if not value:
            continue
        conf = item.get("confidence")
        tags = ",".join(item.get("tags") or [])
        if conf is not None:
            lines.append(f"- {key}: {value} (conf {conf:.2f}, tags {tags})")
        else:
            lines.append(f"- {key}: {value} (tags {tags})")
    if not lines:
        return "- (none)"
    return "\n".join(lines)


def _format_items(items: List[Dict[str, Any]], label_key: str) -> str:
    if not items:
        return "- (none)"
    lines = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = item.get(label_key) or item.get("item") or item.get("title") or ""
        label = str(label).strip()
        if not label:
            continue
        lines.append(f"- {label}")
    if not lines:
        return "- (none)"
    return "\n".join(lines)


def _format_tools(tool_schema: List[Dict[str, Any]]) -> str:
    if not tool_schema:
        return "- (none)"
    lines: List[str] = []
    for tool in tool_schema:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "").strip() or "unnamed_tool"
        desc = str(tool.get("description") or "").strip()
        args = tool.get("args_schema", {})
        args_json = json.dumps(args, ensure_ascii=True, sort_keys=True)
        if desc:
            lines.append(f"- {name}: {desc} args={args_json}")
        else:
            lines.append(f"- {name}: args={args_json}")
    if not lines:
        return "- (none)"
    return "\n".join(lines)


def _json_block(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=True, sort_keys=True)


def _render_template(template: str, values: Dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _cap_system_prompt(base_prompt: str, system_memory_block: Optional[str]) -> tuple[str, bool, int]:
    cap_chars = _env_int("FRIDAY_SYSTEM_PROMPT_MAX_CHARS", 16000)
    if not system_memory_block:
        if len(base_prompt) <= cap_chars:
            return base_prompt, False, 0
        return base_prompt[:cap_chars], False, 0

    memory_block = system_memory_block
    with_memory = f"{base_prompt}\n\n{memory_block}"
    if len(with_memory) <= cap_chars:
        return with_memory, True, len(memory_block)

    base_headroom = cap_chars - len(base_prompt) - 2
    if base_headroom <= 0:
        truncated_base = base_prompt[:cap_chars]
        return truncated_base, False, 0

    truncated_memory = memory_block[:base_headroom]
    return f"{base_prompt}\n\n{truncated_memory}", True, len(truncated_memory)


def build_messages(
    user_prompt: str,
    memory_bundle: Dict[str, Any],
    tool_schema: Optional[List[Dict[str, Any]]] = None,
    system_memory_block: Optional[str] = None,
    interaction_policy: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    profile = _env("FRIDAY_PROMPT_PROFILE", "friday_exec")
    system_template = _PROMPT_PROFILES.get(profile, _PROMPT_PROFILES["friday_exec"])

    capabilities = get_capabilities()
    identity = memory_bundle.get("identity") if isinstance(memory_bundle.get("identity"), dict) else {}

    if tool_schema is None:
        tool_schema = tool_schema_list()

    template_values = {
        "CAPABILITIES_ENABLED_JSON": _json_block(capabilities.get("enabled")),
        "PREFERENCES_BLOCK": _format_kv(identity.get("preferences", [])),
        "PROFILE_FACTS_BLOCK": _format_kv(identity.get("profile", [])),
        "CONSTRAINTS_BLOCK": _format_kv(identity.get("constraints", [])),
        "PROJECTS_BLOCK": _format_kv(identity.get("projects", [])),
        "GOALS_BLOCK": _format_kv(identity.get("goals", [])),
        "ACTIVE_LOOPS_BLOCK": _format_items(memory_bundle.get("active_loops", []), "item"),
        "OPEN_LOOPS_BLOCK": _format_items(memory_bundle.get("open_loops", []), "item"),
        "COMMITMENTS_BLOCK": _format_items(memory_bundle.get("commitments", []), "item"),
        "TASKS_BLOCK": _format_items(memory_bundle.get("tasks", []), "title"),
        "RELEVANT_FACTS_BLOCK": _format_kv(memory_bundle.get("relevant_facts", [])),
        "RELEVANT_SUMMARIES_BLOCK": _format_items(memory_bundle.get("relevant_summaries", []), "summary"),
        "TOOLS_SCHEMA_BLOCK": _format_tools(tool_schema),
    }
    base_prompt = _render_template(system_template, template_values)
    if isinstance(interaction_policy, dict) and interaction_policy:
        base_prompt = f"{base_prompt}\n\n{render_policy_block(interaction_policy)}"
    system_prompt, _, _ = _cap_system_prompt(base_prompt, system_memory_block)

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in memory_bundle.get("recent_turns", []):
        role = turn.get("role", "user")
        content = str(turn.get("content", ""))
        if not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})
    return messages
