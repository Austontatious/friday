from __future__ import annotations

from backend.tools import builtins  # noqa: F401 - registers default tools
from backend.core.prompt_builder import build_messages


def _empty_bundle():
    return {
        "recent_turns": [],
        "relevant_facts": [],
        "relevant_summaries": [],
        "open_loops": [],
        "commitments": [],
        "tasks": [],
        "identity": {},
    }


def test_prompt_truth_markers(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRIDAY_MEMORY_PROVIDER", "muninn")
    monkeypatch.setenv("FRIDAY_MEMORY_PERSIST_ENABLED", "0")
    monkeypatch.setenv("FRIDAY_LLM_ENABLED", "1")

    messages = build_messages(
        user_prompt="Prompt truth test",
        memory_bundle=_empty_bundle(),
        tool_schema=None,
        system_memory_block=None,
    )
    system_prompt = messages[0]["content"]

    assert "You are FRIDAY, an executive assistant and systems operator." in system_prompt
    assert '"llm": true' in system_prompt
    assert '"memory_persist": true' in system_prompt
    assert "Tools available (call only when necessary)" in system_prompt
    assert "Capabilities available" not in system_prompt


def test_system_memory_is_in_same_system_message_and_capped(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRIDAY_SYSTEM_PROMPT_MAX_CHARS", "5000")
    memory_block = "<SYSTEM_MEMORY>\n" + ("- Card [fact]\n  - value\n" * 80) + "</SYSTEM_MEMORY>"

    messages = build_messages(
        user_prompt="memory cap check",
        memory_bundle=_empty_bundle(),
        tool_schema=[{"name": "t", "description": "d", "args_schema": {"type": "object"}}],
        system_memory_block=memory_block,
    )

    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert len(messages[0]["content"]) <= 5000
    assert "<SYSTEM_MEMORY>" in messages[0]["content"]


def test_interaction_policy_block_is_injected(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path / "data"))
    messages = build_messages(
        user_prompt="policy check",
        memory_bundle=_empty_bundle(),
        tool_schema=[],
        system_memory_block=None,
        interaction_policy={
            "mode": "focused",
            "mode_source": "override",
            "banter_budget": 0,
            "one_question_max": 1,
            "max_chars": 900,
            "response_shape": "action_then_next_step",
        },
    )
    system_prompt = messages[0]["content"]
    assert "<INTERACTION_POLICY>" in system_prompt
    assert "mode=focused" in system_prompt
