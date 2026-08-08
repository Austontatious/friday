from __future__ import annotations

import pytest

from sketchmath.executor.command_router import GeometrySession
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext


def _point(point_id: str, x: float, y: float, *, locked: bool = False) -> dict[str, object]:
    return {"id": point_id, "type": "point_2d", "coords": [x, y], "locked": locked}


def _command(command_type: str, command_id: str, selection: list[str], parameters: dict[str, object] | None = None) -> GeometryCommand:
    return GeometryCommand(
        version="0.6",
        command_id=command_id,
        mode="commit",
        command_type=command_type,
        selection=selection,
        parameters=parameters or {},
    )


def _session(items: list[dict[str, object]]) -> GeometrySession:
    return GeometrySession(
        SelectionContext.model_validate(
            {
                "selection_set_id": "gate_b_constraints",
                "units": "mm",
                "frame": "canvas_2d",
                "items": items,
                "constraints": [],
                "named_references": {},
            }
        )
    )


def _analysis(session: GeometrySession) -> dict[str, object]:
    command = GeometryCommand(version="0.3", command_id="analysis", mode="preview", command_type="analyze_constraints")
    return session.execute(command).metadata["solver_analysis"]


def test_fixed_constraint_is_exact_and_blocks_drag_without_partial_commit() -> None:
    session = _session([_point("anchor", 2, 3)])
    result = session.execute(_command("make_fixed", "fix", ["anchor"]))
    assert result.after.constraints[0].type == "fixed_point_constraint"
    assert _analysis(session)["remaining_dof"] == 0

    with pytest.raises(Exception) as error:
        session.execute(_command("move_point", "drag", ["anchor"], {"coords": [9, 9]}))
    assert error.value.to_dict()["code"] == "solver_error"
    assert session.state.get_entity("anchor").coords == (2.0, 3.0)


def test_midpoint_constraint_moves_point_and_enters_exact_linear_analysis() -> None:
    session = _session([_point("mid", 9, 4), _point("a", 0, 0, locked=True), _point("b", 8, 4, locked=True)])
    result = session.execute(_command("make_midpoint", "midpoint", ["mid", "a", "b"]))
    assert result.after.get_entity("mid").coords == (4.0, 2.0)
    assert result.after.constraints[0].type == "midpoint_constraint"
    analysis = _analysis(session)
    assert analysis["coverage"] == "exact"
    assert analysis["remaining_dof"] == 0


def test_collinear_and_symmetric_constraints_apply_closed_form_and_remain_partial() -> None:
    collinear = _session([_point("a", 0, 0), _point("b", 8, 0), _point("moving", 3, 4)])
    result = collinear.execute(_command("make_collinear", "collinear", ["a", "b", "moving"]))
    assert result.after.get_entity("moving").coords == pytest.approx((3.0, 0.0))
    assert _analysis(collinear)["coverage"] == "partial"

    symmetric = _session([_point("reference", 2, 1), _point("target", 5, 5), _point("axis_a", 0, 0), _point("axis_b", 0, 6)])
    result = symmetric.execute(_command("make_symmetric", "symmetric", ["reference", "target", "axis_a", "axis_b"]))
    assert result.after.get_entity("target").coords == pytest.approx((-2.0, 1.0))
    assert _analysis(symmetric)["coverage"] == "partial"


def test_concentric_circles_update_linked_center_and_are_exact() -> None:
    session = _session(
        [
            _point("target_center", 10, 5),
            {"id": "reference", "type": "circle_2d", "center": [2, 3], "radius": 4},
            {"id": "target", "type": "circle_2d", "center": [10, 5], "radius": 2, "center_point_id": "target_center"},
        ]
    )
    result = session.execute(_command("make_concentric", "concentric", ["reference", "target"]))
    assert result.after.get_entity("target_center").coords == (2.0, 3.0)
    assert result.after.get_entity("target").center == (2.0, 3.0)
    analysis = _analysis(session)
    assert analysis["coverage"] == "exact"
    assert analysis["supported_constraint_ids"] == ["constraint_concentric"]


