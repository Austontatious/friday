from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import math
import time

from fastapi.testclient import TestClient
import pytest

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


def _feature_command(
    operation_type: str,
    operation_id: str,
    revision: int,
    *,
    feature: dict[str, object] | None = None,
    target_id: str | None = None,
    mode: str = "preview",
) -> dict[str, object]:
    parameters: dict[str, object] = {}
    if feature is not None:
        parameters["feature"] = feature
    return {
        "version": "1.0",
        "operation_id": operation_id,
        "mode": mode,
        "base_revision": revision,
        "operation_type": operation_type,
        "target_id": target_id,
        "parameters": parameters,
    }


def _extrude_feature(depth: float = 10.0) -> dict[str, object]:
    return {
        "feature_id": "feature_plate",
        "feature_type": "extrude",
        "name": "Plate",
        "body_id": "body_main",
        "sketch_id": "sketch_main",
        "profile_id": "profile_box",
        "source_region_id": None,
        "dependencies": [],
        "parameters": {
            "depth_mm": depth,
            "extent": "one_sided",
            "direction": "positive",
            "operation": "new_body",
        },
        "suppressed": False,
    }


def _topology_loop(prefix: str, minimum: float, maximum: float) -> list[dict[str, object]]:
    return [
        {"id": f"{prefix}_bottom", "type": "line_2d", "start": [minimum, minimum], "end": [maximum, minimum]},
        {"id": f"{prefix}_right", "type": "line_2d", "start": [maximum, minimum], "end": [maximum, maximum]},
        {"id": f"{prefix}_top", "type": "line_2d", "start": [maximum, maximum], "end": [minimum, maximum]},
        {"id": f"{prefix}_left", "type": "line_2d", "start": [minimum, maximum], "end": [minimum, minimum]},
    ]


def test_v09_general_topology_select_promote_and_reload_round_trip(monkeypatch, tmp_path):
    from backend.sketchmath.service import SESSION_STORE

    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={"selection_context": _selection_context([*_topology_loop("outer", 0, 10), *_topology_loop("inner", 3, 7)])},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    detect_command = _command("detect_regions", "detect_regions_v09", parameters={"point": [1, 1]})
    detect_command["version"] = "0.9"
    detected = client.post(f"/api/sketchmath/sessions/{session_id}/commands/preview", json={"command": detect_command})
    assert detected.status_code == 200
    topology = detected.json()["result"]["metadata"]["topology"]
    assert [region["area"] for region in topology["regions"]] == [16.0, 84.0]
    assert topology["selection"]["status"] == "selected"
    assert len(topology["selection"]["region_ids"]) == 1

    promote_command = _command(
        "make_region_profile",
        "promote_region_v09",
        mode="commit",
        parameters={"point": [1, 1], "name": "profile_annulus"},
    )
    promote_command["version"] = "0.9"
    promoted = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": promote_command})
    assert promoted.status_code == 200
    metadata = promoted.json()["result"]["metadata"]
    assert metadata["net_area"] == 84.0
    assert len(metadata["hole_profile_ids"]) == 1
    outer = next(item for item in promoted.json()["selection_context"]["items"] if item["id"] == "profile_annulus")
    assert outer["source_region_id"] == metadata["region_id"]
    assert outer["holes"] == metadata["hole_profile_ids"]

    SESSION_STORE._sessions.clear()
    reloaded = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert reloaded.status_code == 200
    restored_outer = next(item for item in reloaded.json()["selection_context"]["items"] if item["id"] == "profile_annulus")
    assert restored_outer["source_region_id"] == metadata["region_id"]
    assert restored_outer["holes"] == metadata["hole_profile_ids"]
    assert reloaded.json()["history_length"] == 1
    client.close()


