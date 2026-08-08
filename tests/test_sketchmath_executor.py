from __future__ import annotations

import pytest


def _session(items: list[dict[str, object]], *, units: str = "mm", constraints: list[dict[str, object]] | None = None):
    from sketchmath.executor.command_router import GeometrySession
    from sketchmath.models.selection_context import SelectionContext

    return GeometrySession(
        SelectionContext.model_validate(
            {
                "selection_set_id": "sel_test",
                "units": units,
                "frame": "canvas_2d",
                "items": items,
                "constraints": constraints or [],
                "named_references": {},
            }
        )
    )


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


def _rectangle_batch_command(*, mode: str = "commit"):
    return _command(
        "batch",
        "cmd_rectangle_batch",
        mode=mode,
        parameters={
            "commands": [
                _command("define_point", "cmd_rect_a", parameters={"name": "rect_test_a", "coords": [10, 20], "label": "A"}).model_dump(),
                _command("define_point", "cmd_rect_b", parameters={"name": "rect_test_b", "coords": [50, 20], "label": "B"}).model_dump(),
                _command("define_point", "cmd_rect_c", parameters={"name": "rect_test_c", "coords": [50, 45], "label": "C"}).model_dump(),
                _command("define_point", "cmd_rect_d", parameters={"name": "rect_test_d", "coords": [10, 45], "label": "D"}).model_dump(),
                _command("define_line", "cmd_rect_ab", parameters={"name": "rect_test_ab", "start": [10, 20], "end": [50, 20], "label": "AB"}).model_dump(),
                _command("define_line", "cmd_rect_bc", parameters={"name": "rect_test_bc", "start": [50, 20], "end": [50, 45], "label": "BC"}).model_dump(),
                _command("define_line", "cmd_rect_cd", parameters={"name": "rect_test_cd", "start": [50, 45], "end": [10, 45], "label": "CD"}).model_dump(),
                _command("define_line", "cmd_rect_da", parameters={"name": "rect_test_da", "start": [10, 45], "end": [10, 20], "label": "DA"}).model_dump(),
                _command("make_parallel", "cmd_rect_parallel_1", selection=["rect_test_a", "rect_test_b", "rect_test_c", "rect_test_d"]).model_dump(),
                _command("make_parallel", "cmd_rect_parallel_2", selection=["rect_test_b", "rect_test_c", "rect_test_d", "rect_test_a"]).model_dump(),
                _command("make_perpendicular", "cmd_rect_perpendicular", selection=["rect_test_a", "rect_test_b", "rect_test_b", "rect_test_c"]).model_dump(),
                _command("solve_constraints", "cmd_rect_solve").model_dump(),
                _command("make_profile", "cmd_rect_profile", selection=["rect_test_ab", "rect_test_bc", "rect_test_cd", "rect_test_da"], parameters={"name": "profile_rect_test"}).model_dump(),
            ]
        },
    )


def _coords_by_id(state) -> dict[str, tuple[float, float]]:
    return {item.id: tuple(item.coords) for item in state.items if hasattr(item, "coords")}


def test_distance_between_two_points() -> None:
    from sketchmath.geometry.vectors import distance

    assert distance((0.0, 0.0), (3.0, 4.0)) == pytest.approx(5.0)


def test_measure_distance_returns_value_without_mutating_state() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
            {"id": "point_B", "type": "point_2d", "coords": [3, 4], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "measure_distance",
            "cmd_measure_distance",
            selection=["point_A", "point_B"],
            parameters={"unit": "mm"},
        )
    )

    assert result.status == "preview"
    assert result.value == pytest.approx(5.0)
    assert result.unit == "mm"
    assert _coords_by_id(session.state) == {"point_A": (0.0, 0.0), "point_B": (3.0, 4.0)}
    assert session.history.records == []


