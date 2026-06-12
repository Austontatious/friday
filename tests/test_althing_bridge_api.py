from __future__ import annotations

import io
import urllib.error

from fastapi.testclient import TestClient

import backend.api.althing_chat as althing_chat
from backend.main import create_app
from backend.security.trust import TRUSTED_USER, TrustContext


def test_althing_bridge_success(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ALTHING_BRIDGE_ENABLED", "1")

    async def _fake_post_json(*, url: str, payload: dict, headers: dict[str, str], timeout_s: float):
        assert url.endswith("/chat/completions")
        assert headers.get("X-Friday-Bridge-Source") == "friday_ui_shell"
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][-1]["role"] == "user"
        assert payload["messages"][-1]["content"] == "hello from ui"
        return (
            200,
            {
                "choices": [{"message": {"role": "assistant", "content": "hello from althing"}}],
                "route": {"mode": "auto_no_reason", "harness_id": "executive_single"},
            },
            12,
        )

    monkeypatch.setattr(althing_chat, "_post_json", _fake_post_json)
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/althing/chat",
        headers={"X-Friday-Device": "bridge-success-device"},
        json={"prompt": "hello from ui"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_text"] == "hello from althing"
    assert body["meta"]["bridge_mode"] == "althing"
    assert body["meta"]["althing_harness_id"] == "executive_single"
    assert body["meta"]["bridge_prompt_mode"] == "althing_routed"
    assert body["meta"]["bridge_prompt_lane"] in {"30b", "7b"}
    client.close()


def test_althing_bridge_recursion_guard(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ALTHING_BRIDGE_ENABLED", "1")
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/althing/chat",
        headers={"X-Friday-Device": "bridge-guard-device", "X-Althing-Handoff": "1"},
        json={"prompt": "should reject"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "recursion_guard"
    client.close()


def test_althing_bridge_disabled(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ALTHING_BRIDGE_ENABLED", "0")
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/althing/chat",
        headers={"X-Friday-Device": "bridge-disabled-device"},
        json={"prompt": "bridge disabled"},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "althing_bridge_disabled"
    client.close()


def test_althing_bridge_upstream_http_error(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ALTHING_BRIDGE_ENABLED", "1")

    async def _fake_post_json(*, url: str, payload: dict, headers: dict[str, str], timeout_s: float):
        raise urllib.error.HTTPError(
            url=url,
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"router warming"}'),
        )

    monkeypatch.setattr(althing_chat, "_post_json", _fake_post_json)
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/althing/chat",
        headers={"X-Friday-Device": "bridge-http-error-device"},
        json={"prompt": "upstream down"},
    )
    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "althing_upstream_http_error"
    client.close()


def test_althing_bridge_lane_unavailable_falls_back_to_direct_friday(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ALTHING_BRIDGE_ENABLED", "1")

    async def _fake_post_json(*, url: str, payload: dict, headers: dict[str, str], timeout_s: float):
        return (
            200,
            {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "[error] backend failure: exec: no_routable_lane_available",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "route": {
                    "mode": "auto_no_reason",
                    "degraded": True,
                    "degradation_reasons": ["lane_not_routable:exec:unavailable"],
                },
            },
            8,
        )

    async def _fake_run_chat(payload: dict, **kwargs):
        assert payload["mode"] == "direct_friday"
        return {
            "assistant_text": "althing-ok",
            "text": "althing-ok",
            "meta": {"llm_route": "primary", "selected_model": "friday"},
        }

    monkeypatch.setattr(althing_chat, "_post_json", _fake_post_json)
    monkeypatch.setattr(althing_chat, "run_chat", _fake_run_chat)
    monkeypatch.setattr(
        althing_chat,
        "classify_request",
        lambda payload, headers: TrustContext(level=TRUSTED_USER, reasons=["test"]),
    )

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/althing/chat",
        headers={"X-Friday-Device": "bridge-fallback-device"},
        json={"prompt": "Althing bridge smoke. Reply exactly: althing-ok"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_text"] == "althing-ok"
    assert body["meta"]["llm_route"] == "primary"
    assert body["meta"]["bridge_mode"] == "althing"
    assert body["meta"]["bridge_fallback"] == "direct_friday_runtime_fallback"
    assert body["meta"]["bridge_fallback_reason"] == "no_routable_lane_available"
    client.close()


def test_althing_bridge_repo_path_prompt_uses_direct_friday_fallback(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ALTHING_BRIDGE_ENABLED", "1")

    async def _unexpected_post_json(*, url: str, payload: dict, headers: dict[str, str], timeout_s: float):
        raise AssertionError("Althing upstream should not be called for repo-path fallback")

    async def _fake_run_chat(payload: dict, **kwargs):
        assert payload["mode"] == "direct_friday"
        return {
            "assistant_text": "I can inspect the mounted workspace.",
            "text": "I can inspect the mounted workspace.",
            "meta": {"llm_route": "primary", "route": "retrieval_or_file"},
        }

    monkeypatch.setattr(althing_chat, "_post_json", _unexpected_post_json)
    monkeypatch.setattr(althing_chat, "run_chat", _fake_run_chat)
    monkeypatch.setattr(
        althing_chat,
        "classify_request",
        lambda payload, headers: TrustContext(level=TRUSTED_USER, reasons=["test"]),
    )

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/althing/chat",
        headers={"X-Friday-Device": "bridge-repo-fallback-device"},
        json={"prompt": "see if you can access /mnt/data/Friday and tell me what is there"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_text"] == "I can inspect the mounted workspace."
    assert body["meta"]["bridge_mode"] == "althing"
    assert body["meta"]["bridge_fallback"] == "direct_friday_read_only"
    client.close()


def test_direct_friday_chat_route_success(monkeypatch) -> None:
    async def _fake_run_chat(payload: dict, **kwargs):
        assert payload["prompt"] == "Say direct-friday-ok."
        assert payload["user_id"] == "direct-friday-success-device"
        return {
            "assistant_text": "direct-friday-ok",
            "text": "direct-friday-ok",
            "meta": {"llm_route": "primary", "selected_model": "friday"},
        }

    monkeypatch.setattr("backend.api.chat.run_chat", _fake_run_chat)

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        headers={"X-Friday-Device": "direct-friday-success-device"},
        json={"prompt": "Say direct-friday-ok."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_text"] == "direct-friday-ok"
    assert body["meta"]["llm_route"] == "primary"
    client.close()


def test_direct_friday_chat_route_still_available() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        headers={"X-Friday-Device": "direct-friday-route-check"},
        json={},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"]["code"] == "bad_request"
    client.close()
