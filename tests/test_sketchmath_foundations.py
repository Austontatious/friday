from __future__ import annotations

import pytest

from sketchmath.executor.command_router import GeometrySession
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext


def command(command_type: str, command_id: str, *, selection: list[str] | None = None, parameters: dict | None = None, mode: str = "commit", version: str = "0.2") -> GeometryCommand:
    return GeometryCommand(
        version=version,
        command_id=command_id,
        mode=mode,
        command_type=command_type,
        selection=selection or [],
        parameters=parameters or {},
    )


def session(items: list[dict], constraints: list[dict] | None = None) -> GeometrySession:
    return GeometrySession(
        SelectionContext.model_validate(
            {
                "selection_set_id": "foundations",
                "units": "mm",
                "frame": "canvas_2d",
                "items": items,
                "constraints": constraints or [],
                "named_references": {},
            }
        )
    )


def point(point_id: str, x: float, y: float, *, locked: bool = False) -> dict:
    return {"id": point_id, "type": "point_2d", "coords": [x, y], "locked": locked}


def line(line_id: str, a: str, b: str, start: tuple[float, float], end: tuple[float, float], *, construction: bool = False) -> dict:
    return {
        "id": line_id,
        "type": "construction_line_2d" if construction else "line_2d",
        "start": start,
        "end": end,
        "start_point_id": a,
        "end_point_id": b,
    }


def test_horizontal_vertical_and_coincident_constraints_are_persistent() -> None:
    sketch = session([point("a", 0, 0), point("b", 3, 2), point("c", 8, 4)])
    sketch.execute(command("make_horizontal", "horizontal", selection=["a", "b"]))
    sketch.execute(command("make_vertical", "vertical", selection=["b", "c"]))
    sketch.execute(command("make_coincident", "coincident", selection=["a", "c"]))

    assert [constraint.type for constraint in sketch.state.constraints] == [
        "horizontal_constraint",
        "vertical_constraint",
        "coincident_constraint",
    ]
    assert next(item for item in sketch.state.items if item.id == "c").coords == (0.0, 0.0)


def test_axis_constraint_updates_linked_line_geometry() -> None:
    sketch = session([point("a", 0, 1), point("b", 4, 3), line("edge", "a", "b", (0, 1), (4, 3))])
    result = sketch.execute(command("make_horizontal", "horizontal", selection=["edge"]))
    edge = next(item for item in result.after.items if item.id == "edge")
    assert edge.end == (4.0, 1.0)


def test_conflicting_locked_coincidence_is_typed() -> None:
    sketch = session([point("a", 0, 0, locked=True), point("b", 1, 1, locked=True)])
    with pytest.raises(Exception) as error:
        sketch.execute(command("make_coincident", "bad", selection=["a", "b"]))
    assert error.value.to_dict()["code"] == "solver_error"


def test_detect_profiles_finds_stable_reversed_square() -> None:
    items = [point("a", 0, 0), point("b", 4, 0), point("c", 4, 3), point("d", 0, 3)]
    items += [
        line("ab", "a", "b", (0, 0), (4, 0)),
        line("bc", "c", "b", (4, 3), (4, 0)),
        line("cd", "c", "d", (4, 3), (0, 3)),
        line("da", "a", "d", (0, 0), (0, 3)),
    ]
    sketch = session(items)
    first = sketch.execute(command("detect_profiles", "detect_1", mode="preview")).metadata["profile_candidates"]
    second = sketch.execute(command("detect_profiles", "detect_2", mode="preview")).metadata["profile_candidates"]
    assert first == second
    assert len(first) == 1
    assert first[0]["valid"] is True
    assert first[0]["area"] == pytest.approx(12.0)


def test_profile_promotion_accepts_detected_order_with_reversed_first_edge() -> None:
    sketch = session(
        [
            line("a", "a0", "a1", (0, 0), (10, 0)),
            line("d", "d0", "d1", (0, 10), (0, 0)),
            line("c", "c0", "c1", (10, 10), (0, 10)),
            line("b", "b0", "b1", (10, 0), (10, 10)),
        ]
    )

    result = sketch.execute(command("make_profile", "promote", selection=["a", "d", "c", "b"], parameters={"name": "profile_square"}))

    profile = result.after.get_entity("profile_square")
    assert profile.type == "profile_2d"
    assert profile.closed is True
    assert profile.area == pytest.approx(100.0)


