from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import create_app


def _client(monkeypatch) -> TestClient:  # noqa: ANN001
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    app = create_app()
    return TestClient(app)


def _selection_context(items: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "selection_set_id": "sel_workspace",
        "units": "mm",
        "frame": "canvas_2d",
        "items": items or [],
        "constraints": [],
        "named_references": {},
    }


def _profile_selection_context() -> dict[str, object]:
    return {
        "selection_set_id": "sel_workspace_profile",
        "units": "mm",
        "frame": "canvas_2d",
        "items": [
            {
                "id": "profile_box",
                "type": "profile_2d",
                "vertices": [[0, 0], [20, 0], [20, 10], [0, 10], [0, 0]],
                "area": 200.0,
                "winding": "counterclockwise",
                "warnings": [],
                "closed": True,
                "locked": False,
                "label": "box",
            }
        ],
        "constraints": [],
        "named_references": {"box": "profile_box"},
    }


def _profile_selection_context_with_hole() -> dict[str, object]:
    return {
        "selection_set_id": "sel_workspace_profile_holes",
        "units": "mm",
        "frame": "canvas_2d",
        "items": [
            {
                "id": "profile_box",
                "type": "profile_2d",
                "vertices": [[0, 0], [20, 0], [20, 10], [0, 10], [0, 0]],
                "area": 200.0,
                "winding": "counterclockwise",
                "warnings": [],
                "closed": True,
                "locked": False,
                "label": "box",
            },
            {
                "id": "profile_inner",
                "type": "profile_2d",
                "vertices": [[4, 2], [16, 2], [16, 8], [4, 8], [4, 2]],
                "area": 72.0,
                "winding": "clockwise",
                "warnings": [],
                "closed": True,
                "locked": False,
                "label": "inner",
            },
        ],
        "constraints": [],
        "named_references": {"box": "profile_box", "inner": "profile_inner"},
    }


def _command(command_type: str, command_id: str, *, mode: str = "preview", selection: list[str] | None = None, parameters: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "version": "0.1",
        "command_id": command_id,
        "mode": mode,
        "command_type": command_type,
        "selection": selection or [],
        "parameters": parameters or {},
    }


def test_sketchmath_session_preview_commit_and_revert(monkeypatch):
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={
            "selection_context": _selection_context(
                [
                    {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
                    {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False},
                ]
            )
        },
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    preview = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={
            "command": _command(
                "set_distance",
                "cmd_preview",
                selection=["point_A", "point_B"],
                parameters={"distance": 8.0, "unit": "mm", "anchor": "point_A"},
            )
        },
    )
    assert preview.status_code == 200
    assert preview.json()["result"]["status"] == "preview"
    assert preview.json()["result"]["after"]["items"][1]["coords"] == [8.0, 0.0]

    current = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert current.status_code == 200
    assert current.json()["selection_context"]["items"][1]["coords"] == [1.0, 0.0]
    assert current.json()["history_length"] == 0

    commit = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/commit",
        json={
            "command": _command(
                "set_distance",
                "cmd_commit",
                mode="commit",
                selection=["point_A", "point_B"],
                parameters={"distance": 8.0, "unit": "mm", "anchor": "point_A"},
            )
        },
    )
    assert commit.status_code == 200
    assert commit.json()["result"]["status"] == "committed"
    assert commit.json()["history_length"] == 1

    history = client.get(f"/api/sketchmath/sessions/{session_id}/history")
    assert history.status_code == 200
    assert history.json()["history_length"] == 1
    assert history.json()["history"][0]["command"]["command_type"] == "set_distance"

    reverted = client.post(f"/api/sketchmath/sessions/{session_id}/revert")
    assert reverted.status_code == 200
    assert reverted.json()["selection_context"]["items"][1]["coords"] == [1.0, 0.0]
    assert reverted.json()["history_length"] == 0
    client.close()


