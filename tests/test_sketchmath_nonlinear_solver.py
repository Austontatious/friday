from __future__ import annotations

import math

import pytest

from sketchmath.executor.command_router import GeometrySession
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext
from sketchmath.solver.nonlinear import evaluate_nonlinear_system


def _state(items: list[dict[str, object]], constraints: list[dict[str, object]]) -> SelectionContext:
    return SelectionContext.model_validate(
        {
            "selection_set_id": "nonlinear_adversarial",
            "units": "mm",
            "frame": "canvas_2d",
            "items": items,
            "constraints": constraints,
            "named_references": {},
        }
    )


def _point(point_id: str, x: float, y: float, *, locked: bool = False) -> dict[str, object]:
    return {"id": point_id, "type": "point_2d", "coords": [x, y], "locked": locked}


def _solve(session: GeometrySession) -> object:
    return session.execute(
        GeometryCommand(
            version="0.7",
            command_id="adversarial_solve",
            mode="commit",
            command_type="solve_constraints",
        )
    )


def test_far_seed_and_zero_length_seed_converge_with_validated_residuals() -> None:
    constraints = [
        {"id": "distance", "type": "distance_constraint", "points": ["a", "b"], "distance": 10, "unit": "mm"},
        {"id": "horizontal", "type": "horizontal_constraint", "points": ["a", "b"]},
    ]
    for start in ((120.0, 75.0), (0.0, 0.0)):
        session = GeometrySession(_state([_point("a", 0, 0, locked=True), _point("b", *start)], constraints))

        result = _solve(session)
        solved = result.after.get_entity("b").coords

        assert math.dist((0.0, 0.0), solved) == pytest.approx(10.0, abs=1e-7)
        assert solved[1] == pytest.approx(0.0, abs=1e-7)
        assert result.metadata["solver_run"]["residual_norm"] <= 1e-7
        assert result.metadata["solver_run"]["feasible"] is True
        assert result.metadata["solver_run"]["schema_version"] == "1.1"
        assert result.metadata["solver_run"]["jacobian_strategy"] == "scipy_3_point_with_central_rank_check"
        assert result.metadata["solver_run"]["jacobian_rank"] == 4
        assert result.metadata["solver_run"]["residual_count"] == 4
        assert result.metadata["solver_run"]["seed_count"] == 3
        assert result.metadata["solver_run"]["optimizer_terminated_successfully"] is True


@pytest.mark.parametrize(("angle", "expected_x"), [(0.0, 2.0), (1e-7, 2.0), (180.0, -2.0), (179.9999999, -2.0)])
def test_boundary_angles_converge_without_branch_instability(angle: float, expected_x: float) -> None:
    state = _state(
        [_point("anchor", 1, 0, locked=True), _point("pivot", 0, 0, locked=True), _point("moving", 0.25, 3)],
        [
            {"id": "angle", "type": "angle_constraint", "points": ["anchor", "pivot", "moving"], "angle": angle, "unit": "deg"},
            {"id": "length", "type": "distance_constraint", "points": ["pivot", "moving"], "distance": 2, "unit": "mm"},
        ],
    )

    result = _solve(GeometrySession(state))
    moving = result.after.get_entity("moving").coords

    assert moving[0] == pytest.approx(expected_x, abs=1e-6)
    assert moving[1] == pytest.approx(0.0, abs=1e-6)
    assert result.metadata["solver_run"]["residual_norm"] <= 1e-7


def test_conflicting_nonlinear_dimensions_are_rejected_without_mutation() -> None:
    state = _state(
        [_point("a", 0, 0, locked=True), _point("b", 8, 0)],
        [
            {"id": "distance_1", "type": "distance_constraint", "points": ["a", "b"], "distance": 1, "unit": "mm"},
            {"id": "distance_2", "type": "distance_constraint", "points": ["a", "b"], "distance": 2, "unit": "mm"},
            {"id": "horizontal", "type": "horizontal_constraint", "points": ["a", "b"]},
        ],
    )
    session = GeometrySession(state)

    with pytest.raises(Exception) as error:
        _solve(session)

    payload = error.value.to_dict()
    assert payload["code"] == "solver_error"
    assert payload["detail"]["solver_run"]["outcome"] == "inconsistent"
    assert payload["detail"]["solver_run"]["feasible"] is False
    assert set(payload["detail"]["solver_run"]["analysis_after"]["conflicting_constraint_ids"]) == {"distance_1", "distance_2"}
    assert session.state.get_entity("b").coords == (8.0, 0.0)