def test_session_store_serializes_overlapping_commits_per_session(monkeypatch, tmp_path):
    from backend.sketchmath.service import SketchMathSessionStore

    store = SketchMathSessionStore(session_dir=tmp_path)
    session_id, session = store.create_session({"selection_context": _selection_context()})
    original_execute = session.execute
    counter_lock = Lock()
    active = 0
    maximum_active = 0

    def wrapped_execute(command):  # noqa: ANN001, ANN202
        nonlocal active, maximum_active
        with counter_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            time.sleep(0.02)
            return original_execute(command)
        finally:
            with counter_lock:
                active -= 1

    monkeypatch.setattr(session, "execute", wrapped_execute)
    start = Barrier(2)

    def commit_point(name: str, x: float) -> dict[str, object]:
        start.wait()
        return store.run_command(
            session_id,
            _command("define_point", f"commit_{name}", mode="commit", parameters={"name": name, "coords": [x, 0]}),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda item: commit_point(*item), [("point_a", 1.0), ("point_b", 2.0)]))

    assert maximum_active == 1
    assert sorted(response["history_length"] for response in responses) == [1, 2]
    snapshot = store.snapshot(session_id, session)
    assert snapshot["history_length"] == 2
    assert sorted(item["id"] for item in snapshot["selection_context"]["items"]) == ["point_a", "point_b"]


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

    vertical_command = _command(
        "set_vertical_distance",
        "axis_vertical_distance",
        mode="commit",
        selection=["point_A", "point_B"],
        parameters={"distance": 3, "unit": "mm", "anchor": "point_a"},
    )
    vertical_command["version"] = "0.4"
    vertical = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": vertical_command})
    assert vertical.status_code == 200

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
    assert diameter.json()["result"]["after"]["constraints"][2]["type"] == "diameter_constraint"

    analyze_command = _command("analyze_constraints", "unified_analysis")
    analyze_command["version"] = "0.3"
    analysis = client.post(f"/api/sketchmath/sessions/{session_id}/commands/preview", json={"command": analyze_command})
    assert analysis.status_code == 200
    assert analysis.json()["result"]["metadata"]["solver_run"]["outcome"] == "analyzed"
    assert analysis.json()["result"]["metadata"]["solver_run"]["backend"] == "scipy_least_squares_v1"

    solve = client.post(
        f"/api/sketchmath/sessions/{session_id}/commands/preview",
        json={"command": _command("solve_constraints", "unified_solve_preview")},
    )
    assert solve.status_code == 200
    assert solve.json()["result"]["metadata"]["solver_run"]["outcome"] == "solved"
    assert solve.json()["result"]["metadata"]["solver_run"]["analysis_after"]["coverage"] == "exact"

    snapshot = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["history_length"] == 3
    client.close()


def test_v05_arc_preview_commit_and_disk_reload_round_trip(monkeypatch, tmp_path):
    from backend.sketchmath.service import SESSION_STORE

    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = _client(monkeypatch)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    arc_command = _command(
        "define_arc",
        "arc_api",
        parameters={
            "name": "arc_api",
            "construction": "three_point",
            "start": [0, 0],
            "through": [5, -5],
            "end": [10, 0],
        },
    )
    arc_command["version"] = "0.5"

    preview = client.post(f"/api/sketchmath/sessions/{session_id}/commands/preview", json={"command": arc_command})
    assert preview.status_code == 200
    assert preview.json()["result"]["after"]["items"][0]["type"] == "arc_2d"
    assert client.get(f"/api/sketchmath/sessions/{session_id}").json()["selection_context"]["items"] == []

    arc_command["mode"] = "commit"
    committed = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": arc_command})
    assert committed.status_code == 200
    canonical = committed.json()["selection_context"]["items"][0]
    assert canonical["construction"] == "three_point"
    assert canonical["radius"] == 5.0
    assert committed.json()["history_length"] == 1

    SESSION_STORE._sessions.pop(session_id, None)
    reloaded = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["selection_context"]["items"][0] == canonical
    assert reloaded.json()["history_length"] == 1
    client.close()


def test_arc_entity_upsert_uses_the_canonical_v05_command_path(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = _client(monkeypatch)
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/sketchmath/sessions/{session_id}/entities",
        json={
            "mode": "commit",
            "entity": {
                "id": "arc_imported",
                "type": "arc_2d",
                "center": [10, 10],
                "radius": 4,
                "start_angle_deg": 30,
                "sweep_angle_deg": -120,
                "construction": "center",
            },
        },
    )

    assert response.status_code == 200
    arc = response.json()["selection_context"]["items"][0]
    assert arc["type"] == "arc_2d"
    assert arc["start_angle_deg"] == 30.0
    assert arc["sweep_angle_deg"] == -120.0
    assert response.json()["result"]["command"]["version"] == "0.5"
    client.close()


