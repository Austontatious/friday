from __future__ import annotations

import asyncio

from backend.core import chat_engine
from backend.memory.factory import reset_memory_provider_cache
from backend.security.trust import TRUSTED_USER, TrustContext


def test_run_chat_uses_blame_free_tool_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_LLM_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_MEMORY_PROVIDER", "none")
    monkeypatch.setenv("FRIDAY_TOOLS_ENABLED", "0")
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRIDAY_LOG_DIR", str(tmp_path / "logs"))
    reset_memory_provider_cache()

    async def fake_generate_messages(messages, **kwargs):  # noqa: ANN001
        return '{"id":"tool_1","name":"list_facts","args":{}}'

    monkeypatch.setattr(chat_engine.llm_client, "generate_messages", fake_generate_messages)

    result = asyncio.run(
        chat_engine.run_chat(
            payload={"prompt": "Pull my stored facts.", "user_id": "device_tool_fail", "workspace_id": "default"},
            trust=TrustContext(level=TRUSTED_USER, reasons=["test"]),
            require_confirm=None,
        )
    )

    assert "That failed because" in result["assistant_text"]
    assert "skip tools entirely" in result["assistant_text"]
    assert result["meta"]["certainty_level"] == "low"
    assert any(
        event.get("type") == "fallback_used" and event.get("reason") == "tool_calls_failed"
        for event in result["meta"]["runtime_events"]
    )


def test_run_chat_sets_high_certainty_when_verification_signal_present(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_LLM_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_MEMORY_PROVIDER", "none")
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRIDAY_LOG_DIR", str(tmp_path / "logs"))
    reset_memory_provider_cache()

    async def fake_generate_messages(messages, **kwargs):  # noqa: ANN001
        if any(msg.get("role") == "tool" for msg in messages):
            return "Checks completed. Proceed with the patch."
        return '{"id":"tool_2","name":"run_checks","args":{"suite":"unit"}}'

    def fake_execute_tool_call(*args, **kwargs):  # noqa: ANN002, ANN003
        return {
            "id": "tool_2",
            "name": "run_checks",
            "ok": True,
            "result": {"exit_code": 0, "status": "passed", "tests_passed": 12},
        }

    monkeypatch.setattr(chat_engine.llm_client, "generate_messages", fake_generate_messages)
    monkeypatch.setattr(chat_engine, "execute_tool_call", fake_execute_tool_call)

    result = asyncio.run(
        chat_engine.run_chat(
            payload={"prompt": "Run checks now and summarize.", "user_id": "device_certainty", "workspace_id": "default"},
            trust=TrustContext(level=TRUSTED_USER, reasons=["test"]),
            require_confirm=None,
        )
    )

    assert result["meta"]["certainty_level"] == "high"
    assert "Here's what I'm assuming" not in result["assistant_text"]
