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


def _rectangle_selection_context() -> dict[str, object]:
    return {
        "selection_set_id": "sel_workspace_rectangle",
        "units": "mm",
        "frame": "canvas_2d",
        "items": [
            {"id": "rect_api_a", "type": "point_2d", "coords": [10, 20], "locked": False},
            {"id": "rect_api_b", "type": "point_2d", "coords": [50, 20], "locked": False},
            {"id": "rect_api_c", "type": "point_2d", "coords": [50, 45], "locked": False},
            {"id": "rect_api_d", "type": "point_2d", "coords": [10, 45], "locked": False},
            {"id": "rect_api_ab", "type": "line_2d", "start": [10, 20], "end": [50, 20], "locked": False},
            {"id": "rect_api_bc", "type": "line_2d", "start": [50, 20], "end": [50, 45], "locked": False},
            {"id": "rect_api_cd", "type": "line_2d", "start": [50, 45], "end": [10, 45], "locked": False},
            {"id": "rect_api_da", "type": "line_2d", "start": [10, 45], "end": [10, 20], "locked": False},
            {
                "id": "profile_rect_api",
                "type": "profile_2d",
                "vertices": [[10, 20], [50, 20], [50, 45], [10, 45], [10, 20]],
                "area": 1000.0,
                "winding": "counterclockwise",
                "warnings": [],
                "closed": True,
                "locked": False,
            },
        ],
        "constraints": [],
        "named_references": {},
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


def test_v04_driving_axis_and_circle_dimensions_round_trip_through_api(monkeypatch):
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={
            "selection_context": _selection_context(
                [
                    {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
                    {"id": "point_B", "type": "point_2d", "coords": [2, 3], "locked": False},
                    {"id": "center", "type": "point_2d", "coords": [20, 20], "locked": True},
                    {"id": "circle", "type": "circle_2d", "center": [20, 20], "radius": 2, "center_point_id": "center"},
                ]
            )
        },
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    axis_command = _command(
        "set_horizontal_distance",
        "axis_distance",
        mode="commit",
        selection=["point_A", "point_B"],
        parameters={"distance": 8, "unit": "mm", "anchor": "point_a"},
    )
    axis_command["version"] = "0.4"
    axis = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": axis_command})
    assert axis.status_code == 200
    assert axis.json()["result"]["after"]["items"][1]["coords"] == [8.0, 3.0]
    assert axis.json()["result"]["after"]["constraints"][0]["type"] == "horizontal_distance_constraint"

    diameter_command = _command(
        "set_diameter",
        "circle_diameter",
        mode="commit",
        selection=["circle"],
        parameters={"diameter": 30, "unit": "mm"},
    )
    diameter_command["version"] = "0.4"
    diameter = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": diameter_command})
    assert diameter.status_code == 200
    circle = next(item for item in diameter.json()["result"]["after"]["items"] if item["id"] == "circle")
    assert circle["radius"] == 15.0
    assert diameter.json()["result"]["after"]["constraints"][1]["type"] == "diameter_constraint"

    snapshot = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["history_length"] == 2
    client.close()


def test_sketchmath_rectangle_dimension_preview_and_commit(monkeypatch):
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={"selection_context": _rectangle_selection_context()},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    selection = [
        "rect_api_a",
        "rect_api_b",
        "rect_api_c",
        "rect_api_d",
        "rect_api_ab",
        "rect_api_bc",
        "rect_api_cd",
        "rect_api_da",
        "profile_rect_api",
    ]

    preview = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={
            "command": _command(
                "set_rectangle_dimension",
                "cmd_rect_width_preview",
                selection=selection,
                parameters={"dimension": "width", "value": 60.0, "unit": "mm"},
            )
        },
    )
    assert preview.status_code == 200
    assert preview.json()["result"]["status"] == "preview"
    assert preview.json()["result"]["after"]["items"][2]["coords"] == [70.0, 45.0]
    assert preview.json()["result"]["metadata"]["solver_status"] == "underconstrained"

    current = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert current.status_code == 200
    assert current.json()["selection_context"]["items"][2]["coords"] == [50.0, 45.0]

    commit = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/commit",
        json={
            "command": _command(
                "set_rectangle_dimension",
                "cmd_rect_width_commit",
                mode="commit",
                selection=selection,
                parameters={"dimension": "width", "value": 60.0, "unit": "mm"},
            )
        },
    )
    assert commit.status_code == 200
    assert commit.json()["selection_context"]["items"][2]["coords"] == [70.0, 45.0]
    assert commit.json()["selection_context"]["items"][8]["vertices"] == [[10.0, 20.0], [70.0, 20.0], [70.0, 45.0], [10.0, 45.0], [10.0, 20.0]]
    assert commit.json()["history_length"] == 1
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


