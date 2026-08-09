from __future__ import annotations

import math

import pytest

from sketchmath.executor.command_router import GeometrySession
from sketchmath.executor.errors import SelectionResolutionError
from sketchmath.models.entities import Arc2DEntity, Circle2DEntity, Line2DEntity, Point2DEntity, Profile2DEntity
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext


def _session(items: list[dict] | None = None, *, constraints: list[dict] | None = None) -> GeometrySession:
    return GeometrySession(
        SelectionContext(
            selection_set_id="gate_b_editing",
            units="mm",
            items=items or [],
            constraints=constraints or [],
        )
    )


def _command(
    command_type: str,
    command_id: str,
    selection: list[str] | None = None,
    parameters: dict | None = None,
    *,
    mode: str = "commit",
) -> GeometryCommand:
    return GeometryCommand(
        version="0.8",
        command_id=command_id,
        mode=mode,
        command_type=command_type,
        selection=selection or [],
        parameters=parameters or {},
    )


def test_regular_polygon_is_a_stable_point_line_profile_bundle() -> None:
    session = _session()
    preview = session.execute(
        _command(
            "define_regular_polygon",
            "polygon_preview",
            parameters={"name": "hex", "center": [10, 20], "radius": 8, "sides": 6},
            mode="preview",
        )
    )
    assert len(preview.after.items) == 13
    assert session.state.items == []

    result = session.execute(
        _command(
            "define_regular_polygon",
            "polygon_commit",
            parameters={"name": "hex", "center": [10, 20], "radius": 8, "sides": 6},
        )
    )

    profile = result.after.get_entity("profile_hex")
    assert isinstance(profile, Profile2DEntity)
    assert profile.source_curve_ids == [f"hex_e{index}" for index in range(1, 7)]
    assert profile.source_line_ids == profile.source_curve_ids
    assert profile.area == pytest.approx(3 * math.sqrt(3) * 8**2 / 2)
    assert len([entity for entity in result.after.items if isinstance(entity, Point2DEntity)]) == 6
    assert len([entity for entity in result.after.items if isinstance(entity, Line2DEntity)]) == 6


def test_slot_uses_two_lines_two_finite_arcs_and_a_curve_backed_profile() -> None:
    session = _session()
    result = session.execute(
        _command(
            "define_slot",
            "slot_commit",
            parameters={"name": "mount_slot", "start": [0, 0], "end": [20, 0], "width": 8},
        )
    )

    profile = result.after.get_entity("profile_mount_slot")
    assert isinstance(profile, Profile2DEntity)
    assert profile.source_curve_ids == [
        "mount_slot_positive",
        "mount_slot_end_arc",
        "mount_slot_negative",
        "mount_slot_start_arc",
    ]
    assert profile.area == pytest.approx(20 * 8 + math.pi * 4**2, rel=0.01)
    arcs = [result.after.get_entity("mount_slot_end_arc"), result.after.get_entity("mount_slot_start_arc")]
    assert all(isinstance(arc, Arc2DEntity) and arc.sweep_angle_deg == -180.0 for arc in arcs)
    assert result.metadata["primitive"] == "slot"


def test_split_line_preserves_source_id_and_records_lineage() -> None:
    session = _session(
        [
            {"id": "a", "type": "point_2d", "coords": [0, 0]},
            {"id": "b", "type": "point_2d", "coords": [10, 0]},
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [10, 0], "start_point_id": "a", "end_point_id": "b"},
        ]
    )
    result = session.execute(_command("split_line", "split", ["line"], {"parameter": 0.25}))

    source = result.after.get_entity("line")
    split = result.after.get_entity("split_split_point")
    remainder = result.after.get_entity("split_split_line")
    assert isinstance(source, Line2DEntity) and source.end == pytest.approx((2.5, 0.0))
    assert isinstance(split, Point2DEntity) and split.coords == pytest.approx((2.5, 0.0))
    assert isinstance(remainder, Line2DEntity) and remainder.start_point_id == split.id and remainder.end_point_id == "b"
    assert result.metadata["result_line_ids"] == ["line", "split_split_line"]


def test_trim_and_extend_require_finite_cutter_contact() -> None:
    trim = _session(
        [
            {"id": "target", "type": "line_2d", "start": [0, 0], "end": [10, 0]},
            {"id": "cutter", "type": "line_2d", "start": [6, -5], "end": [6, 5]},
        ]
    )
    trimmed = trim.execute(_command("trim_line", "trim", ["target", "cutter"], {"keep": "start"}))
    assert trimmed.after.get_entity("target").end == pytest.approx((6.0, 0.0))

    extend = _session(
        [
            {"id": "target", "type": "line_2d", "start": [0, 0], "end": [4, 0]},
            {"id": "cutter", "type": "line_2d", "start": [6, -5], "end": [6, 5]},
        ]
    )
    extended = extend.execute(_command("extend_line", "extend", ["target", "cutter"]))
    assert extended.after.get_entity("target").end == pytest.approx((6.0, 0.0))

    miss = _session(
        [
            {"id": "target", "type": "line_2d", "start": [0, 0], "end": [4, 0]},
            {"id": "cutter", "type": "line_2d", "start": [6, 5], "end": [6, 8]},
        ]
    )
    with pytest.raises(SelectionResolutionError) as exc_info:
        miss.execute(_command("extend_line", "miss", ["target", "cutter"]))
    assert exc_info.value.detail["error_code"] == "cutter_misses_segment"


