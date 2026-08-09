from __future__ import annotations

import math

import pytest

from sketchmath.executor.command_router import GeometrySession
from sketchmath.executor.errors import CommandValidationError, SelectionResolutionError, SolverError
from sketchmath.geometry.topology import detect_planar_regions
from sketchmath.models.entities import Profile2DEntity
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext


def _line(entity_id: str, start: tuple[float, float], end: tuple[float, float]) -> dict:
    return {"id": entity_id, "type": "line_2d", "start": start, "end": end}


def _loop(prefix: str, minimum: float, maximum: float) -> list[dict]:
    a = (minimum, minimum)
    b = (maximum, minimum)
    c = (maximum, maximum)
    d = (minimum, maximum)
    return [
        _line(f"{prefix}_bottom", a, b),
        _line(f"{prefix}_right", b, c),
        _line(f"{prefix}_top", c, d),
        _line(f"{prefix}_left", d, a),
    ]


def _state(items: list[dict]) -> SelectionContext:
    return SelectionContext(selection_set_id="general_topology", units="mm", items=items)


def _diagnostic_codes(result) -> set[str]:
    return {diagnostic.code for diagnostic in result.diagnostics}


def _command(command_type: str, command_id: str, parameters: dict | None = None, *, mode: str = "preview") -> GeometryCommand:
    return GeometryCommand(
        version="0.9",
        command_id=command_id,
        command_type=command_type,
        mode=mode,
        parameters=parameters or {},
    )


def test_disconnected_loops_have_stable_region_ids_independent_of_input_order() -> None:
    items = [*_loop("left", 0, 4), *_loop("right", 10, 14)]
    first = detect_planar_regions(_state(items))
    second = detect_planar_regions(_state(list(reversed(items))))

    assert [region.region_id for region in first.regions] == [region.region_id for region in second.regions]
    assert [region.area for region in first.regions] == pytest.approx([16.0, 16.0])
    assert all(region.outer_loop.winding == "counterclockwise" and not region.holes for region in first.regions)
    assert "disconnected_components" in _diagnostic_codes(first)


def test_nested_loops_produce_annuli_holes_and_island_depths() -> None:
    result = detect_planar_regions(_state([*_loop("outer", 0, 10), *_loop("middle", 2, 8), *_loop("inner", 4, 6)]))
    ordered = sorted(result.regions, key=lambda region: region.area, reverse=True)

    assert [region.area for region in ordered] == pytest.approx([64.0, 32.0, 4.0])
    assert [len(region.holes) for region in ordered] == [1, 1, 0]
    assert [region.nesting_depth for region in ordered] == [0, 1, 2]
    assert all(region.outer_loop.winding == "counterclockwise" for region in ordered)
    assert all(hole.winding == "clockwise" for region in ordered for hole in region.holes)


def test_outer_region_preserves_multiple_disjoint_holes() -> None:
    result = detect_planar_regions(
        _state([*_loop("outer", 0, 20), *_loop("left_hole", 2, 6), *_loop("right_hole", 12, 16)])
    )
    outer = max(result.regions, key=lambda region: region.area)

    assert outer.area == pytest.approx(368.0)
    assert len(outer.holes) == 2
    assert [hole.area for hole in outer.holes] == pytest.approx([16.0, 16.0])
    assert outer.outer_loop.winding == "counterclockwise"
    assert all(hole.winding == "clockwise" for hole in outer.holes)


def test_shared_edge_builds_two_regions_and_preserves_shared_source_lineage() -> None:
    items = [
        _line("bottom", (0, 0), (20, 0)),
        _line("right", (20, 0), (20, 10)),
        _line("top", (20, 10), (0, 10)),
        _line("left", (0, 10), (0, 0)),
        _line("divider", (10, 0), (10, 10)),
    ]
    result = detect_planar_regions(_state(items))

    assert len(result.regions) == 2
    assert [region.area for region in result.regions] == pytest.approx([100.0, 100.0])
    assert all("divider" in region.source_curve_ids for region in result.regions)