def test_measure_angle_returns_value_for_line_entities() -> None:
    session = _session(
        [
            {"id": "line_A", "type": "line_2d", "start": [0, 0], "end": [1, 0], "locked": False},
            {"id": "line_B", "type": "construction_line_2d", "start": [0, 0], "end": [0, 3], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "measure_angle",
            "cmd_measure_angle",
            selection=["line_A", "line_B"],
            parameters={"unit": "deg"},
        )
    )

    assert result.status == "preview"
    assert result.value == pytest.approx(90.0)
    assert result.unit == "deg"
    assert session.history.records == []


def test_set_distance_preview_and_commit_follow_replayable_history() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False},
        ]
    )

    preview = session.execute(
        _command(
            "set_distance",
            "cmd_set_distance_preview",
            selection=["point_A", "point_B"],
            parameters={"distance": 8.0, "unit": "mm", "anchor": "point_A"},
        )
    )
    assert preview.after.items[1].coords == pytest.approx((8.0, 0.0))
    assert session.state.items[1].coords == (1.0, 0.0)
    assert session.history.records == []

    commit = session.execute(
        _command(
            "set_distance",
            "cmd_set_distance_commit",
            mode="commit",
            selection=["point_A", "point_B"],
            parameters={"distance": 8.0, "unit": "mm", "anchor": "point_A"},
        )
    )
    assert commit.status == "committed"
    assert session.state.items[1].coords == pytest.approx((8.0, 0.0))
    assert len(session.history.records) == 1
    assert session.history.replay(session.initial_state).items[1].coords == pytest.approx((8.0, 0.0))


def test_set_line_polar_commit_moves_end_point_only() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [2, 3], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [9, 9], "locked": False},
        ]
    )

    result = session.execute(
        _command(
            "set_line_polar",
            "cmd_set_line_polar",
            mode="commit",
            selection=["point_A", "point_B"],
            parameters={
                "start": "point_A",
                "end": "point_B",
                "length": 5.0,
                "length_unit": "mm",
                "angle": 0.0,
                "angle_unit": "deg",
            },
        )
    )

    assert result.after.items[0].coords == (2.0, 3.0)
    assert result.after.items[1].coords == pytest.approx((7.0, 3.0))
    assert session.state.items[1].coords == pytest.approx((7.0, 3.0))


def test_translate_rotate_and_mirror_cover_mutating_geometry_paths() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [1, 2], "locked": False},
            {"id": "line_A", "type": "line_2d", "start": [0, 0], "end": [2, 0], "locked": False},
        ]
    )

    translated = session.execute(
        _command(
            "translate",
            "cmd_translate",
            mode="commit",
            selection=["point_A", "line_A"],
            parameters={"vector": [3, -1]},
        )
    )
    assert translated.after.items[0].coords == pytest.approx((4.0, 1.0))
    assert translated.after.items[1].start == pytest.approx((3.0, -1.0))
    assert translated.after.items[1].end == pytest.approx((5.0, -1.0))

    rotated = session.execute(
        _command(
            "rotate",
            "cmd_rotate",
            mode="commit",
            selection=["point_A", "line_A"],
            parameters={"angle": 90.0, "angle_unit": "deg", "origin": [0, 0]},
        )
    )
    assert rotated.after.items[0].coords == pytest.approx((-1.0, 4.0))
    assert rotated.after.items[1].start == pytest.approx((1.0, 3.0))
    assert rotated.after.items[1].end == pytest.approx((1.0, 5.0))

    mirrored = session.execute(
        _command(
            "mirror",
            "cmd_mirror",
            mode="commit",
            selection=["point_A", "line_A"],
            parameters={"axis_x": 1.0},
        )
    )
    assert mirrored.after.items[0].coords == pytest.approx((3.0, 4.0))
    assert mirrored.after.items[1].start == pytest.approx((1.0, 3.0))
    assert mirrored.after.items[1].end == pytest.approx((1.0, 5.0))