def test_referenced_curve_edit_fails_without_partial_topology_mutation() -> None:
    session = _session(
        [
            {"id": "a", "type": "point_2d", "coords": [0, 0]},
            {"id": "b", "type": "point_2d", "coords": [10, 0]},
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [10, 0], "start_point_id": "a", "end_point_id": "b"},
            {
                "id": "profile",
                "type": "profile_2d",
                "vertices": [[0, 0], [10, 0], [0, 0]],
                "area": 0,
                "winding": "degenerate",
                "source_line_ids": ["line"],
                "source_curve_ids": ["line"],
            },
        ]
    )
    before = session.state.model_dump(mode="json")
    with pytest.raises(SelectionResolutionError) as exc_info:
        session.execute(_command("split_line", "blocked", ["line"]))
    assert exc_info.value.detail["error_code"] == "unsafe_referenced_curve_edit"
    assert session.state.model_dump(mode="json") == before


def test_offset_creates_independent_line_circle_and_arc_geometry() -> None:
    session = _session(
        [
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [10, 0]},
            {"id": "circle", "type": "circle_2d", "center": [0, 0], "radius": 5},
            {"id": "arc", "type": "arc_2d", "center": [0, 0], "radius": 4, "start_angle_deg": 0, "sweep_angle_deg": 90, "construction": "center"},
        ]
    )
    line_result = session.execute(_command("offset_curve", "line", ["line"], {"distance": 2, "side": "left", "name": "line_offset"}))
    line = line_result.after.get_entity("line_offset")
    assert isinstance(line, Line2DEntity) and line.start == pytest.approx((0.0, 2.0)) and line.end == pytest.approx((10.0, 2.0))

    circle_result = session.execute(_command("offset_curve", "circle", ["circle"], {"distance": 2, "side": "right", "name": "circle_offset"}))
    circle = circle_result.after.get_entity("circle_offset")
    assert isinstance(circle, Circle2DEntity) and circle.radius == pytest.approx(3.0)

    arc_result = session.execute(_command("offset_curve", "arc", ["arc"], {"distance": 2, "side": "left", "name": "arc_offset"}))
    arc = arc_result.after.get_entity("arc_offset")
    assert isinstance(arc, Arc2DEntity) and arc.radius == pytest.approx(6.0) and arc.start_point_id is None


def test_linked_line_transform_and_copy_preserve_canonical_point_references() -> None:
    session = _session(
        [
            {"id": "a", "type": "point_2d", "coords": [0, 0]},
            {"id": "b", "type": "point_2d", "coords": [10, 0]},
            {"id": "line", "type": "line_2d", "start": [0, 0], "end": [10, 0], "start_point_id": "a", "end_point_id": "b"},
        ]
    )
    translated = session.execute(
        GeometryCommand(version="0.2", command_id="move", mode="commit", command_type="translate", selection=["line"], parameters={"vector": [3, 4]})
    )
    assert translated.after.get_entity("a").coords == pytest.approx((3.0, 4.0))
    assert translated.after.get_entity("b").coords == pytest.approx((13.0, 4.0))
    assert translated.after.get_entity("line").start == pytest.approx((3.0, 4.0))

    copied = session.execute(
        GeometryCommand(
            version="0.2",
            command_id="pattern",
            mode="commit",
            command_type="copy_linear",
            selection=["line"],
            parameters={"vector": [0, 5], "count": 2, "id_prefix": "pattern"},
        )
    )
    first_line = copied.after.get_entity("pattern_pattern_1_line")
    assert isinstance(first_line, Line2DEntity)
    assert first_line.start_point_id == "pattern_pattern_1_a"
    assert first_line.end_point_id == "pattern_pattern_1_b"
    assert copied.after.get_entity(first_line.start_point_id).coords == pytest.approx((3.0, 9.0))


def test_slot_profile_mirror_and_linear_pattern_keep_curve_bundles_connected() -> None:
    session = _session()
    session.execute(_command("define_slot", "slot", parameters={"name": "slot", "start": [0, 0], "end": [20, 0], "width": 8}))
    mirrored = session.execute(
        GeometryCommand(version="0.2", command_id="mirror", mode="commit", command_type="mirror", selection=["profile_slot"], parameters={"axis_x": 10})
    )
    mirrored_profile = mirrored.after.get_entity("profile_slot")
    assert isinstance(mirrored_profile, Profile2DEntity)
    assert mirrored_profile.area == pytest.approx(20 * 8 + math.pi * 4**2, rel=0.01)

    patterned = session.execute(
        GeometryCommand(
            version="0.2",
            command_id="pattern_slot",
            mode="commit",
            command_type="copy_linear",
            selection=["profile_slot"],
            parameters={"vector": [0, 20], "count": 1, "id_prefix": "pattern"},
        )
    )
    copied_profile = patterned.after.get_entity("pattern_pattern_slot_1_profile_slot")
    assert isinstance(copied_profile, Profile2DEntity)
    assert copied_profile.source_curve_ids == [
        "pattern_pattern_slot_1_slot_positive",
        "pattern_pattern_slot_1_slot_end_arc",
        "pattern_pattern_slot_1_slot_negative",
        "pattern_pattern_slot_1_slot_start_arc",
    ]
    assert copied_profile.area == pytest.approx(mirrored_profile.area)
