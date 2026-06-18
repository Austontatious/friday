from __future__ import annotations

import pytest


def _session(items: list[dict[str, object]], *, constraints: list[dict[str, object]] | None = None):
    from sketchmath.executor.command_router import GeometrySession
    from sketchmath.models.selection_context import SelectionContext

    payload = {
        "selection_set_id": "sel_solver",
        "units": "mm",
        "frame": "canvas_2d",
        "items": items,
        "constraints": constraints or [],
        "named_references": {},
    }
    return GeometrySession(SelectionContext.model_validate(payload))


def _command(command_type: str, command_id: str, *, mode: str = "preview", selection: list[str] | None = None, parameters: dict[str, object] | None = None):
    from sketchmath.models.geometry_command import GeometryCommand

    return GeometryCommand.model_validate(
        {
            "version": "0.1",
            "command_id": command_id,
            "mode": mode,
            "command_type": command_type,
            "selection": selection or [],
            "parameters": parameters or {},
        }
    )


def _coords(session, entity_id: str) -> tuple[float, float]:
    return tuple(next(item.coords for item in session.state.items if item.id == entity_id))


def test_set_angle_with_anchored_segment_moves_only_the_free_point() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [1, 1], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "set_angle",
            "cmd_set_angle",
            mode="commit",
            selection=["point_A", "point_B", "point_C"],
            parameters={"angle": 90.0, "angle_unit": "deg"},
        )
    )

    assert result.after.items[2].coords == pytest.approx((1.0, -1.0))
    assert session.state.items[2].coords == pytest.approx((1.0, -1.0))


def test_make_parallel_moves_one_unlocked_point() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [4, 0], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [0, 2], "locked": True},
            {"id": "point_D", "type": "point_2d", "coords": [1, 3], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "make_parallel",
            "cmd_make_parallel",
            mode="commit",
            selection=["point_A", "point_B", "point_C", "point_D"],
            parameters={},
        )
    )

    assert result.after.items[3].coords == pytest.approx((1.41421356237, 2.0))


def test_make_perpendicular_moves_one_unlocked_point() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [4, 0], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [0, 2], "locked": True},
            {"id": "point_D", "type": "point_2d", "coords": [1, 3], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "make_perpendicular",
            "cmd_make_perpendicular",
            mode="commit",
            selection=["point_A", "point_B", "point_C", "point_D"],
            parameters={},
        )
    )

    assert result.after.items[3].coords == pytest.approx((0.0, 3.41421356237))


def test_make_equal_length_adjusts_target_segment_to_reference_length() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [3, 4], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [0, 2], "locked": True},
            {"id": "point_D", "type": "point_2d", "coords": [1, 2], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "make_equal_length",
            "cmd_equal_length",
            mode="commit",
            selection=["point_A", "point_B", "point_C", "point_D"],
            parameters={},
        )
    )

    assert result.after.items[3].coords == pytest.approx((5.0, 2.0))


def test_make_equal_angle_adjusts_target_angle() -> None:
    session = _session(
        [
            {"id": "source_a", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "source_b", "type": "point_2d", "coords": [1, 0], "locked": True},
            {"id": "source_c", "type": "point_2d", "coords": [1, 1], "locked": True},
            {"id": "target_a", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "target_b", "type": "point_2d", "coords": [2, 0], "locked": True},
            {"id": "target_c", "type": "point_2d", "coords": [3, 0], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "make_equal_angle",
            "cmd_equal_angle",
            mode="commit",
            selection=["source_a", "source_b", "source_c", "target_a", "target_b", "target_c"],
            parameters={},
        )
    )

    assert result.after.items[5].coords == pytest.approx((2.0, 1.0))


def test_solve_constraints_can_place_missing_quadrilateral_corner() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
            {"id": "point_B", "type": "point_2d", "coords": [4, 0], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [4, 3], "locked": True},
            {"id": "point_D", "type": "point_2d", "coords": [1, 1], "locked": False},
        ],
        constraints=[
            {"id": "c_parallel", "type": "parallel_constraint", "points": ["point_A", "point_B", "point_C", "point_D"]},
            {"id": "c_perp", "type": "perpendicular_constraint", "points": ["point_A", "point_B", "point_A", "point_D"]},
        ],
    )

    result = session.execute(_command("solve_constraints", "cmd_solve", mode="commit"))

    assert result.after.items[3].coords == pytest.approx((0.0, 3.0))


def test_under_constrained_solve_returns_structured_error() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
            {"id": "point_B", "type": "point_2d", "coords": [1, 1], "locked": False},
        ],
        constraints=[
            {"id": "c_distance", "type": "distance_constraint", "points": ["point_A", "point_B"], "distance": 5.0, "unit": "mm", "anchor": "midpoint"},
        ],
    )

    with pytest.raises(Exception) as exc_info:
        session.execute(_command("solve_constraints", "cmd_under", mode="commit"))

    assert exc_info.value.to_dict()["code"] == "clarification_required"