def test_open_branch_does_not_destroy_a_valid_region() -> None:
    result = detect_planar_regions(_state([*_loop("box", 0, 10), _line("branch", (10, 5), (15, 5))]))

    assert len(result.regions) == 1
    assert result.regions[0].area == pytest.approx(100.0)
    assert {"t_junction", "open_branches"}.intersection(_diagnostic_codes(result))


def test_intersecting_curves_are_noded_into_deterministic_faces() -> None:
    items = [
        *_loop("box", 0, 10),
        _line("vertical", (5, 0), (5, 10)),
        _line("horizontal", (0, 5), (10, 5)),
    ]
    result = detect_planar_regions(_state(items))

    assert len(result.regions) == 4
    assert [region.area for region in result.regions] == pytest.approx([25.0] * 4)
    assert {"curve_intersection", "t_junction"}.intersection(_diagnostic_codes(result))


def test_point_selection_distinguishes_inside_boundary_and_outside() -> None:
    state = _state(_loop("box", 0, 10))
    inside = detect_planar_regions(state, selection_point=(4, 4))
    boundary = detect_planar_regions(state, selection_point=(0, 4))
    outside = detect_planar_regions(state, selection_point=(20, 20))

    assert inside.selection.status == "selected"
    assert inside.selection.region_ids == [inside.regions[0].region_id]
    assert boundary.selection.status == "boundary"
    assert boundary.selection.boundary_region_ids == [boundary.regions[0].region_id]
    assert outside.selection.status == "none"


def test_touching_loops_remain_distinct_regions() -> None:
    result = detect_planar_regions(_state([*_loop("left", 0, 4), *_loop("right", 4, 8)]))

    assert len(result.regions) == 2
    assert [region.area for region in result.regions] == pytest.approx([16.0, 16.0])


def test_overlapping_duplicate_edge_is_diagnosed_without_duplicate_region() -> None:
    result = detect_planar_regions(_state([*_loop("box", 0, 10), _line("duplicate_bottom", (0, 0), (10, 0))]))

    assert len(result.regions) == 1
    assert result.regions[0].area == pytest.approx(100.0)
    assert "overlapping_curves" in _diagnostic_codes(result)


def test_near_vertex_gap_is_not_silently_snapped() -> None:
    items = [
        _line("bottom", (0, 0), (10, 0)),
        _line("right", (10, 0), (10, 10)),
        _line("top", (10, 10), (0, 10)),
        _line("left", (0, 10), (0, 0.000001)),
    ]
    result = detect_planar_regions(_state(items))

    assert result.regions == []
    assert "near_vertex_gap" in _diagnostic_codes(result)
    assert "no_bounded_regions" in _diagnostic_codes(result)


def test_bow_tie_self_intersection_yields_two_explicit_faces() -> None:
    items = [
        _line("a", (0, 0), (10, 10)),
        _line("b", (10, 10), (0, 10)),
        _line("c", (0, 10), (10, 0)),
        _line("d", (10, 0), (0, 0)),
    ]
    result = detect_planar_regions(_state(items))

    assert len(result.regions) == 2
    assert [region.area for region in result.regions] == pytest.approx([25.0, 25.0])
    assert "curve_intersection" in _diagnostic_codes(result)


def test_nested_circles_produce_annulus_and_inner_disk() -> None:
    result = detect_planar_regions(
        _state(
            [
                {"id": "outer", "type": "circle_2d", "center": (0, 0), "radius": 10},
                {"id": "inner", "type": "circle_2d", "center": (0, 0), "radius": 4},
            ]
        )
    )
    ordered = sorted(result.regions, key=lambda region: region.area, reverse=True)

    assert len(ordered) == 2
    assert ordered[0].area == pytest.approx(math.pi * (10**2 - 4**2), rel=0.001)
    assert ordered[1].area == pytest.approx(math.pi * 4**2, rel=0.001)
    assert len(ordered[0].holes) == 1


def test_finite_arc_and_diameter_form_a_region() -> None:
    result = detect_planar_regions(
        _state(
            [
                {
                    "id": "arc",
                    "type": "arc_2d",
                    "center": (0, 0),
                    "radius": 10,
                    "start_angle_deg": 0,
                    "sweep_angle_deg": 180,
                    "construction": "center",
                },
                _line("diameter", (-10, 0), (10, 0)),
            ]
        )
    )

    assert len(result.regions) == 1
    assert result.regions[0].area == pytest.approx(math.pi * 10**2 / 2, rel=0.001)
    assert result.regions[0].source_curve_ids == ["arc", "diameter"]