def test_v06_gate_b_constraints_round_trip_with_typed_solver_analysis(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={
            "selection_context": _selection_context(
                [
                    {"id": "a", "type": "point_2d", "coords": [0, 0], "locked": True},
                    {"id": "b", "type": "point_2d", "coords": [8, 4], "locked": True},
                    {"id": "mid", "type": "point_2d", "coords": [9, 9], "locked": False},
                    {"id": "reference", "type": "circle_2d", "center": [2, 3], "radius": 4},
                    {"id": "target", "type": "circle_2d", "center": [12, 7], "radius": 2},
                ]
            )
        },
    )
    session_id = created.json()["session_id"]
    commands = [
        _command("make_midpoint", "midpoint_api", mode="commit", selection=["mid", "a", "b"]),
        _command("make_concentric", "concentric_api", mode="commit", selection=["reference", "target"]),
    ]
    for command in commands:
        command["version"] = "0.6"
        response = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": command})
        assert response.status_code == 200

    snapshot = client.get(f"/api/sketchmath/sessions/{session_id}").json()
    assert next(item for item in snapshot["selection_context"]["items"] if item["id"] == "mid")["coords"] == [4.0, 2.0]
    assert next(item for item in snapshot["selection_context"]["items"] if item["id"] == "target")["center"] == [2.0, 3.0]
    assert [constraint["type"] for constraint in snapshot["selection_context"]["constraints"]] == ["midpoint_constraint", "concentric_constraint"]

    analysis_command = _command("analyze_constraints", "analyze_v06")
    analysis_command["version"] = "0.3"
    analysis = client.post(f"/api/sketchmath/sessions/{session_id}/commands/preview", json={"command": analysis_command})
    assert analysis.status_code == 200
    payload = analysis.json()["result"]["metadata"]["solver_analysis"]
    assert payload["coverage"] == "exact"
    assert payload["supported_constraint_ids"] == ["constraint_concentric_api", "constraint_midpoint_api"]
    client.close()


def test_v07_construction_conversion_round_trips_with_stable_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = _client(monkeypatch)
    created = client.post(
        "/api/sketchmath/sessions",
        json={
            "selection_context": _selection_context(
                [
                    {"id": "guide", "type": "point_2d", "coords": [0, 0]},
                    {"id": "centerline", "type": "line_2d", "start": [0, 0], "end": [10, 0], "start_point_id": "guide"},
                ]
            )
        },
    )
    session_id = created.json()["session_id"]
    command = _command("set_construction", "construction_api", mode="commit", selection=["guide", "centerline"])
    command["version"] = "0.7"
    command["parameters"] = {"enabled": True}
    response = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": command})
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["selection_context"]["items"]}
    assert items["guide"]["construction"] is True
    assert items["centerline"]["type"] == "construction_line_2d"

    reloaded = client.get(f"/api/sketchmath/sessions/{session_id}").json()
    reloaded_items = {item["id"]: item for item in reloaded["selection_context"]["items"]}
    assert reloaded_items["guide"]["construction"] is True
    assert reloaded_items["centerline"]["type"] == "construction_line_2d"
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


