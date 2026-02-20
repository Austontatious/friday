from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api import memory_provider as memory_provider_api
from backend.core import chat_engine
from backend.main import create_app
from backend.memory.factory import _FallbackMemoryProvider, get_memory_provider, reset_memory_provider_cache
from backend.memory.muninn_client import MuninnClient
from backend.memory.provider import LegacyMemoryProvider, MemoryProviderError, NullMemoryProvider
from backend.security.trust import TRUSTED_USER, TrustContext


@pytest.fixture(autouse=True)
def _reset_provider_cache():
    reset_memory_provider_cache()
    yield
    reset_memory_provider_cache()


def test_provider_selection_from_env(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORY_PROVIDER", "none")
    provider = get_memory_provider()
    assert provider.name == "none"

    reset_memory_provider_cache()
    monkeypatch.setenv("FRIDAY_MEMORY_PROVIDER", "legacy")
    provider = get_memory_provider()
    assert isinstance(provider, LegacyMemoryProvider)


def test_muninn_client_api_key_handling(monkeypatch):
    client = MuninnClient(base_url="http://muninn:8000", require_api_key=True, api_key="")
    with pytest.raises(MemoryProviderError) as exc:
        client.post("/v0/memory/rehydrate", {"query": "hello"})
    assert exc.value.code == "muninn_auth_missing"

    def fake_post(self, url, json=None, headers=None):  # noqa: ANN001
        assert headers["Content-Type"] == "application/json"
        assert headers["X-API-Key"] == "secret"
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = MuninnClient(base_url="http://muninn:8000", require_api_key=True, api_key="secret")
    data = client.post("/v0/memory/rehydrate", {"query": "hello"})
    assert data["ok"] is True


def test_muninn_client_timeout_maps_to_timeout_error(monkeypatch):
    monkeypatch.setenv("MUNINN_HTTP_RETRIES", "1")
    monkeypatch.setenv("MUNINN_HTTP_RETRY_BACKOFF_SECONDS", "0")
    attempts = {"count": 0}

    def fake_post(self, url, json=None, headers=None):  # noqa: ANN001
        attempts["count"] += 1
        request = httpx.Request("POST", url)
        raise httpx.ReadTimeout("timed out", request=request)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = MuninnClient(base_url="http://muninn:8000")

    with pytest.raises(MemoryProviderError) as exc:
        client.post("/v0/memory/rehydrate", {"query": "hello"})

    assert exc.value.code == "muninn_timeout"
    assert exc.value.retryable is True
    assert exc.value.detail["url"] == "http://muninn:8000/v0/memory/rehydrate"
    assert attempts["count"] == 2


def test_fallback_provider_returns_actual_provider_name():
    class BrokenMuninn:
        name = "muninn"

        def rehydrate(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

        def stage(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

        def confirm(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

        def list_pending(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

    wrapped = _FallbackMemoryProvider(BrokenMuninn(), NullMemoryProvider())
    data = wrapped.rehydrate("hello", "ent_test", namespace="friday", profile="friday", k=8)
    assert data["provider"] == "none"
    assert data["fallback_reason"] == "muninn_unavailable"


def test_confirm_endpoint_forwards_and_returns_shape(monkeypatch):
    class StubProvider:
        name = "muninn"

        def __init__(self):
            self.last_call = None

        def confirm(self, pending_ids, decision, decided_by, note=None, *, namespace):  # noqa: ANN001
            self.last_call = {
                "pending_ids": pending_ids,
                "decision": decision,
                "decided_by": decided_by,
                "note": note,
                "namespace": namespace,
            }
            return {
                "provider": "legacy",
                "processed": len(pending_ids),
                "accepted_ids": list(pending_ids),
                "accepted_writes": len(pending_ids),
                "rejected": 0,
            }

        def list_pending(self, *, namespace, entity_id=None):  # noqa: ANN001
            return {"provider": "legacy", "items": []}

    stub = StubProvider()
    monkeypatch.setattr(memory_provider_api, "get_memory_provider", lambda: stub)
    monkeypatch.setattr(memory_provider_api, "selected_memory_provider_name", lambda: "muninn")

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/memory/confirm",
        headers={"X-Friday-Device": "device_123"},
        json={"pending_ids": ["p_1", "p_2"], "decision": "accept"},
    )
    assert response.status_code == 200
    payload = response.json()["memory"]
    assert payload["provider"] == "legacy"
    assert payload["processed"] == 2
    assert payload["accepted_ids"] == ["p_1", "p_2"]
    assert stub.last_call["decided_by"] == "user:device_123"
    client.close()


def test_run_chat_survives_memory_provider_failures(monkeypatch, tmp_path):
    class BrokenMuninn:
        name = "muninn"

        def rehydrate(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

        def stage(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

        def confirm(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

        def list_pending(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise MemoryProviderError(code="muninn_unavailable", message="down", retryable=True)

    wrapped = _FallbackMemoryProvider(BrokenMuninn(), NullMemoryProvider())
    monkeypatch.setattr(chat_engine, "get_memory_provider", lambda: wrapped)
    monkeypatch.setattr(chat_engine, "selected_memory_provider_name", lambda: "muninn")
    monkeypatch.setattr(chat_engine.llm_client, "enabled", False)
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FRIDAY_LOG_DIR", str(tmp_path / "logs"))

    result = asyncio.run(
        chat_engine.run_chat(
            payload={"prompt": "Hello", "user_id": "device_123", "workspace_id": "default"},
            trust=TrustContext(level=TRUSTED_USER, reasons=["test"]),
            require_confirm=None,
        )
    )
    assert result["assistant_text"]
    assert result["memory"]["provider"] == "none"
