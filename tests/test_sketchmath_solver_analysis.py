from __future__ import annotations

import pytest

from sketchmath.executor.command_router import GeometrySession
from sketchmath.executor.errors import CommandValidationError
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext
from sketchmath.solver.analysis import analyze_constraint_system


def _state(*, items: list[dict], constraints: list[dict] | None = None) -> SelectionContext:
    return SelectionContext.model_validate(
        {
            "selection_set_id": "solver_analysis",
            "units": "mm",
            "frame": "canvas_2d",
            "items": items,
            "constraints": constraints or [],
            "named_references": {},
        }
    )


def _point(point_id: str, x: float, y: float, *, locked: bool = False) -> dict:
    return {"id": point_id, "type": "point_2d", "coords": [x, y], "locked": locked}


def test_free_point_dof_is_exact() -> None:
    analysis = analyze_constraint_system(_state(items=[_point("a", 0, 0), _point("b", 5, 2)]))

    assert analysis.coverage == "exact"
    assert analysis.freedom_state == "under_constrained"
    assert analysis.consistency_state == "consistent"
    assert analysis.tracked_variable_count == 4
    assert analysis.independent_equation_count == 0
    assert analysis.remaining_dof == 4


def test_point_backed_line_horizontal_constraint_has_three_dof() -> None:
    state = _state(
        items=[
            _point("a", 0, 0),
            _point("b", 5, 2),
            {
                "id": "line",
                "type": "line_2d",
                "start": [0, 0],
                "end": [5, 2],
                "start_point_id": "a",
                "end_point_id": "b",
            },
        ],
        constraints=[{"id": "horizontal", "type": "horizontal_constraint", "points": ["a", "b"]}],
    )

    analysis = analyze_constraint_system(state)

    assert analysis.coverage == "exact"
    assert analysis.supported_constraint_ids == ["horizontal"]
    assert analysis.unmodeled_entity_ids == []
    assert analysis.independent_equation_count == 1
    assert analysis.remaining_dof == 3


def test_locked_points_expose_inconsistent_linear_constraint() -> None:
    state = _state(
        items=[_point("a", 0, 0, locked=True), _point("b", 5, 2, locked=True)],
        constraints=[{"id": "horizontal", "type": "horizontal_constraint", "points": ["a", "b"]}],
    )

    analysis = analyze_constraint_system(state)

    assert analysis.coverage == "exact"
    assert analysis.consistency_state == "inconsistent"
    assert analysis.freedom_state == "unknown"
    assert analysis.conflicting_constraint_ids == ["horizontal"]
    assert analysis.remaining_dof is None


def test_coincident_constraint_can_be_proven_redundant() -> None:
    state = _state(
        items=[_point("a", 0, 0, locked=True), _point("b", 0, 0, locked=True)],
        constraints=[{"id": "same", "type": "coincident_constraint", "points": ["a", "b"]}],
    )

    analysis = analyze_constraint_system(state)

    assert analysis.consistency_state == "consistent"
    assert analysis.redundancy_state == "redundant"
    assert analysis.redundant_constraint_ids == ["same"]
    assert analysis.remaining_dof == 0


def test_nonlinear_distance_constraint_reports_exact_dof() -> None:
    state = _state(
        items=[_point("a", 0, 0), _point("b", 5, 0)],
        constraints=[
            {
                "id": "distance",
                "type": "distance_constraint",
                "points": ["a", "b"],
                "distance": 5,
            }
        ],
    )

    analysis = analyze_constraint_system(state)

    assert analysis.coverage == "exact"
    assert analysis.freedom_state == "under_constrained"
    assert analysis.consistency_state == "consistent"
    assert analysis.supported_constraint_ids == ["distance"]
    assert analysis.unsupported_constraint_ids == []
    assert analysis.remaining_dof == 3
    assert analysis.remaining_tracked_dof_upper_bound == 3


def test_axis_distances_are_exact_linear_constraints() -> None:
    state = _state(
        items=[_point("a", 0, 0, locked=True), _point("b", 8, -3)],
        constraints=[
            {
                "id": "horizontal_distance",
                "type": "horizontal_distance_constraint",
                "points": ["a", "b"],
                "distance": 8,
                "direction": 1,
            },
            {
                "id": "vertical_distance",
                "type": "vertical_distance_constraint",
                "points": ["a", "b"],
                "distance": 3,
                "direction": -1,
            },
        ],
    )

    analysis = analyze_constraint_system(state)

    assert analysis.coverage == "exact"
    assert analysis.freedom_state == "fully_constrained"
    assert analysis.consistency_state == "consistent"
    assert analysis.independent_equation_count == 4
    assert analysis.remaining_dof == 0


def test_circle_radius_constraint_tracks_center_and_radius_dof() -> None:
    state = _state(
        items=[
            _point("center", 2, 3, locked=True),
            {"id": "circle", "type": "circle_2d", "center": [2, 3], "radius": 5, "center_point_id": "center"},
            {
                "id": "profile_circle",
                "type": "profile_2d",
                "vertices": [[7, 3], [2, 8], [-3, 3], [2, -2], [7, 3]],
                "area": 78.5,
                "winding": "counterclockwise",
                "source_circle_id": "circle",
            },
        ],
        constraints=[{"id": "radius", "type": "radius_constraint", "circle_id": "circle", "radius": 5}],
    )

    analysis = analyze_constraint_system(state)

    assert analysis.coverage == "exact"
    assert analysis.tracked_variable_count == 3
    assert analysis.independent_equation_count == 3
    assert analysis.remaining_dof == 0
    assert analysis.unmodeled_entity_ids == []


def test_equivalent_radius_and_diameter_constraints_are_redundant() -> None:
    state = _state(
        items=[{"id": "circle", "type": "circle_2d", "center": [0, 0], "radius": 4}],
        constraints=[
            {"id": "radius", "type": "radius_constraint", "circle_id": "circle", "radius": 4},
            {"id": "diameter", "type": "diameter_constraint", "circle_id": "circle", "diameter": 8},
        ],
    )

    analysis = analyze_constraint_system(state)

    assert analysis.coverage == "exact"
    assert analysis.redundancy_state == "redundant"
    assert analysis.redundant_constraint_ids == ["radius"]
    assert analysis.remaining_dof == 2


def test_coordinate_only_line_prevents_whole_sketch_dof_claim() -> None:
    state = _state(items=[{"id": "legacy", "type": "line_2d", "start": [0, 0], "end": [5, 0]}])

    analysis = analyze_constraint_system(state)

    assert analysis.coverage == "unknown"
    assert analysis.unmodeled_entity_ids == ["legacy"]
    assert analysis.remaining_dof is None


def test_analyze_command_is_preview_only_and_does_not_enter_history() -> None:
    session = GeometrySession(_state(items=[_point("a", 0, 0)]))
    command = GeometryCommand.model_validate(
        {
            "version": "0.3",
            "command_id": "analyze",
            "mode": "preview",
            "command_type": "analyze_constraints",
            "selection": [],
            "parameters": {},
        }
    )

    result = session.execute(command)

    assert result.changed_entity_ids == []
    assert result.metadata["solver_analysis"]["remaining_dof"] == 2
    assert result.metadata["solver_run"]["mode"] == "analyze"
    assert result.metadata["solver_run"]["outcome"] == "analyzed"
    assert result.metadata["solver_run"]["proposed_patch"] == []
    assert session.history.records == []

    with pytest.raises(CommandValidationError):
        session.execute(command.model_copy(update={"mode": "commit"}))