def test_duplicate_nonlinear_dimension_is_explicitly_redundant() -> None:
    state = _state(
        [_point("a", 0, 0, locked=True), _point("b", 5, 0)],
        [
            {"id": "distance_a", "type": "distance_constraint", "points": ["a", "b"], "distance": 5, "unit": "mm"},
            {"id": "distance_b", "type": "distance_constraint", "points": ["a", "b"], "distance": 5, "unit": "mm"},
            {"id": "horizontal", "type": "horizontal_constraint", "points": ["a", "b"]},
        ],
    )
    evaluation = evaluate_nonlinear_system(state)

    assert evaluation is not None
    assert evaluation.analysis.consistency_state == "consistent"
    assert evaluation.analysis.redundancy_state == "redundant"
    assert evaluation.analysis.redundant_constraint_ids == ["distance_b"]


def test_long_reversed_constraint_chain_cannot_false_positive_before_convergence() -> None:
    items = [_point("p00", 0, 0, locked=True), *[_point(f"p{index:02d}", float(index), 0) for index in range(1, 13)]]
    constraints = [
        {
            "id": f"coincident_{12 - index:02d}",
            "type": "coincident_constraint",
            "points": [f"p{12 - index - 1:02d}", f"p{12 - index:02d}"],
        }
        for index in range(12)
    ]
    session = GeometrySession(_state(items, constraints))

    result = _solve(session)

    assert result.metadata["solver_run"]["outcome"] == "solved"
    assert result.metadata["solver_run"]["residual_norm"] <= 1e-7
    assert {session.state.get_entity(f"p{index:02d}").coords for index in range(13)} == {(0.0, 0.0)}


def test_distance_constraint_replay_normalizes_centimeters_to_millimeters() -> None:
    session = GeometrySession(
        _state(
            [_point("a", 0, 0, locked=True), _point("b", 1, 0)],
            [
                {"id": "distance", "type": "distance_constraint", "points": ["a", "b"], "distance": 2, "unit": "cm"},
                {"id": "horizontal", "type": "horizontal_constraint", "points": ["a", "b"]},
            ],
        )
    )

    result = _solve(session)

    assert result.after.get_entity("b").coords == pytest.approx((20.0, 0.0), abs=1e-7)
    assert result.metadata["solver_run"]["residual_norm"] <= 1e-7


def test_coincident_circle_centers_use_deterministic_tangent_seed_recovery() -> None:
    state = _state(
        [
            _point("center_a", 0, 0, locked=True),
            _point("center_b", 0, 0),
            {"id": "circle_a", "type": "circle_2d", "center": [0, 0], "radius": 2, "center_point_id": "center_a"},
            {"id": "circle_b", "type": "circle_2d", "center": [0, 0], "radius": 3, "center_point_id": "center_b"},
        ],
        [
            {"id": "horizontal", "type": "horizontal_constraint", "points": ["center_a", "center_b"]},
            {"id": "radius_a", "type": "radius_constraint", "circle_id": "circle_a", "radius": 2, "unit": "mm"},
            {"id": "radius_b", "type": "radius_constraint", "circle_id": "circle_b", "radius": 3, "unit": "mm"},
            {"id": "tangent", "type": "tangent_constraint", "entities": ["circle_a", "circle_b"], "tangency": "external"},
        ],
    )

    first = _solve(GeometrySession(state))
    second = _solve(GeometrySession(state.model_copy(deep=True)))
    first_center = first.after.get_entity("center_b").coords
    second_center = second.after.get_entity("center_b").coords

    assert first_center == second_center
    assert abs(first_center[0]) == pytest.approx(5.0, abs=1e-7)
    assert first_center[1] == pytest.approx(0.0, abs=1e-7)
    assert first.metadata["solver_run"]["residual_norm"] <= 1e-7