def test_detect_and_select_region_commands_are_preview_only_and_typed() -> None:
    session = GeometrySession(_state(_loop("box", 0, 10)))
    detected = session.execute(_command("detect_regions", "detect"))
    selected = session.execute(_command("select_region", "select", {"point": [5, 5]}))

    assert detected.metadata["topology"]["schema_version"] == "1.0"
    assert detected.metadata["region_count"] == 1
    assert selected.metadata["selection"]["status"] == "selected"
    assert session.history.cursor == 0
    with pytest.raises(CommandValidationError):
        session.execute(_command("detect_regions", "bad_commit", mode="commit"))


def test_make_region_profile_promotes_outer_and_hole_profiles_atomically() -> None:
    state = _state([*_loop("outer", 0, 10), *_loop("inner", 3, 7)])
    region = max(detect_planar_regions(state).regions, key=lambda candidate: candidate.area)
    session = GeometrySession(state)
    result = session.execute(
        _command(
            "make_region_profile",
            "promote",
            {"region_id": region.region_id, "name": "profile_annulus"},
            mode="commit",
        )
    )

    outer = result.after.get_entity("profile_annulus")
    assert isinstance(outer, Profile2DEntity)
    assert outer.area == pytest.approx(100.0)
    assert len(outer.holes) == 1
    hole = result.after.get_entity(outer.holes[0])
    assert isinstance(hole, Profile2DEntity)
    assert hole.area == pytest.approx(16.0)
    assert hole.winding == "clockwise"
    assert result.value == pytest.approx(84.0)
    assert result.metadata["region_id"] == region.region_id
    assert session.history.cursor == 1
    session.revert()
    assert all(not isinstance(entity, Profile2DEntity) for entity in session.state.items)


def test_make_region_profile_accepts_point_selection_and_rejects_stale_id() -> None:
    session = GeometrySession(_state(_loop("box", 0, 10)))
    promoted = session.execute(
        _command(
            "make_region_profile",
            "point_promote",
            {"point": [5, 5], "name": "profile_from_point"},
            mode="commit",
        )
    )
    assert promoted.after.get_entity("profile_from_point").type == "profile_2d"

    before = session.state.model_dump(mode="json")
    with pytest.raises(SelectionResolutionError) as exc_info:
        session.execute(
            _command(
                "make_region_profile",
                "stale",
                {"region_id": "region_stale"},
                mode="commit",
            )
        )
    assert exc_info.value.detail["error_code"] == "stale_region_reference"
    assert session.state.model_dump(mode="json") == before


def test_topology_profile_reference_tracks_bundle_transform_and_rejects_broken_boundary() -> None:
    session = GeometrySession(_state(_loop("box", 0, 10)))
    promoted = session.execute(
        _command(
            "make_region_profile",
            "promote",
            {"point": [5, 5], "name": "profile_box"},
            mode="commit",
        )
    )
    source_region_id = promoted.after.get_entity("profile_box").source_region_id
    translated = session.execute(
        GeometryCommand(
            version="0.2",
            command_id="translate_profile",
            command_type="translate",
            mode="commit",
            selection=["profile_box"],
            parameters={"vector": [5, 2]},
        )
    )
    moved = translated.after.get_entity("profile_box")
    assert moved.source_region_id != source_region_id
    assert min(x for x, _ in moved.vertices) == pytest.approx(5.0)
    assert min(y for _, y in moved.vertices) == pytest.approx(2.0)

    before = session.state.model_dump(mode="json")
    with pytest.raises(SolverError) as exc_info:
        session.execute(
            GeometryCommand(
                version="0.1",
                command_id="break_boundary",
                command_type="define_line",
                mode="commit",
                parameters={"name": "box_top", "start": [15, 12], "end": [6, 11]},
            )
        )
    assert exc_info.value.detail["error_code"] == "topology_region_reference_missing"
    assert session.state.model_dump(mode="json") == before