def test_detect_profiles_handles_disconnected_loops_and_excludes_open_or_branched_components() -> None:
    items: list[dict] = []
    for prefix, offset in (("a", 0), ("b", 10)):
        ids = [f"{prefix}{index}" for index in range(4)]
        coords = [(offset, 0), (offset + 2, 0), (offset + 2, 2), (offset, 2)]
        items.extend(point(entity_id, *coord) for entity_id, coord in zip(ids, coords, strict=True))
        items.extend(
            line(f"{prefix}line{index}", ids[index], ids[(index + 1) % 4], coords[index], coords[(index + 1) % 4])
            for index in range(4)
        )
    sketch = session(items)
    candidates = sketch.execute(command("detect_profiles", "detect", mode="preview")).metadata["profile_candidates"]
    assert len(candidates) == 2

    branched = session(items + [point("branch", -1, 0), line("branch_line", "a0", "branch", (0, 0), (-1, 0))])
    branched_candidates = branched.execute(command("detect_profiles", "branch", mode="preview")).metadata["profile_candidates"]
    assert len(branched_candidates) == 1


def test_construction_lines_are_excluded_and_near_points_do_not_close() -> None:
    items = [point("a", 0, 0), point("b", 2, 0), point("c", 1, 2), point("near", 0.001, 0)]
    items += [
        line("ab", "a", "b", (0, 0), (2, 0)),
        line("bc", "b", "c", (2, 0), (1, 2)),
        line("ca", "c", "near", (1, 2), (0.001, 0)),
        line("construction", "a", "c", (0, 0), (1, 2), construction=True),
    ]
    candidates = session(items).execute(command("detect_profiles", "detect", mode="preview")).metadata["profile_candidates"]
    assert candidates == []


def test_coincident_constraint_closes_profile_without_merging_ids() -> None:
    items = [point("a", 0, 0), point("b", 2, 0), point("c", 1, 2), point("near", 0.1, 0)]
    items += [line("ab", "a", "b", (0, 0), (2, 0)), line("bc", "b", "c", (2, 0), (1, 2)), line("ca", "c", "near", (1, 2), (0.1, 0))]
    sketch = session(items)
    sketch.execute(command("make_coincident", "close", selection=["a", "near"]))
    candidates = sketch.execute(command("detect_profiles", "detect", mode="preview")).metadata["profile_candidates"]
    assert len(candidates) == 1
    assert {item.id for item in sketch.state.items if item.type == "point_2d"} == {"a", "b", "c", "near"}


def test_circle_can_be_edited_and_adapted_to_extrusion_profile() -> None:
    sketch = session([])
    sketch.execute(command("define_circle", "circle", parameters={"name": "circle_1", "center": [5, 6], "radius": 3}))
    sketch.execute(command("update_circle", "resize", selection=["circle_1"], parameters={"radius": 4}))
    result = sketch.execute(command("make_circle_profile", "profile", selection=["circle_1"]))
    circle = next(item for item in sketch.state.items if item.id == "circle_1")
    profile = next(item for item in sketch.state.items if item.id == "profile_circle_1")
    assert circle.radius == 4
    assert profile.area == pytest.approx(3.141592653589793 * 16, rel=0.01)
    assert result.metadata["source_circle_id"] == "circle_1"


def test_center_arc_is_canonical_and_replayable() -> None:
    sketch = session([])
    result = sketch.execute(
        command(
            "define_arc",
            "arc",
            version="0.5",
            parameters={
                "name": "arc_1",
                "construction": "center",
                "center": [0, 0],
                "start": [5, 0],
                "end": [0, 5],
                "direction": "clockwise",
            },
        )
    )

    arc = result.after.get_entity("arc_1")
    assert arc.type == "arc_2d"
    assert arc.radius == pytest.approx(5.0)
    assert arc.start_angle_deg == pytest.approx(0.0)
    assert arc.sweep_angle_deg == pytest.approx(90.0)
    sketch.revert()
    assert sketch.state.items == []
    sketch.redo()
    assert sketch.state.get_entity("arc_1").model_dump() == arc.model_dump()


def test_three_point_arc_selects_the_sweep_through_the_middle_point() -> None:
    sketch = session([])
    sketch.execute(
        command(
            "define_arc",
            "arc_three",
            version="0.5",
            parameters={
                "name": "arc_three",
                "construction": "three_point",
                "start": [1, 0],
                "through": [0, 1],
                "end": [-1, 0],
            },
        )
    )

    arc = sketch.state.get_entity("arc_three")
    assert arc.center == pytest.approx((0.0, 0.0))
    assert arc.radius == pytest.approx(1.0)
    assert arc.sweep_angle_deg == pytest.approx(180.0)