def test_intersect_lines_project_point_and_copy_linear_are_deterministic() -> None:
    session = _session(
        [
            {"id": "line_A", "type": "line_2d", "start": [0, 0], "end": [4, 4], "locked": False},
            {"id": "line_B", "type": "line_2d", "start": [0, 4], "end": [4, 0], "locked": False},
            {"id": "point_A", "type": "point_2d", "coords": [2, 3], "locked": False},
        ]
    )

    intersect = session.execute(
        _command(
            "intersect_lines",
            "cmd_intersect",
            mode="commit",
            selection=["line_A", "line_B"],
            parameters={},
        )
    )
    assert intersect.after.items[-1].id == "line_A_line_B_intersection"
    assert intersect.after.items[-1].coords == pytest.approx((2.0, 2.0))

    projected = session.execute(
        _command(
            "project_point_to_line",
            "cmd_project",
            mode="commit",
            selection=["point_A", "line_A"],
            parameters={},
        )
    )
    assert projected.after.items[-1].id == "point_A_projected"
    assert projected.after.items[-1].coords == pytest.approx((2.5, 2.5))

    copied = session.execute(
        _command(
            "copy_linear",
            "cmd_copy_linear",
            mode="commit",
            selection=["point_A", "line_A"],
            parameters={"vector": [10, 0], "count": 2, "id_prefix": "copy"},
        )
    )
    assert "copy_cmd_copy_linear_1_point_A" in {item.id for item in copied.after.items}
    assert "copy_cmd_copy_linear_2_line_A" in {item.id for item in copied.after.items}
    assert session.history.records[-1].command.command_type == "copy_linear"


def test_delete_entity_removes_unreferenced_entity_and_updates_history() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False, "label": "A"},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False, "label": "B"},
        ]
    )

    deleted = session.execute(
        _command(
            "delete_entity",
            "cmd_delete",
            mode="commit",
            selection=["point_B"],
            parameters={},
        )
    )

    assert "point_B" not in {item.id for item in deleted.after.items}
    assert "B" not in deleted.after.named_references
    assert session.history.records[-1].command.command_type == "delete_entity"


def test_delete_entity_cascade_removes_referenced_constraints() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False, "label": "A"},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False, "label": "B"},
        ],
        constraints=[
            {"id": "c_distance", "type": "distance_constraint", "points": ["point_A", "point_B"], "distance": 1.0, "unit": "mm"},
        ],
    )

    deleted = session.execute(
        _command(
            "delete_entity",
            "cmd_delete_cascade",
            mode="commit",
            selection=["point_A", "point_B"],
            parameters={"cascade": True},
        )
    )

    assert deleted.after.items == []
    assert deleted.after.constraints == []
    assert deleted.metadata["deleted_entity_ids"] == ["point_A", "point_B"]


def test_referenced_delete_reports_dependency_detail_without_mutating_state() -> None:
    from sketchmath.executor.errors import SelectionResolutionError

    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False, "label": "A"},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False, "label": "B"},
        ],
        constraints=[
            {"id": "c_distance", "type": "distance_constraint", "points": ["point_A", "point_B"], "distance": 1.0, "unit": "mm"},
        ],
    )

    with pytest.raises(SelectionResolutionError) as exc_info:
        session.execute(
            _command(
                "delete_entity",
                "cmd_delete_referenced",
                mode="commit",
                selection=["point_A"],
                parameters={},
            )
        )

    assert exc_info.value.detail["entity_id"] == "point_A"
    assert exc_info.value.detail["dependencies"] == [{"kind": "constraint", "id": "c_distance"}]
    assert [item.id for item in session.state.items] == ["point_A", "point_B"]
    assert [constraint.id for constraint in session.state.constraints] == ["c_distance"]
    assert session.history.records == []


def test_rectangle_batch_keeps_generated_points_aligned_with_edges_and_profile() -> None:
    session = _session([])

    result = session.execute(_rectangle_batch_command())

    assert result.status == "committed"
    assert _coords_by_id(result.after) == {
        "rect_test_a": (10.0, 20.0),
        "rect_test_b": (50.0, 20.0),
        "rect_test_c": (50.0, 45.0),
        "rect_test_d": (10.0, 45.0),
    }
    profile = result.after.get_entity("profile_rect_test")
    assert profile.closed is True
    assert profile.vertices == [(10.0, 20.0), (50.0, 20.0), (50.0, 45.0), (10.0, 45.0), (10.0, 20.0)]