def test_concentric_constraint_is_preserved_when_reference_center_is_dragged() -> None:
    session = _session(
        [
            _point("reference_center", 2, 3),
            _point("target_center", 10, 5),
            {"id": "reference", "type": "circle_2d", "center": [2, 3], "radius": 4, "center_point_id": "reference_center"},
            {"id": "target", "type": "circle_2d", "center": [10, 5], "radius": 2, "center_point_id": "target_center"},
        ]
    )
    session.execute(_command("make_concentric", "concentric", ["reference", "target"]))
    result = session.execute(_command("move_point", "drag_reference", ["reference_center"], {"coords": [7, 8]}))
    assert result.after.get_entity("reference").center == (7.0, 8.0)
    assert result.after.get_entity("target_center").coords == (7.0, 8.0)
    assert result.after.get_entity("target").center == (7.0, 8.0)


def test_tangent_supports_line_circle_and_circle_circle_but_rejects_finite_arcs() -> None:
    line_circle = _session(
        [
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [10, 0]},
            {"id": "circle", "type": "circle_2d", "center": [4, 7], "radius": 2},
        ]
    )
    result = line_circle.execute(_command("make_tangent", "line_circle", ["line", "circle"]))
    assert result.after.get_entity("circle").center == pytest.approx((4.0, 2.0))
    assert _analysis(line_circle)["coverage"] == "partial"

    circles = _session(
        [
            {"id": "reference", "type": "circle_2d", "center": [0, 0], "radius": 2},
            {"id": "target", "type": "circle_2d", "center": [10, 0], "radius": 3},
        ]
    )
    result = circles.execute(_command("make_tangent", "circle_circle", ["reference", "target"]))
    assert result.after.get_entity("target").center == pytest.approx((5.0, 0.0))

    arc_session = _session(
        [
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [10, 0]},
            {
                "id": "arc",
                "type": "arc_2d",
                "center": [5, 5],
                "radius": 2,
                "start_angle_deg": 0,
                "sweep_angle_deg": 90,
                "construction": "center",
            },
        ]
    )
    with pytest.raises(Exception) as error:
        arc_session.execute(_command("make_tangent", "arc_tangent", ["line", "arc"]))
    assert error.value.to_dict()["detail"]["error_code"] == "unsupported_arc_tangency"
    assert arc_session.state.constraints == []


def test_tangent_constraint_is_preserved_when_linked_circle_center_is_dragged() -> None:
    session = _session(
        [
            _point("center", 4, 7),
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [10, 0]},
            {"id": "circle", "type": "circle_2d", "center": [4, 7], "radius": 2, "center_point_id": "center"},
        ]
    )
    session.execute(_command("make_tangent", "tangent", ["line", "circle"]))
    result = session.execute(_command("move_point", "drag_center", ["center"], {"coords": [4, 8]}))
    assert result.after.get_entity("center").coords == pytest.approx((4.0, 2.0))
    assert result.after.get_entity("circle").center == pytest.approx((4.0, 2.0))


@pytest.mark.parametrize(
    ("command_type", "selection"),
    [
        ("make_midpoint", ["a", "a", "b"]),
        ("make_collinear", ["a", "b", "b"]),
        ("make_symmetric", ["a", "b", "c", "c"]),
        ("make_concentric", ["circle_a", "circle_a"]),
        ("make_tangent", ["circle_a", "circle_a"]),
    ],
)
def test_new_constraint_families_reject_repeated_entity_ids(command_type: str, selection: list[str]) -> None:
    session = _session(
        [
            _point("a", 0, 0),
            _point("b", 1, 0),
            _point("c", 0, 1),
            {"id": "circle_a", "type": "circle_2d", "center": [0, 0], "radius": 1},
        ]
    )
    with pytest.raises(Exception) as error:
        session.execute(_command(command_type, f"invalid_{command_type}", selection))
    assert error.value.to_dict()["code"] == "selection_resolution_error"
    assert session.state.constraints == []