def test_sketchmath_entity_upsert_accepts_profile_updates(monkeypatch):
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={"selection_context": _profile_selection_context()},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    update = client.post(
        f"/api/sketchmath/sessions/{session_id}/entities",
        json={
            "mode": "commit",
            "entity": {
                "id": "profile_box",
                "type": "profile_2d",
                "vertices": [[0, 0], [40, 0], [40, 25], [0, 25]],
                "area": 1000.0,
                "winding": "counterclockwise",
                "warnings": [],
                "closed": True,
                "locked": False,
                "label": "box",
            },
        },
    )

    assert update.status_code == 200
    payload = update.json()
    assert payload["result"]["command"]["command_type"] == "define_profile"
    assert payload["result"]["changed_entity_ids"] == ["profile_box"]
    assert payload["selection_context"]["items"][0]["vertices"] == [[0.0, 0.0], [40.0, 0.0], [40.0, 25.0], [0.0, 25.0]]
    assert payload["history_length"] == 1

    history = client.get(f"/api/sketchmath/sessions/{session_id}/history")
    assert history.status_code == 200
    assert history.json()["history_length"] == 1
    assert history.json()["history"][0]["command"]["command_type"] == "define_profile"

    reverted = client.post(f"/api/sketchmath/sessions/{session_id}/revert")
    assert reverted.status_code == 200
    assert reverted.json()["selection_context"]["items"][0]["vertices"] == [[0.0, 0.0], [20.0, 0.0], [20.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
    assert reverted.json()["history_length"] == 0
    client.close()


def test_sketchmath_batch_preview_commit_and_replay(monkeypatch):
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={"selection_context": _selection_context([{"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False}])},
    )
    session_id = created.json()["session_id"]

    batch_preview = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={
            "command": _command(
                "batch",
                "cmd_batch_preview",
                parameters={
                    "commands": [
                        _command("define_point", "cmd_point", parameters={"name": "point_B", "coords": [2, 0]}),
                        _command("translate", "cmd_translate", selection=["point_A"], parameters={"vector": [1, 0]}),
                    ]
                },
            )
        },
    )
    assert batch_preview.status_code == 200
    assert batch_preview.json()["result"]["status"] == "preview"
    assert client.get(f"/api/sketchmath/sessions/{session_id}").json()["selection_context"]["items"][0]["coords"] == [0.0, 0.0]

    batch_commit = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/commit",
        json={
            "command": _command(
                "batch",
                "cmd_batch_commit",
                mode="commit",
                parameters={
                    "commands": [
                        _command("define_point", "cmd_point", parameters={"name": "point_B", "coords": [2, 0]}),
                        _command("translate", "cmd_translate", selection=["point_A"], parameters={"vector": [1, 0]}),
                    ]
                },
            )
        },
    )
    assert batch_commit.status_code == 200
    assert batch_commit.json()["history_length"] == 1
    assert batch_commit.json()["selection_context"]["items"][0]["coords"] == [1.0, 0.0]
    assert any(item["id"] == "point_B" for item in batch_commit.json()["selection_context"]["items"])

    replay = client.get(f"/api/sketchmath/sessions/{session_id}/history")
    assert replay.status_code == 200
    assert replay.json()["history_length"] == 1

    reverted = client.post(f"/api/sketchmath/sessions/{session_id}/revert")
    assert reverted.status_code == 200
    assert reverted.json()["selection_context"]["items"][0]["coords"] == [0.0, 0.0]
    assert reverted.json()["history_length"] == 0
    client.close()


def test_sketchmath_feature_flag_disables_routes(monkeypatch):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "0")
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/sketchmath/sessions", json={})
    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_disabled"
    client.close()


def test_sketchmath_extrude_profile_preview_commit(monkeypatch):
    client = _client(monkeypatch)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _profile_selection_context()})
    session_id = created.json()["session_id"]

    preview = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={
            "command": _command(
                "extrude_profile",
                "cmd_extrude_preview",
                selection=["profile_box"],
                parameters={"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step"},
            )
        },
    )
    assert preview.status_code == 200
    assert preview.json()["result"]["metadata"]["cad_export"]["status"] == "export_ready"

    commit = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/commit",
        json={
            "command": _command(
                "extrude_profile",
                "cmd_extrude_commit",
                mode="commit",
                selection=["profile_box"],
                parameters={"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step"},
            )
        },
    )
    assert commit.status_code == 200
    assert commit.json()["result"]["metadata"]["cad_export"]["artifacts"]["step_path"].endswith("export.step")
    assert commit.json()["history_length"] == 1
    client.close()


def test_sketchmath_extrude_profile_with_holes_preview_commit(monkeypatch):
    client = _client(monkeypatch)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _profile_selection_context_with_hole()})
    session_id = created.json()["session_id"]

    preview = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={
            "command": _command(
                "extrude_profile",
                "cmd_extrude_preview_holes",
                selection=["profile_box"],
                parameters={
                    "depth": 7.5,
                    "depth_unit": "mm",
                    "direction": "positive_normal",
                    "output_format": "step",
                    "holes": ["profile_inner"],
                },
            )
        },
    )
    assert preview.status_code == 200
    assert preview.json()["result"]["metadata"]["cad_export"]["metadata"]["adapter_strategy"] in {"face_with_holes", "boolean_subtraction"}
    assert preview.json()["result"]["metadata"]["profile_hole_validation"]["ok"] is True

    commit = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/commit",
        json={
            "command": _command(
                "extrude_profile",
                "cmd_extrude_commit_holes",
                mode="commit",
                selection=["profile_box"],
                parameters={
                    "depth": 7.5,
                    "depth_unit": "mm",
                    "direction": "positive_normal",
                    "output_format": "step",
                    "holes": ["profile_inner"],
                },
            )
        },
    )
    assert commit.status_code == 200
    assert commit.json()["result"]["metadata"]["cad_export"]["metadata"]["hole_count"] == 1
    assert commit.json()["history_length"] == 1
    client.close()
