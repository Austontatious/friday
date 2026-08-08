from __future__ import annotations

import pytest

from sketchmath.executor.command_router import GeometrySession
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext


def _command(command_type: str, command_id: str, *, selection: list[str] | None = None, parameters: dict[str, object] | None = None, mode: str = "commit") -> GeometryCommand:
    return GeometryCommand(
        version="0.7",
        command_id=command_id,
        mode=mode,
        command_type=command_type,
        selection=selection or [],
        parameters=parameters or {},
    )


def _session(items: list[dict[str, object]], constraints: list[dict[str, object]] | None = None) -> GeometrySession:
    return GeometrySession(
        SelectionContext.model_validate(
            {
                "selection_set_id": "construction_geometry",
                "units": "mm",
                "frame": "canvas_2d",
                "items": items,
                "constraints": constraints or [],
                "named_references": {},
            }
        )
    )


def test_define_commands_create_canonical_construction_geometry() -> None:
    session = _session([])
    point = session.execute(
        _command("define_point", "point", parameters={"name": "guide_point", "coords": [2, 3], "construction": True})
    )
    assert point.after.get_entity("guide_point").construction is True

    line = session.execute(
        _command(
            "define_line",
            "line",
            parameters={"name": "centerline", "start": [0, 0], "end": [10, 0], "construction": True},
        )
    )
    assert line.after.get_entity("centerline").type == "construction_line_2d"


def test_set_construction_preserves_ids_constraints_and_preview_is_non_mutating() -> None:
    session = _session(
        [
            {"id": "a", "type": "point_2d", "coords": [0, 0]},
            {"id": "b", "type": "point_2d", "coords": [8, 0]},
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [8, 0], "start_point_id": "a", "end_point_id": "b"},
        ],
        [{"id": "horizontal", "type": "horizontal_constraint", "points": ["a", "b"]}],
    )
    preview = session.execute(_command("set_construction", "preview", selection=["a", "line"], mode="preview"))
    assert preview.after.get_entity("a").construction is True
    assert preview.after.get_entity("line").type == "construction_line_2d"
    assert session.state.get_entity("a").construction is False
    assert session.state.get_entity("line").type == "line_2d"

    committed = session.execute(_command("set_construction", "commit", selection=["a", "line"]))
    assert committed.after.get_entity("a").construction is True
    assert committed.after.get_entity("line").type == "construction_line_2d"
    assert committed.after.constraints[0].points == ("a", "b")

    regular = session.execute(_command("set_construction", "regular", selection=["a", "line"], parameters={"enabled": False}))
    assert regular.after.get_entity("a").construction is False
    assert regular.after.get_entity("line").type == "line_2d"


def test_profile_source_line_cannot_be_silently_converted() -> None:
    session = _session(
        [
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [8, 0]},
            {
                "id": "profile",
                "type": "profile_2d",
                "vertices": [[0, 0], [8, 0], [0, 4], [0, 0]],
                "area": 16,
                "winding": "counterclockwise",
                "source_line_ids": ["line"],
            },
        ]
    )
    with pytest.raises(Exception) as error:
        session.execute(_command("set_construction", "blocked", selection=["line"]))
    assert error.value.to_dict()["code"] == "selection_resolution_error"
    assert session.state.get_entity("line").type == "line_2d"
    assert session.history.records == []


def test_set_construction_rejects_non_reference_geometry() -> None:
    session = _session([{"id": "circle", "type": "circle_2d", "center": [0, 0], "radius": 2}])
    with pytest.raises(Exception) as error:
        session.execute(_command("set_construction", "wrong_type", selection=["circle"]))
    assert error.value.to_dict()["code"] == "wrong_entity_type"
    assert session.history.records == []
