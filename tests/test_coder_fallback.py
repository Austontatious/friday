from __future__ import annotations

import asyncio

from backend.core import chat_engine
from backend.memory.factory import reset_memory_provider_cache
from backend.security.trust import TRUSTED_USER, TrustContext


def test_run_chat_falls_back_to_primary_when_coder_route_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_LLM_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_MEMORY_PROVIDER", "none")
    monkeypatch.setenv("FRIDAY_CODER_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_CODER_BASE_URL", "http://coder:8000")
    monkeypatch.setenv("FRIDAY_CODER_MODEL_NAME", "Lexi-Coder")
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRIDAY_LOG_DIR", str(tmp_path / "logs"))
    reset_memory_provider_cache()

    calls: list[dict] = []

    async def fake_generate_messages(messages, **kwargs):  # noqa: ANN001
        calls.append(
            {
                "kwargs": dict(kwargs),
                "messages": messages,
            }
        )
        if kwargs.get("base_url_override") == "http://coder:8000":
            raise chat_engine.LLMRequestError("coder unavailable")
        return "primary-response"

    monkeypatch.setattr(chat_engine.llm_client, "generate_messages", fake_generate_messages)

    result = asyncio.run(
        chat_engine.run_chat(
            payload={
                "prompt": "Write a migration checklist.",
                "user_id": "device_coder_fallback",
                "workspace_id": "default",
                "agent_profile": "coding",
            },
            trust=TrustContext(level=TRUSTED_USER, reasons=["test"]),
            require_confirm=None,
        )
    )

    assert result["assistant_text"] == "primary-response"
    assert result["meta"]["llm_route"] == "primary"
    assert any(call["kwargs"].get("base_url_override") == "http://coder:8000" for call in calls)
    assert any(not call["kwargs"].get("base_url_override") for call in calls)
    assert any("<INTERACTION_POLICY>" in str(call["messages"][0]["content"]) for call in calls)