def test_plain_set_distance_does_not_preserve_rectangle_edges_and_profile() -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())

    result = session.execute(
        _command(
            "set_distance",
            "cmd_rect_width_set_distance",
            selection=["rect_test_a", "rect_test_b"],
            parameters={"distance": 60.0, "unit": "mm", "anchor": "point_a"},
        )
    )

    coords = _coords_by_id(result.after)
    assert coords["rect_test_b"] == pytest.approx((70.0, 20.0))
    assert coords["rect_test_c"] == pytest.approx((50.0, 45.0))

    top = result.after.get_entity("rect_test_ab")
    right = result.after.get_entity("rect_test_bc")
    bottom = result.after.get_entity("rect_test_cd")
    profile = result.after.get_entity("profile_rect_test")
    assert top.end == pytest.approx((50.0, 20.0))
    assert right.start == pytest.approx((50.0, 20.0))
    assert right.end == pytest.approx((50.0, 45.0))
    assert bottom.start == pytest.approx((50.0, 45.0))
    assert profile.vertices == [(10.0, 20.0), (50.0, 20.0), (50.0, 45.0), (10.0, 45.0), (10.0, 20.0)]


def test_set_rectangle_dimension_preview_updates_points_edges_and_profile_without_commit() -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())

    result = session.execute(
        _command(
            "set_rectangle_dimension",
            "cmd_rect_width_preview",
            selection=["rect_test_ab"],
            parameters={"dimension": "width", "value": 60.0, "unit": "mm"},
        )
    )

    assert result.status == "preview"
    assert result.value == pytest.approx(60.0)
    assert result.metadata["solver_status"] == "underconstrained"
    assert _coords_by_id(session.state)["rect_test_c"] == pytest.approx((50.0, 45.0))
    assert _coords_by_id(result.after) == {
        "rect_test_a": (10.0, 20.0),
        "rect_test_b": pytest.approx((70.0, 20.0)),
        "rect_test_c": pytest.approx((70.0, 45.0)),
        "rect_test_d": (10.0, 45.0),
    }
    assert result.after.get_entity("rect_test_ab").end == pytest.approx((70.0, 20.0))
    assert result.after.get_entity("rect_test_bc").start == pytest.approx((70.0, 20.0))
    assert result.after.get_entity("rect_test_bc").end == pytest.approx((70.0, 45.0))
    assert result.after.get_entity("rect_test_cd").start == pytest.approx((70.0, 45.0))
    assert result.after.get_entity("profile_rect_test").vertices == [
        (10.0, 20.0),
        (70.0, 20.0),
        (70.0, 45.0),
        (10.0, 45.0),
        (10.0, 20.0),
    ]


def test_set_rectangle_dimension_commit_and_revert_keep_rectangle_semantic() -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())

    result = session.execute(
        _command(
            "set_rectangle_dimension",
            "cmd_rect_height_commit",
            mode="commit",
            selection=["profile_rect_test"],
            parameters={"dimension": "height", "value": 15.0, "unit": "mm"},
        )
    )

    assert result.status == "committed"
    assert _coords_by_id(session.state)["rect_test_c"] == pytest.approx((50.0, 35.0))
    assert session.state.get_entity("rect_test_bc").end == pytest.approx((50.0, 35.0))
    assert session.state.get_entity("profile_rect_test").vertices == [
        (10.0, 20.0),
        (50.0, 20.0),
        (50.0, 35.0),
        (10.0, 35.0),
        (10.0, 20.0),
    ]

    reverted = session.revert()

    assert _coords_by_id(reverted)["rect_test_c"] == pytest.approx((50.0, 45.0))
    assert reverted.get_entity("profile_rect_test").vertices == [
        (10.0, 20.0),
        (50.0, 20.0),
        (50.0, 45.0),
        (10.0, 45.0),
        (10.0, 20.0),
    ]