def test_sketchmath_feature_flag_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("FRIDAY_SKETCHMATH_ENABLED", raising=False)
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/sketchmath/sessions", json={})

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_disabled"
    client.close()


def test_sketchmath_rejects_undeclared_command_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = _client(monkeypatch)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/commit",
        json={
            "command": {
                "version": "9.9",
                "command_id": "cmd_invalid_contract",
                "mode": "commit",
                "command_type": "not_a_sketchmath_command",
                "selection": [],
                "parameters": {},
            }
        },
    )

    assert response.status_code == 422
    error = response.json()["detail"]["error"]
    assert error["code"] == "invalid_command"
    assert {tuple(item["location"]) for item in error["detail"]["errors"]} == {("version",), ("command_type",)}
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
    preview_mesh = preview.json()["result"]["metadata"]["preview_mesh"]
    assert preview_mesh["profile_id"] == "profile_box"
    assert preview_mesh["depth"] == 7.5
    assert preview_mesh["metadata"]["hole_count"] == 1
    assert any(triangle["surface"] == "hole_wall" for triangle in preview_mesh["triangles"])
    assert preview_mesh["metadata"]["bbox"]["zmax"] == 7.5

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
    assert commit.json()["result"]["metadata"]["preview_mesh"]["metadata"]["hole_count"] == 1
    assert commit.json()["history_length"] == 1
    client.close()


def test_sketchmath_extrude_profile_preview_mesh_changes_after_hole_update(monkeypatch):
    client = _client(monkeypatch)
    context = _profile_selection_context_with_hole()
    created = client.post("/api/sketchmath/sessions", json={"selection_context": context})
    session_id = created.json()["session_id"]

    first = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={
            "command": _command(
                "extrude_profile",
                "cmd_extrude_preview_hole_small",
                selection=["profile_box"],
                parameters={"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step", "holes": ["profile_inner"]},
            )
        },
    )
    assert first.status_code == 200

    updated_context = _profile_selection_context_with_hole()
    for item in updated_context["items"]:
        if isinstance(item, dict) and item.get("id") == "profile_inner":
            item["vertices"] = [[6, 3], [14, 3], [14, 7], [6, 7], [6, 3]]
            item["area"] = 32.0
    second_session = client.post("/api/sketchmath/sessions", json={"selection_context": updated_context})
    second_session_id = second_session.json()["session_id"]
    second = client.post(
        f"/api/sketchmath/sessions/{second_session_id}/commands/preview",
        json={
            "command": _command(
                "extrude_profile",
                "cmd_extrude_preview_hole_large",
                selection=["profile_box"],
                parameters={"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step", "holes": ["profile_inner"]},
            )
        },
    )
    assert second.status_code == 200

    assert first.json()["result"]["metadata"]["preview_mesh"]["vertices"] != second.json()["result"]["metadata"]["preview_mesh"]["vertices"]
    client.close()


def test_sketchmath_extrude_profile_invalid_hole_returns_structured_error(monkeypatch):
    client = _client(monkeypatch)
    context = _profile_selection_context_with_hole()
    for item in context["items"]:
        if isinstance(item, dict) and item.get("id") == "profile_inner":
            item["vertices"] = [[18, 8], [24, 8], [24, 12], [18, 12], [18, 8]]
            item["area"] = 24.0
    created = client.post("/api/sketchmath/sessions", json={"selection_context": context})
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={
            "command": _command(
                "extrude_profile",
                "cmd_extrude_preview_invalid_hole",
                selection=["profile_box"],
                parameters={"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step", "holes": ["profile_inner"]},
            )
        },
    )

    assert response.status_code == 422
    error = response.json()["detail"]["error"]
    assert error["code"] == "selection_resolution_error"
    assert error["detail"]["error_code"] in {"hole_outside_outer", "profile_intersection"}
    client.close()


def test_sketchmath_step_artifact_download_is_browser_reachable(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_CAD_EXPORT_DIR", str(tmp_path))
    client = _client(monkeypatch)
    step_path = tmp_path / "sel_download" / "cmd_export" / "export.step"
    step_path.parent.mkdir(parents=True)
    step_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")

    response = client.get("/api/sketchmath/artifacts/step", params={"path": str(step_path)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("model/step")
    assert response.headers["content-disposition"].endswith('filename="export.step"')
    assert b"ISO-10303-21" in response.content
    client.close()


def test_sketchmath_step_artifact_download_rejects_outside_export_root(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_CAD_EXPORT_DIR", str(tmp_path / "exports"))
    client = _client(monkeypatch)
    outside_path = tmp_path / "outside.step"
    outside_path.write_text("not allowed", encoding="utf-8")

    response = client.get("/api/sketchmath/artifacts/step", params={"path": str(outside_path)})

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "artifact_outside_export_root"
    client.close()
