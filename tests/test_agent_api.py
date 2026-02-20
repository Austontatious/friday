from __future__ import annotations

from fastapi.testclient import TestClient

from backend.agentic.events import on_agent_event, reset_agent_events_for_tests
from backend.agentic.service import agent_run_service
from backend.main import create_app


def test_agent_submit_and_wait_returns_result(monkeypatch):
    async def fake_run_chat(payload, trust, require_confirm):  # noqa: ANN001
        return {
            "assistant_text": "agent-ok",
            "text": "agent-ok",
            "tools": [],
            "meta": {"user_id": payload.get("user_id"), "workspace_id": payload.get("workspace_id")},
            "memory": {"provider": "none", "accepted_ids": [], "pending_ids": [], "pending_reasons": [], "rejected": 0},
        }

    from backend.agentic import service as agent_service_module

    monkeypatch.setattr(agent_service_module, "run_chat", fake_run_chat)
    agent_run_service.reset_for_tests()

    app = create_app()
    client = TestClient(app)

    submit = client.post(
        "/api/agent",
        headers={"X-Friday-Device": "device_agent_api"},
        json={"prompt": "hello async", "idempotency_key": "agent-api-1"},
    )
    assert submit.status_code == 200
    accepted = submit.json()
    assert accepted["status"] == "accepted"
    run_id = accepted["run_id"]

    waited = client.post(
        "/api/agent/wait",
        json={"run_id": run_id, "timeout_ms": 3000, "include_result": True},
    )
    assert waited.status_code == 200
    payload = waited.json()
    assert payload["status"] == "ok"
    assert payload["result"]["assistant_text"] == "agent-ok"

    status = client.get(f"/api/agent/{run_id}", params={"include_result": "true"})
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["status"] == "ok"
    assert status_payload["result"]["text"] == "agent-ok"
    client.close()


def test_agent_submit_honors_idempotency(monkeypatch):
    async def fake_run_chat(payload, trust, require_confirm):  # noqa: ANN001
        return {
            "assistant_text": "ok",
            "text": "ok",
            "tools": [],
            "meta": {},
            "memory": {"provider": "none", "accepted_ids": [], "pending_ids": [], "pending_reasons": [], "rejected": 0},
        }

    from backend.agentic import service as agent_service_module

    monkeypatch.setattr(agent_service_module, "run_chat", fake_run_chat)
    agent_run_service.reset_for_tests()

    app = create_app()
    client = TestClient(app)
    headers = {"X-Friday-Device": "device_agent_idem"}

    first = client.post(
        "/api/agent",
        headers=headers,
        json={"prompt": "hello", "idempotency_key": "idem-run-42"},
    )
    second = client.post(
        "/api/agent",
        headers=headers,
        json={"prompt": "hello again", "idempotency_key": "idem-run-42"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["run_id"] == second.json()["run_id"]
    assert second.json().get("cached") is True
    client.close()


def test_agent_wait_unknown_run_times_out():
    agent_run_service.reset_for_tests()
    app = create_app()
    client = TestClient(app)
    waited = client.post(
        "/api/agent/wait",
        json={"run_id": "run-does-not-exist", "timeout_ms": 10},
    )
    assert waited.status_code == 200
    payload = waited.json()
    assert payload["run_id"] == "run-does-not-exist"
    assert payload["status"] == "timeout"
    client.close()


def test_agent_emits_runtime_events_from_chat_meta(monkeypatch):
    async def fake_run_chat(payload, trust, require_confirm):  # noqa: ANN001
        return {
            "assistant_text": "ok",
            "text": "ok",
            "tools": [],
            "meta": {
                "runtime_events": [
                    {"type": "policy_selected", "mode": "focused"},
                    {"type": "retry_attempted", "reason": "llm_request_error"},
                ]
            },
            "memory": {"provider": "none", "accepted_ids": [], "pending_ids": [], "pending_reasons": [], "rejected": 0},
        }

    from backend.agentic import service as agent_service_module

    monkeypatch.setattr(agent_service_module, "run_chat", fake_run_chat)
    reset_agent_events_for_tests()
    agent_run_service.reset_for_tests()

    captured = []
    unsubscribe = on_agent_event(lambda event: captured.append(event))
    try:
        app = create_app()
        client = TestClient(app)
        submit = client.post(
            "/api/agent",
            headers={"X-Friday-Device": "device_agent_runtime_events"},
            json={"prompt": "hello", "idempotency_key": "agent-runtime-events-1"},
        )
        assert submit.status_code == 200
        run_id = submit.json()["run_id"]
        waited = client.post(
            "/api/agent/wait",
            json={"run_id": run_id, "timeout_ms": 3000, "include_result": True},
        )
        assert waited.status_code == 200
        assert waited.json()["status"] == "ok"
        client.close()
    finally:
        unsubscribe()

    assert any(event.stream == "runtime" and event.data.get("type") == "policy_selected" for event in captured)
    assert any(event.stream == "runtime" and event.data.get("type") == "retry_attempted" for event in captured)