def test_add_profile_hole_preview_does_not_mutate_session() -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())

    result = session.execute(
        _command(
            "add_profile_hole",
            "cmd_add_hole_preview",
            selection=["profile_rect_test"],
            parameters={"diameter": 8.0, "unit": "mm", "center": [30.0, 32.5]},
        )
    )

    assert result.status == "preview"
    assert "hole_profile_rect_test_cmd_add_hole_preview" in result.changed_entity_ids
    assert result.after.get_entity("profile_rect_test").holes == ["hole_profile_rect_test_cmd_add_hole_preview"]
    hole = result.after.get_entity("hole_profile_rect_test_cmd_add_hole_preview")
    assert hole.type == "profile_2d"
    assert hole.closed is True
    assert hole.area == pytest.approx(50.265, rel=1e-2)
    assert session.state.get_entity("profile_rect_test").holes == []
    assert "hole_profile_rect_test_cmd_add_hole_preview" not in {item.id for item in session.state.items}
    assert session.history.records[-1].command.command_type == "batch"


def test_add_profile_hole_commit_persists_hole_profile_and_replayable_history() -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())

    result = session.execute(
        _command(
            "add_profile_hole",
            "cmd_add_hole_commit",
            mode="commit",
            selection=["profile_rect_test"],
            parameters={"diameter": 8.0, "unit": "mm", "center": [30.0, 32.5]},
        )
    )

    hole_id = "hole_profile_rect_test_cmd_add_hole_commit"
    assert result.status == "committed"
    assert session.state.get_entity("profile_rect_test").holes == [hole_id]
    assert session.state.get_entity(hole_id).winding == "clockwise"
    assert session.history.records[-1].command.command_type == "add_profile_hole"
    assert session.history.replay(session.initial_state).get_entity("profile_rect_test").holes == [hole_id]


def test_update_profile_hole_commit_replaces_existing_hole_geometry() -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())
    session.execute(
        _command(
            "add_profile_hole",
            "cmd_add_hole_commit",
            mode="commit",
            selection=["profile_rect_test"],
            parameters={"diameter": 8.0, "unit": "mm", "center": [30.0, 32.5]},
        )
    )

    hole_id = "hole_profile_rect_test_cmd_add_hole_commit"
    result = session.execute(
        _command(
            "update_profile_hole",
            "cmd_update_hole_commit",
            mode="commit",
            selection=["profile_rect_test", hole_id],
            parameters={"diameter": 6.0, "unit": "mm", "center": [28.0, 32.5]},
        )
    )

    updated_hole = session.state.get_entity(hole_id)
    assert result.status == "committed"
    assert result.changed_entity_ids == ["profile_rect_test", hole_id]
    assert result.metadata["diameter"] == 6.0
    assert result.metadata["center"] == [28.0, 32.5]
    assert updated_hole.area == pytest.approx(28.274, rel=1e-2)
    assert session.state.get_entity("profile_rect_test").holes == [hole_id]
    assert session.history.records[-1].command.command_type == "update_profile_hole"
    assert session.history.replay(session.initial_state).get_entity("profile_rect_test").holes == [hole_id]


def test_update_profile_hole_invalid_diameter_is_structured() -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())
    session.execute(
        _command(
            "add_profile_hole",
            "cmd_add_hole_commit",
            mode="commit",
            selection=["profile_rect_test"],
            parameters={"diameter": 8.0, "unit": "mm", "center": [30.0, 32.5]},
        )
    )

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "update_profile_hole",
                "cmd_update_hole_invalid",
                mode="commit",
                selection=["profile_rect_test", "hole_profile_rect_test_cmd_add_hole_commit"],
                parameters={"diameter": 0.0, "unit": "mm", "center": [30.0, 32.5]},
            )
        )

    payload = exc_info.value.to_dict()
    assert payload["code"] == "selection_resolution_error"
    assert payload["detail"]["error_code"] == "invalid_hole_diameter"