def test_degenerate_arc_is_structured_and_does_not_enter_history() -> None:
    sketch = session([])
    with pytest.raises(Exception) as error:
        sketch.execute(
            command(
                "define_arc",
                "bad_arc",
                version="0.5",
                parameters={
                    "name": "bad_arc",
                    "construction": "three_point",
                    "start": [0, 0],
                    "through": [1, 0],
                    "end": [2, 0],
                },
            )
        )
    payload = error.value.to_dict()
    assert payload["code"] == "selection_resolution_error"
    assert payload["detail"]["error_code"] == "invalid_arc_geometry"
    assert sketch.history.records == []


def test_arc_updates_and_linked_point_moves_refresh_canonical_geometry() -> None:
    sketch = session([point("center", 0, 0), point("start", 2, 0), point("end", 0, 2)])
    sketch.execute(
        command(
            "define_arc",
            "linked_arc",
            version="0.5",
            parameters={
                "name": "linked_arc",
                "construction": "center",
                "center": [0, 0],
                "start": [2, 0],
                "end": [0, 2],
                "direction": "clockwise",
                "center_point_id": "center",
                "start_point_id": "start",
                "end_point_id": "end",
            },
        )
    )
    sketch.execute(command("move_point", "move_end", selection=["end"], parameters={"coords": [-2, 0]}))
    arc = sketch.state.get_entity("linked_arc")
    assert arc.radius == pytest.approx(2.0)
    assert arc.sweep_angle_deg == pytest.approx(180.0)

    with pytest.raises(Exception) as error:
        sketch.execute(command("move_point", "degenerate_start", selection=["start"], parameters={"coords": [0, 0]}))
    assert error.value.to_dict()["code"] == "solver_error"
    assert sketch.state.get_entity("start").coords == (2.0, 0.0)

    sketch.execute(
        command(
            "update_arc",
            "detach_and_update",
            version="0.5",
            selection=["linked_arc"],
            parameters={
                "radius": 3,
                "start_angle_deg": 405,
                "sweep_angle_deg": -90,
                "center_point_id": None,
                "start_point_id": None,
                "end_point_id": None,
            },
        )
    )
    updated = sketch.state.get_entity("linked_arc")
    assert updated.radius == pytest.approx(3.0)
    assert updated.start_angle_deg == pytest.approx(45.0)
    assert updated.sweep_angle_deg == pytest.approx(-90.0)


def test_arc_transform_and_copy_preserve_canonical_sweep() -> None:
    sketch = session(
        [
            {
                "id": "arc",
                "type": "arc_2d",
                "center": [0, 0],
                "radius": 2,
                "start_angle_deg": 0,
                "sweep_angle_deg": 90,
                "construction": "center",
            }
        ]
    )
    sketch.execute(command("translate", "move_arc", selection=["arc"], parameters={"vector": [3, -1]}))
    sketch.execute(command("rotate", "rotate_arc", selection=["arc"], parameters={"angle": 90, "angle_unit": "deg", "origin": [0, 0]}))
    sketch.execute(command("mirror", "mirror_arc", selection=["arc"], parameters={"axis_x": 0}))
    arc = sketch.state.get_entity("arc")
    assert arc.center == pytest.approx((-1.0, 3.0))
    assert arc.start_angle_deg == pytest.approx(90.0)
    assert arc.sweep_angle_deg == pytest.approx(-90.0)

    sketch.execute(command("copy_linear", "copy_arc", selection=["arc"], parameters={"vector": [2, 0], "count": 1}))
    copied = sketch.state.get_entity("copy_copy_arc_1_arc")
    assert copied.center == pytest.approx((1.0, 3.0))
    assert copied.sweep_angle_deg == pytest.approx(-90.0)
    assert copied.start_point_id is None


def test_history_supports_multistep_undo_redo_and_branch_truncation() -> None:
    sketch = session([])
    sketch.execute(command("define_point", "one", parameters={"name": "one", "coords": [0, 0]}))
    sketch.execute(command("define_point", "two", parameters={"name": "two", "coords": [1, 0]}))
    sketch.revert()
    sketch.revert()
    assert sketch.state.items == []
    sketch.redo()
    sketch.redo()
    assert [item.id for item in sketch.state.items] == ["one", "two"]
    sketch.revert()
    sketch.execute(command("define_point", "three", parameters={"name": "three", "coords": [2, 0]}))
    assert [record.command.command_id for record in sketch.history.records] == ["one", "three"]
    assert sketch.history.cursor == 2


def test_preview_and_failed_operations_do_not_enter_history() -> None:
    sketch = session([])
    sketch.execute(command("define_point", "preview", parameters={"name": "preview", "coords": [0, 0]}, mode="preview"))
    with pytest.raises(Exception):
        sketch.execute(command("define_circle", "bad", parameters={"name": "bad", "center": [0, 0], "radius": 0}))
    assert sketch.history.records == []
    assert sketch.history.cursor == 0