def test_over_constrained_solve_returns_structured_error() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": True},
        ],
        constraints=[
            {"id": "c_distance", "type": "distance_constraint", "points": ["point_A", "point_B"], "distance": 5.0, "unit": "mm", "anchor": "midpoint"},
        ],
    )

    with pytest.raises(Exception) as exc_info:
        session.execute(_command("solve_constraints", "cmd_over", mode="commit"))

    assert exc_info.value.to_dict()["code"] == "solver_error"


def test_locked_entity_mutation_rejected_by_solver_commands() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [1, 1], "locked": True},
        ]
    )

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "set_angle",
                "cmd_locked",
                mode="commit",
                selection=["point_A", "point_B", "point_C"],
                parameters={"angle": 45.0, "angle_unit": "deg"},
            )
        )

    assert exc_info.value.to_dict()["code"] == "locked_entity_mutation"


def test_batch_preview_does_not_mutate_state() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "batch",
            "cmd_batch_preview",
            selection=[],
            parameters={
                "commands": [
                    {
                        "version": "0.1",
                        "command_id": "cmd_add",
                        "mode": "preview",
                        "command_type": "define_point",
                        "selection": [],
                        "parameters": {"name": "point_B", "coords": [2, 0]},
                    },
                    {
                        "version": "0.1",
                        "command_id": "cmd_move",
                        "mode": "preview",
                        "command_type": "translate",
                        "selection": ["point_A"],
                        "parameters": {"vector": [1, 0]},
                    },
                ]
            },
        )
    )

    assert result.status == "preview"
    assert session.state.items[0].coords == (0.0, 0.0)
    assert len(session.state.items) == 1
    assert session.history.records == []


def test_batch_commit_mutates_state_and_is_replayable() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "batch",
            "cmd_batch_commit",
            mode="commit",
            selection=[],
            parameters={
                "commands": [
                    {
                        "version": "0.1",
                        "command_id": "cmd_add_commit",
                        "mode": "commit",
                        "command_type": "define_point",
                        "selection": [],
                        "parameters": {"name": "point_B", "coords": [2, 0]},
                    },
                    {
                        "version": "0.1",
                        "command_id": "cmd_move_commit",
                        "mode": "commit",
                        "command_type": "translate",
                        "selection": ["point_A"],
                        "parameters": {"vector": [1, 0]},
                    },
                ]
            },
        )
    )

    assert result.status == "committed"
    assert len(session.history.records) == 1
    assert session.state.items[0].coords == pytest.approx((1.0, 0.0))
    assert {item.id for item in session.state.items} == {"point_A", "point_B"}
    assert session.history.replay(session.initial_state).items[0].coords == pytest.approx((1.0, 0.0))


def test_revert_after_batch_commit_restores_prior_state() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
        ]
    )
    session.execute(
        _command(
            "batch",
            "cmd_batch_revert",
            mode="commit",
            selection=[],
            parameters={
                "commands": [
                    {
                        "version": "0.1",
                        "command_id": "cmd_batch_revert_add",
                        "mode": "commit",
                        "command_type": "define_point",
                        "selection": [],
                        "parameters": {"name": "point_B", "coords": [2, 0]},
                    }
                ]
            },
        )
    )

    reverted = session.revert()

    assert {item.id for item in reverted.items} == {"point_A"}
    assert session.history.records == []


def test_make_profile_succeeds_for_closed_polygon() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [2, 0], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [2, 2], "locked": True},
            {"id": "point_D", "type": "point_2d", "coords": [0, 2], "locked": True},
        ]
    )

    result = session.execute(
        _command(
            "make_profile",
            "cmd_profile",
            mode="commit",
            selection=["point_A", "point_B", "point_C", "point_D", "point_A"],
            parameters={"name": "profile_square"},
        )
    )

    assert result.metadata["area"] == pytest.approx(4.0)
    assert result.metadata["winding"] == "counterclockwise"
    assert any(item.id == "profile_square" for item in session.state.items)


def test_make_profile_fails_for_open_profile() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [2, 0], "locked": True},
            {"id": "point_C", "type": "point_2d", "coords": [2, 2], "locked": True},
            {"id": "point_D", "type": "point_2d", "coords": [0, 2], "locked": True},
        ]
    )

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "make_profile",
                "cmd_profile_open",
                mode="commit",
                selection=["point_A", "point_B", "point_C", "point_D"],
                parameters={"name": "profile_open"},
            )
        )

    assert exc_info.value.to_dict()["code"] == "selection_resolution_error"
