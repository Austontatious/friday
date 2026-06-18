from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import create_app


def _client(monkeypatch, tmp_path) -> TestClient:  # noqa: ANN001
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path))
    app = create_app()
    return TestClient(app)


def _selection_context() -> dict[str, object]:
    return {
        "selection_set_id": "sel_slice5",
        "units": "mm",
        "frame": "canvas_2d",
        "items": [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True, "label": "A"},
            {"id": "point_B", "type": "point_2d", "coords": [10, 0], "locked": False, "label": "B"},
        ],
        "constraints": [],
        "named_references": {"A": "point_A", "B": "point_B"},
    }


def test_translate_returns_proposed_command_without_committing(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/sketchmath/sessions/{session_id}/translate",
        json={
            "utterance": "make A-B 17.5 mm at 45 degrees",
            "selection_context": _selection_context(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "command"
    assert payload["command"]["command_type"] == "set_line_polar"
    assert payload["command"]["selection"] == ["point_A", "point_B"]
    assert payload["command"]["mode"] == "preview"
    assert payload["command"]["parameters"]["length"] == 17.5
    assert payload["command"]["parameters"]["angle"] == 45.0
    assert client.get(f"/api/sketchmath/sessions/{session_id}").json()["history_length"] == 0
    client.close()


def test_translate_can_request_clarification(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/sketchmath/sessions/{session_id}/translate",
        json={
            "utterance": "make the selected line longer",
            "selection_context": _selection_context(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "clarification_required"
    assert payload["reason"]
    assert payload["options"]
    client.close()


def test_session_store_persists_and_reloads_history(monkeypatch, tmp_path):
    from backend.sketchmath.service import SketchMathSessionStore

    client = _client(monkeypatch, tmp_path)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})
    session_id = created.json()["session_id"]

    commit = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/commit",
        json={
            "command": {
                "version": "0.1",
                "command_id": "cmd_slice5_distance",
                "mode": "commit",
                "command_type": "set_distance",
                "selection": ["point_A", "point_B"],
                "parameters": {"distance": 17.5, "unit": "mm", "anchor": "point_A"},
            }
        },
    )
    assert commit.status_code == 200
    assert commit.json()["history_length"] == 1
    client.close()

    fresh_store = SketchMathSessionStore(session_dir=tmp_path)
    reloaded_session = fresh_store.get_session(session_id)
    assert reloaded_session.state.items[1].coords == (17.5, 0.0)
    assert len(reloaded_session.history.records) == 1
    assert fresh_store.snapshot(session_id, reloaded_session)["session_metadata"]["persisted"] is True