def test_sketchmath_document_v1_defaults_off_and_gates_feature_routes(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "0")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})

    assert created.status_code == 200
    assert "document" not in created.json()
    response = client.post(
        f"/api/sketchmath/sessions/{created.json()['session_id']}/features/preview",
        json={"command": _feature_command("rebuild", "rebuild_disabled", 0)},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_document_v1_disabled"
    client.close()


def test_sketchmath_artifact_jobs_default_off_and_gate_build_route(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.delenv("FRIDAY_SKETCHMATH_ARTIFACT_JOBS_ENABLED", raising=False)
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={})

    response = client.post(
        f"/api/sketchmath/sessions/{created.json()['session_id']}/artifacts/build",
        json={"feature_id": "feature_missing", "format": "stl", "base_revision": 0},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_artifact_jobs_disabled"
    client.close()


def test_sketchmath_hole_features_default_off_and_gate_feature_route(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.delenv("FRIDAY_SKETCHMATH_HOLE_FEATURES_ENABLED", raising=False)
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={})
    hole = {
        "feature_id": "feature_gated_hole",
        "feature_type": "hole",
        "name": "Gated hole",
        "body_id": "body_main",
        "sketch_id": "sketch_main",
        "dependencies": ["feature_missing"],
        "topology_references": [],
        "parameters": {
            "style": "simple",
            "termination": "through",
            "position_mm": [0, 0],
            "diameter_mm": 4,
            "operation": "cut",
        },
    }

    response = client.post(
        f"/api/sketchmath/sessions/{created.json()['session_id']}/features/preview",
        json={"command": _feature_command("add_feature", "gated_hole", 0, feature=hole)},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_hole_features_disabled"
    client.close()


def test_sketchmath_revolve_features_default_off_and_gate_feature_route(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.delenv("FRIDAY_SKETCHMATH_REVOLVE_FEATURES_ENABLED", raising=False)
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={})
    revolve = {
        "feature_id": "feature_gated_revolve",
        "feature_type": "revolve",
        "name": "Gated revolve",
        "body_id": "body_main",
        "sketch_id": "sketch_main",
        "profile_id": "profile_missing",
        "parameters": {"axis_entity_id": "axis_missing", "angle_deg": 360, "operation": "new_body"},
    }

    response = client.post(
        f"/api/sketchmath/sessions/{created.json()['session_id']}/features/preview",
        json={"command": _feature_command("add_feature", "gated_revolve", 0, feature=revolve)},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_revolve_features_disabled"
    client.close()


def test_sketchmath_fillet_features_default_off_and_gate_feature_route(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.delenv("FRIDAY_SKETCHMATH_FILLET_FEATURES_ENABLED", raising=False)
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={})
    fillet = {
        "feature_id": "feature_gated_fillet",
        "feature_type": "fillet",
        "name": "Gated fillet",
        "body_id": "body_main",
        "sketch_id": "sketch_main",
        "profile_id": None,
        "dependencies": ["feature_missing"],
        "topology_references": [],
        "parameters": {"radius_mm": 2, "operation": "modify"},
    }

    response = client.post(
        f"/api/sketchmath/sessions/{created.json()['session_id']}/features/preview",
        json={"command": _feature_command("add_feature", "gated_fillet", 0, feature=fillet)},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_fillet_features_disabled"
    client.close()


def test_sketchmath_chamfer_features_default_off_and_gate_feature_route(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.delenv("FRIDAY_SKETCHMATH_CHAMFER_FEATURES_ENABLED", raising=False)
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={})
    chamfer = {
        "feature_id": "feature_gated_chamfer",
        "feature_type": "chamfer",
        "name": "Gated chamfer",
        "body_id": "body_main",
        "sketch_id": "sketch_main",
        "profile_id": None,
        "dependencies": ["feature_missing"],
        "topology_references": [],
        "parameters": {"distance_mm": 2, "operation": "modify"},
    }

    response = client.post(
        f"/api/sketchmath/sessions/{created.json()['session_id']}/features/preview",
        json={"command": _feature_command("add_feature", "gated_chamfer", 0, feature=chamfer)},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "sketchmath_chamfer_features_disabled"
    client.close()


def test_sketchmath_artifact_job_build_poll_register_download_and_replay(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ARTIFACT_JOBS_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ARTIFACT_JOB_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("FRIDAY_SKETCHMATH_CAD_EXPORT_DIR", str(tmp_path / "cad"))
    client = TestClient(create_app())
    selection = _profile_selection_context_with_hole()
    selection["items"][0]["holes"] = ["profile_inner"]
    created = client.post("/api/sketchmath/sessions", json={"selection_context": selection})
    session_id = created.json()["session_id"]
    committed = client.post(
        f"/api/sketchmath/sessions/{session_id}/features/commit",
        json={"command": _feature_command("add_feature", "add_artifact_plate", 0, feature=_extrude_feature(), mode="commit")},
    )
    assert committed.status_code == 200

    request = {"feature_id": "feature_plate", "format": "stl", "base_revision": 1}
    submitted = client.post(f"/api/sketchmath/sessions/{session_id}/artifacts/build", json=request)
    assert submitted.status_code == 202
    job_id = submitted.json()["job_id"]
    job = submitted.json()
    for _ in range(100):
        polled = client.get(f"/api/sketchmath/sessions/{session_id}/artifacts/jobs/{job_id}")
        assert polled.status_code == 200
        job = polled.json()
        if job["state"] in {"DONE", "FAILED"}:
            break
        time.sleep(0.02)

    assert job["state"] == "DONE", job
    assert job["input_revision"] == 1
    assert job["result"]["measurements"]["volume_mm3"] == 1280.0
    artifact = job["result"]["artifact"]
    assert artifact["revision"] == 1
    snapshot = client.get(f"/api/sketchmath/sessions/{session_id}").json()
    assert snapshot["document"]["revision"] == 1
    assert snapshot["document"]["artifacts"] == [artifact]

    download = client.get("/api/sketchmath/artifacts/stl", params={"path": artifact["path"]})
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("model/stl")
    assert download.content.startswith(b"solid feature_plate\n")

    replay = client.post(f"/api/sketchmath/sessions/{session_id}/artifacts/build", json=request)
    assert replay.status_code == 202
    assert replay.json()["job_id"] == job_id
    assert replay.json()["state"] == "DONE"
    client.close()


def test_sketchmath_feature_history_preview_commit_reload_conflict_and_undo_redo(monkeypatch, tmp_path):
    from backend.sketchmath.service import SESSION_STORE

    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    selection = _profile_selection_context_with_hole()
    selection["items"][0]["holes"] = ["profile_inner"]
    created = client.post("/api/sketchmath/sessions", json={"selection_context": selection})

    assert created.status_code == 200
    session_id = created.json()["session_id"]
    assert created.json()["document"]["revision"] == 0
    assert created.json()["document"]["sketches"][0]["state"]["items"][0]["id"] == "profile_box"

    add = _feature_command("add_feature", "add_plate", 0, feature=_extrude_feature(), mode="commit")
    preview = client.post(f"/api/sketchmath/sessions/{session_id}/features/preview", json={"command": add})
    assert preview.status_code == 200
    assert preview.json()["result"]["status"] == "preview"
    assert preview.json()["result"]["after"]["revision"] == 1
    assert preview.json()["document"]["revision"] == 0
    assert preview.json()["feature_history_length"] == 0

    committed = client.post(f"/api/sketchmath/sessions/{session_id}/features/commit", json={"command": add})
    assert committed.status_code == 200
    committed_payload = committed.json()
    assert committed_payload["document"]["revision"] == 1
    assert committed_payload["history_length"] == 0
    assert committed_payload["feature_history_length"] == 1
    assert committed_payload["document"]["bodies"][0]["feature_ids"] == ["feature_plate"]
    measurements = committed_payload["document"]["last_rebuild"]["records"][0]["measurements"]
    assert measurements["net_profile_area_mm2"] == 128.0
    assert measurements["volume_delta_mm3"] == 1280.0

    SESSION_STORE._sessions.pop(session_id, None)
    reloaded = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["document"]["features"][0]["feature_id"] == "feature_plate"
    assert reloaded.json()["feature_history_length"] == 1

    stale = _feature_command(
        "replace_feature",
        "replace_stale",
        0,
        feature=_extrude_feature(25.0),
        target_id="feature_plate",
        mode="commit",
    )
    conflict = client.post(f"/api/sketchmath/sessions/{session_id}/features/commit", json={"command": stale})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"]["code"] == "revision_conflict"
    assert conflict.json()["detail"]["error"]["detail"]["current_revision"] == 1

    replacement = {**stale, "operation_id": "replace_depth", "base_revision": 1}
    replaced = client.post(f"/api/sketchmath/sessions/{session_id}/features/commit", json={"command": replacement})
    assert replaced.status_code == 200
    assert replaced.json()["document"]["revision"] == 2
    assert replaced.json()["document"]["features"][0]["parameters"]["depth_mm"] == 25.0
    replacement_signature = replaced.json()["document"]["last_rebuild"]["records"][0]["output_signature"]

    reverted = client.post(f"/api/sketchmath/sessions/{session_id}/features/revert")
    assert reverted.status_code == 200
    assert reverted.json()["document"]["revision"] == 3
    assert reverted.json()["document"]["features"][0]["parameters"]["depth_mm"] == 10.0
    assert reverted.json()["can_feature_redo"] is True

    redone = client.post(f"/api/sketchmath/sessions/{session_id}/features/redo")
    assert redone.status_code == 200
    assert redone.json()["document"]["revision"] == 4
    assert redone.json()["document"]["features"][0]["parameters"]["depth_mm"] == 25.0
    assert redone.json()["document"]["last_rebuild"]["records"][0]["output_signature"] == replacement_signature

    point_command = _command(
        "define_point",
        "feature_history_point",
        mode="commit",
        parameters={"name": "inspection_point", "coords": [30, 30]},
    )
    point_added = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": point_command})
    assert point_added.status_code == 200, point_added.text
    assert point_added.json()["document"]["revision"] == 5

    undo_after_sketch_edit = client.post(f"/api/sketchmath/sessions/{session_id}/features/revert")
    assert undo_after_sketch_edit.status_code == 200
    assert undo_after_sketch_edit.json()["document"]["revision"] == 6
    assert undo_after_sketch_edit.json()["document"]["features"][0]["parameters"]["depth_mm"] == 10.0
    assert any(
        item["id"] == "inspection_point"
        for item in undo_after_sketch_edit.json()["document"]["sketches"][0]["state"]["items"]
    )

    redo_after_sketch_edit = client.post(f"/api/sketchmath/sessions/{session_id}/features/redo")
    assert redo_after_sketch_edit.status_code == 200
    assert redo_after_sketch_edit.json()["document"]["revision"] == 7
    assert redo_after_sketch_edit.json()["document"]["features"][0]["parameters"]["depth_mm"] == 25.0
    assert any(
        item["id"] == "inspection_point"
        for item in redo_after_sketch_edit.json()["document"]["sketches"][0]["state"]["items"]
    )

    invalidating_delete = _command(
        "delete_entity",
        "delete_feature_source",
        mode="commit",
        selection=["profile_box"],
        parameters={"cascade": True},
    )
    refused = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": invalidating_delete})
    assert refused.status_code == 409
    error = refused.json()["detail"]["error"]
    assert error["code"] == "feature_rebuild_error"
    assert error["detail"]["error_code"] == "feature_reference_invalidated"
    after_refusal = client.get(f"/api/sketchmath/sessions/{session_id}").json()
    assert after_refusal["document"]["revision"] == 7
    assert after_refusal["history_length"] == 1
    assert any(item["id"] == "profile_box" for item in after_refusal["selection_context"]["items"])
    client.close()


def test_sketchmath_typed_hole_feature_recovers_top_face_after_base_edit_and_reload(monkeypatch, tmp_path):
    from backend.sketchmath.service import SESSION_STORE

    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_HOLE_FEATURES_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _profile_selection_context()})
    session_id = created.json()["session_id"]
    base = _extrude_feature(10)
    base_response = client.post(
        f"/api/sketchmath/sessions/{session_id}/features/commit",
        json={"command": _feature_command("add_feature", "add_hole_base", 0, feature=base, mode="commit")},
    )
    assert base_response.status_code == 200
    top = next(
        item
        for item in base_response.json()["document"]["last_rebuild"]["records"][0]["generated_topology"]
        if item["role"] == "top"
    )
    hole = {
        "feature_id": "feature_mount_hole",
        "feature_type": "hole",
        "name": "Mount hole",
        "body_id": "body_main",
        "sketch_id": "sketch_main",
        "dependencies": ["feature_plate"],
        "topology_references": [
            {
                "reference_id": top["reference_id"],
                "owner_feature_id": "feature_plate",
                "topology_type": "face",
                "role": "top",
                "source_entity_id": "profile_box",
                "expected_signature": top["geometric_signature"],
            }
        ],
        "parameters": {
            "style": "simple",
            "termination": "through",
            "position_mm": [10, 5],
            "diameter_mm": 4,
            "operation": "cut",
        },
    }
    hole_response = client.post(
        f"/api/sketchmath/sessions/{session_id}/features/commit",
        json={"command": _feature_command("add_feature", "add_mount_hole", 1, feature=hole, mode="commit")},
    )
    assert hole_response.status_code == 200, hole_response.text
    hole_record = hole_response.json()["document"]["last_rebuild"]["records"][1]
    assert hole_record["measurements"]["volume_delta_mm3"] == pytest.approx(-40 * math.pi)
    assert hole_record["resolved_references"][0]["recovery_state"] == "exact"

    edited_base = _extrude_feature(20)
    edited_response = client.post(
        f"/api/sketchmath/sessions/{session_id}/features/commit",
        json={
            "command": _feature_command(
                "replace_feature",
                "edit_hole_base_depth",
                2,
                feature=edited_base,
                target_id="feature_plate",
                mode="commit",
            )
        },
    )
    assert edited_response.status_code == 200, edited_response.text
    edited_hole_record = edited_response.json()["document"]["last_rebuild"]["records"][1]
    assert edited_hole_record["measurements"]["volume_delta_mm3"] == pytest.approx(-80 * math.pi)
    assert edited_hole_record["resolved_references"][0]["recovery_state"] == "recovered"

    SESSION_STORE._sessions.pop(session_id, None)
    reloaded = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert reloaded.status_code == 200
    assert [feature["feature_type"] for feature in reloaded.json()["document"]["features"]] == ["extrude", "hole"]
    assert reloaded.json()["document"]["revision"] == 3
    client.close()


def test_sketchmath_full_revolve_commits_with_explicit_axis_and_reloads(monkeypatch, tmp_path):
    from backend.sketchmath.service import SESSION_STORE

    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_REVOLVE_FEATURES_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    selection = _profile_selection_context()
    selection["items"].append(
        {"id": "axis_y", "type": "axis_2d", "origin": [0, 0], "direction": [0, 1]}
    )
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={"selection_context": selection})
    session_id = created.json()["session_id"]
    revolve = {
        "feature_id": "feature_revolve",
        "feature_type": "revolve",
        "name": "Full revolve",
        "body_id": "body_main",
        "sketch_id": "sketch_main",
        "profile_id": "profile_box",
        "parameters": {"axis_entity_id": "axis_y", "angle_deg": 360, "operation": "new_body"},
    }

    committed = client.post(
        f"/api/sketchmath/sessions/{session_id}/features/commit",
        json={"command": _feature_command("add_feature", "add_revolve", 0, feature=revolve, mode="commit")},
    )

    assert committed.status_code == 200, committed.text
    record = committed.json()["document"]["last_rebuild"]["records"][0]
    assert record["measurements"]["volume_delta_mm3"] == pytest.approx(4000 * math.pi)
    assert record["measurements"]["bounds_mm"] == pytest.approx([-20, 20, 0, 10, -20, 20])
    assert record["generated_topology"][0]["role"] == "revolved_outer_face"
    SESSION_STORE._sessions.pop(session_id, None)
    reloaded = client.get(f"/api/sketchmath/sessions/{session_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["document"]["features"][0]["parameters"]["axis_entity_id"] == "axis_y"
    client.close()


def test_geometry_commit_syncs_document_sketch_and_revision(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_SKETCHMATH_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_SESSION_DIR", str(tmp_path / "sessions"))
    client = TestClient(create_app())
    created = client.post("/api/sketchmath/sessions", json={"selection_context": _selection_context()})
    session_id = created.json()["session_id"]
    command = _command("define_point", "point_document_sync", mode="commit", parameters={"name": "origin", "coords": [0, 0]})

    response = client.post(f"/api/sketchmath/sessions/{session_id}/commands/commit", json={"command": command})

    assert response.status_code == 200
    assert response.json()["document"]["revision"] == 1
    assert response.json()["document"]["sketches"][0]["state"] == response.json()["selection_context"]
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