@pytest.mark.parametrize(
    ("selection", "parameters", "error_code", "detail_code"),
    [
        ([], {"diameter": 8.0, "unit": "mm", "center": [30.0, 32.5]}, "selection_resolution_error", "missing_profile_selection"),
        (["profile_rect_test"], {"diameter": 0.0, "unit": "mm", "center": [30.0, 32.5]}, "selection_resolution_error", "invalid_hole_diameter"),
        (["profile_rect_test"], {"diameter": 8.0, "unit": "mm", "center": [80.0, 32.5]}, "selection_resolution_error", "hole_outside_outer"),
        (["profile_rect_test"], {"diameter": 40.0, "unit": "mm", "center": [30.0, 32.5]}, "selection_resolution_error", "profile_intersection"),
    ],
)
def test_add_profile_hole_invalid_cases_are_structured(selection, parameters, error_code, detail_code) -> None:
    session = _session([])
    session.execute(_rectangle_batch_command())

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "add_profile_hole",
                "cmd_add_hole_invalid",
                selection=selection,
                parameters=parameters,
            )
        )

    payload = exc_info.value.to_dict()
    assert payload["code"] == error_code
    assert payload["detail"]["error_code"] == detail_code


def test_revert_restores_prior_state() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False},
        ]
    )

    session.execute(
        _command(
            "set_distance",
            "cmd_revert",
            mode="commit",
            selection=["point_A", "point_B"],
            parameters={"distance": 6.0, "unit": "mm", "anchor": "point_A"},
        )
    )
    assert session.state.items[1].coords == pytest.approx((6.0, 0.0))

    reverted = session.revert()
    assert reverted.items[1].coords == pytest.approx((1.0, 0.0))
    assert session.state.items[1].coords == pytest.approx((1.0, 0.0))
    assert session.history.records == []


@pytest.mark.parametrize(
    ("command_type", "selection", "parameters", "error_code"),
    [
        ("set_distance", ["missing_A", "point_B"], {"distance": 4.0, "unit": "mm", "anchor": "point_A"}, "missing_entity"),
        ("measure_distance", ["point_A", "line_B"], {"unit": "mm"}, "wrong_entity_type"),
        ("set_line_polar", ["point_A", "point_B"], {"start": "point_A", "end": "point_B", "angle": 0.0, "angle_unit": "deg"}, "missing_parameter"),
        ("set_distance", ["point_A", "point_B"], {"distance": 4.0, "unit": "furlong", "anchor": "point_A"}, "invalid_units"),
    ],
)
def test_structured_errors_cover_validation_failures(command_type, selection, parameters, error_code) -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False},
            {"id": "line_B", "type": "line_2d", "start": [0, 0], "end": [1, 0], "locked": False},
        ]
    )

    command = _command(command_type, "cmd_error", selection=selection, parameters=parameters)

    with pytest.raises(Exception) as exc_info:
        session.execute(command)

    assert hasattr(exc_info.value, "to_dict")
    assert exc_info.value.to_dict()["code"] == error_code


def test_executor_defensively_rejects_unvalidated_command_type() -> None:
    from sketchmath.models.geometry_command import GeometryCommand

    session = _session([])
    command = GeometryCommand.model_construct(
        version="0.1",
        command_id="cmd_unsupported",
        mode="preview",
        command_type="unsupported",
        selection=[],
        parameters={},
    )

    with pytest.raises(Exception) as exc_info:
        session.execute(command)

    assert hasattr(exc_info.value, "to_dict")
    assert exc_info.value.to_dict()["code"] == "unsupported_command_type"


def test_locked_entity_mutation_raises_structured_error() -> None:
    session = _session(
        [
            {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True},
            {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False},
        ]
    )

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "set_distance",
                "cmd_locked",
                mode="commit",
                selection=["point_A", "point_B"],
                parameters={"distance": 5.0, "unit": "mm", "anchor": "midpoint"},
            )
        )

    assert exc_info.value.to_dict()["code"] == "locked_entity_mutation"
