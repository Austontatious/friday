from __future__ import annotations

import math

import pytest

from sketchmath.executor.errors import FeatureRebuildError, RevisionConflictError, SelectionResolutionError
from sketchmath.features.executor import apply_feature_command
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import FeatureRecord, SketchMathDocument, wrap_legacy_selection_context
from sketchmath.models.feature_command import FeatureCommand
from sketchmath.models.selection_context import SelectionContext


def _selection() -> SelectionContext:
    return SelectionContext.model_validate(
        {
            "selection_set_id": "feature_history",
            "units": "mm",
            "items": [
                {
                    "id": "profile_plate_hole",
                    "type": "profile_2d",
                    "vertices": [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]],
                    "area": 16,
                    "winding": "clockwise",
                    "source_region_id": "region_plate",
                },
                {
                    "id": "profile_plate",
                    "type": "profile_2d",
                    "vertices": [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                    "area": 100,
                    "winding": "counterclockwise",
                    "holes": ["profile_plate_hole"],
                    "source_region_id": "region_plate",
                },
                {
                    "id": "profile_boss",
                    "type": "profile_2d",
                    "vertices": [[2, 2], [8, 2], [8, 8], [2, 8], [2, 2]],
                    "area": 36,
                    "winding": "counterclockwise",
                    "source_region_id": "region_boss",
                },
                {
                    "id": "profile_revolve_add",
                    "type": "profile_2d",
                    "vertices": [[8, 2], [10, 2], [10, 8], [8, 8], [8, 2]],
                    "area": 12,
                    "winding": "counterclockwise",
                },
                {
                    "id": "profile_revolve_cut",
                    "type": "profile_2d",
                    "vertices": [[4, 2], [6, 2], [6, 8], [4, 8], [4, 2]],
                    "area": 12,
                    "winding": "counterclockwise",
                },
                {
                    "id": "profile_cross_axis",
                    "type": "profile_2d",
                    "vertices": [[-2, 2], [2, 2], [2, 8], [-2, 8], [-2, 2]],
                    "area": 24,
                    "winding": "counterclockwise",
                },
                {
                    "id": "axis_y",
                    "type": "axis_2d",
                    "origin": [0, 0],
                    "direction": [0, 1],
                },
            ],
        }
    )


def _document() -> SketchMathDocument:
    return wrap_legacy_selection_context(_selection(), document_id="doc_feature_history")


def _feature(
    feature_id: str,
    *,
    profile_id: str = "profile_plate",
    operation: str = "new_body",
    dependencies: list[str] | None = None,
    depth: float = 10,
    extent: str = "one_sided",
    second_depth: float | None = None,
    direction: str = "positive",
    topology_references: list[dict] | None = None,
) -> FeatureRecord:
    return FeatureRecord.model_validate(
        {
            "feature_id": feature_id,
            "name": feature_id.replace("_", " ").title(),
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": profile_id,
            "source_region_id": "region_plate" if profile_id == "profile_plate" else "region_boss",
            "dependencies": dependencies or [],
            "topology_references": topology_references or [],
            "parameters": {
                "depth_mm": depth,
                "extent": extent,
                "second_depth_mm": second_depth,
                "direction": direction,
                "operation": operation,
            },
        }
    )


def _command(
    operation_type: str,
    revision: int,
    *,
    feature: FeatureRecord | None = None,
    target_id: str | None = None,
    parameters: dict | None = None,
    mode: str = "preview",
) -> FeatureCommand:
    payload = dict(parameters or {})
    if feature is not None:
        payload["feature"] = feature.model_dump(mode="json")
    return FeatureCommand.model_validate(
        {
            "operation_id": f"op_{operation_type}_{revision}",
            "mode": mode,
            "base_revision": revision,
            "operation_type": operation_type,
            "target_id": target_id,
            "parameters": payload,
        }
    )


def _hole_feature(
    feature_id: str,
    base: FeatureRecord,
    *,
    position: tuple[float, float] = (5, 5),
    diameter: float = 2,
    style: str = "simple",
    termination: str = "through",
    depth: float | None = None,
    counterbore_diameter: float | None = None,
    counterbore_depth: float | None = None,
    countersink_diameter: float | None = None,
    countersink_angle: float | None = None,
) -> FeatureRecord:
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    top = next(item for item in base_report.records[0].generated_topology if item.role == "top")
    return FeatureRecord.model_validate(
        {
            "feature_id": feature_id,
            "feature_type": "hole",
            "name": feature_id.replace("_", " ").title(),
            "body_id": base.body_id,
            "sketch_id": base.sketch_id,
            "dependencies": [base.feature_id],
            "topology_references": [
                {
                    "reference_id": top.reference_id,
                    "owner_feature_id": base.feature_id,
                    "topology_type": "face",
                    "role": "top",
                    "source_entity_id": base.profile_id,
                    "expected_signature": top.geometric_signature,
                }
            ],
            "parameters": {
                "style": style,
                "termination": termination,
                "position_mm": position,
                "diameter_mm": diameter,
                "depth_mm": depth,
                "counterbore_diameter_mm": counterbore_diameter,
                "counterbore_depth_mm": counterbore_depth,
                "countersink_diameter_mm": countersink_diameter,
                "countersink_angle_deg": countersink_angle,
                "operation": "cut",
            },
        }
    )


def _revolve_feature(
    feature_id: str,
    *,
    profile_id: str = "profile_boss",
    operation: str = "new_body",
    dependencies: list[str] | None = None,
    topology_references: list[dict] | None = None,
    axis_entity_id: str = "axis_y",
    angle: float = 360,
) -> FeatureRecord:
    return FeatureRecord.model_validate(
        {
            "feature_id": feature_id,
            "feature_type": "revolve",
            "name": feature_id.replace("_", " ").title(),
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": profile_id,
            "dependencies": dependencies or [],
            "topology_references": topology_references or [],
            "parameters": {
                "axis_entity_id": axis_entity_id,
                "angle_deg": angle,
                "operation": operation,
            },
        }
    )


def _fillet_feature(
    feature_id: str,
    target: FeatureRecord,
    edge_references: list,
    *,
    radius: float = 2,
) -> FeatureRecord:
    return FeatureRecord.model_validate(
        {
            "feature_id": feature_id,
            "feature_type": "fillet",
            "name": feature_id.replace("_", " ").title(),
            "body_id": target.body_id,
            "sketch_id": target.sketch_id,
            "profile_id": None,
            "dependencies": [target.feature_id],
            "topology_references": [
                {
                    "reference_id": edge.reference_id,
                    "owner_feature_id": target.feature_id,
                    "topology_type": "edge",
                    "role": edge.role,
                    "source_entity_id": edge.source_entity_id,
                    "expected_signature": edge.geometric_signature,
                }
                for edge in edge_references
            ],
            "parameters": {"radius_mm": radius, "operation": "modify"},
        }
    )


def _chamfer_feature(
    feature_id: str,
    target: FeatureRecord,
    edge_references: list,
    *,
    distance: float = 2,
) -> FeatureRecord:
    fillet = _fillet_feature(feature_id, target, edge_references, radius=distance)
    payload = fillet.model_dump(mode="json")
    payload.update(
        {
            "feature_type": "chamfer",
            "parameters": {"distance_mm": distance, "operation": "modify"},
        }
    )
    return FeatureRecord.model_validate(payload)


def _linear_pattern_feature(
    feature_id: str,
    seed: FeatureRecord,
    *,
    count: int = 3,
    spacing: float = 2,
    direction: tuple[float, float] = (1, 0),
) -> FeatureRecord:
    return FeatureRecord.model_validate(
        {
            "feature_id": feature_id,
            "feature_type": "linear_pattern",
            "name": feature_id.replace("_", " ").title(),
            "body_id": seed.body_id,
            "sketch_id": seed.sketch_id,
            "profile_id": None,
            "dependencies": [seed.feature_id],
            "topology_references": [],
            "parameters": {
                "count": count,
                "spacing_mm": spacing,
                "direction_xy": direction,
                "operation": "modify",
            },
        }
    )


def test_legacy_selection_wrap_preserves_entity_ids_and_creates_one_body_sketch() -> None:
    document = _document()

    assert document.schema_version == "1.1"
    assert document.revision == 0
    assert [body.body_id for body in document.bodies] == ["body_main"]
    assert [sketch.sketch_id for sketch in document.sketches] == ["sketch_main"]
    assert [entity.id for entity in document.sketches[0].state.items] == [
        "profile_plate_hole",
        "profile_plate",
        "profile_boss",
        "profile_revolve_add",
        "profile_revolve_cut",
        "profile_cross_axis",
        "axis_y",
    ]


def test_extrude_rebuild_is_pure_deterministic_and_hole_aware() -> None:
    document = _document().model_copy(update={"features": [_feature("feature_base")]})

    first = rebuild_document(document)
    second = rebuild_document(document.model_copy(deep=True))

    assert first == second
    assert first.ok is True
    assert first.rebuild_order == ["feature_base"]
    measurements = first.records[0].measurements
    assert measurements is not None
    assert measurements.net_profile_area_mm2 == pytest.approx(84.0)
    assert measurements.volume_delta_mm3 == pytest.approx(840.0)
    assert measurements.bounds_mm == pytest.approx((0, 10, 0, 10, 0, 10))
    assert measurements.hole_count == 1


def test_dependency_order_drives_add_and_cut_rebuild() -> None:
    base = _feature("feature_base")
    base_top = next(
        item
        for item in rebuild_document(_document().model_copy(update={"features": [base]})).records[0].generated_topology
        if item.role == "top"
    )
    add = _feature(
        "feature_add",
        profile_id="profile_boss",
        operation="add",
        dependencies=["feature_base"],
        depth=4,
        topology_references=[
            {
                "reference_id": base_top.reference_id,
                "owner_feature_id": "feature_base",
                "topology_type": "face",
                "role": "top",
                "source_entity_id": "profile_plate",
                "expected_signature": base_top.geometric_signature,
            }
        ],
    )
    add_top = next(
        item
        for item in rebuild_document(_document().model_copy(update={"features": [base, add]})).records[1].generated_topology
        if item.role == "top"
    )
    cut = _feature(
        "feature_cut",
        profile_id="profile_boss",
        operation="cut",
        dependencies=["feature_add"],
        depth=2,
        direction="negative",
        topology_references=[
            {
                "reference_id": add_top.reference_id,
                "owner_feature_id": "feature_add",
                "topology_type": "face",
                "role": "top",
                "source_entity_id": "profile_boss",
                "expected_signature": add_top.geometric_signature,
            }
        ],
    )
    document = _document().model_copy(update={"features": [cut, add, base]})

    report = rebuild_document(document)

    assert report.ok is True
    assert report.rebuild_order == ["feature_base", "feature_add", "feature_cut"]
    assert [record.measurements.volume_delta_mm3 for record in report.records if record.measurements] == pytest.approx([840, 144, -72])
    assert report.records[1].measurements.bounds_mm[-2:] == pytest.approx((10, 14))
    assert report.records[2].measurements.bounds_mm[-2:] == pytest.approx((12, 14))


def test_linear_hole_pattern_rebuild_is_exact_deterministic_and_topology_stable() -> None:
    base = _feature("feature_base", profile_id="profile_boss")
    seed = _hole_feature("hole_seed", base, position=(3, 5), diameter=1)
    pattern = _linear_pattern_feature("pattern_holes", seed, count=3, spacing=2, direction=(2, 0))
    document = _document().model_copy(update={"features": [pattern, seed, base]})

    first = rebuild_document(document)
    second = rebuild_document(document.model_copy(deep=True))

    assert first == second
    assert first.ok is True
    assert first.rebuild_order == ["feature_base", "hole_seed", "pattern_holes"]
    record = first.records[2]
    assert record.measurements is not None
    assert record.measurements.net_profile_area_mm2 == pytest.approx(math.pi / 2)
    assert record.measurements.volume_delta_mm3 == pytest.approx(-5 * math.pi)
    assert record.measurements.bounds_mm == pytest.approx((4.5, 7.5, 4.5, 5.5, 0, 10))
    assert record.measurements.hole_count == 2
    assert len(record.generated_topology) == 4
    assert {item.measurements["instance_index"] for item in record.generated_topology} == {1, 2}
    assert {item.measurements["offset_x_mm"] for item in record.generated_topology} == {2.0, 4.0}


@pytest.mark.parametrize(
    ("count", "spacing", "direction"),
    [(1, 2, (1, 0)), (3, 0, (1, 0)), (3, 2, (0, 0)), (3, math.inf, (1, 0))],
)
def test_linear_pattern_rejects_invalid_typed_parameters(
    count: int,
    spacing: float,
    direction: tuple[float, float],
) -> None:
    base = _feature("feature_base", profile_id="profile_boss")
    seed = _hole_feature("hole_seed", base, position=(3, 5), diameter=1)

    with pytest.raises(ValueError):
        _linear_pattern_feature("pattern_holes", seed, count=count, spacing=spacing, direction=direction)


def test_linear_pattern_refuses_overlap_and_instances_outside_target_atomically() -> None:
    base = _feature("feature_base", profile_id="profile_boss")
    seed = _hole_feature("hole_seed", base, position=(3, 5), diameter=1)
    overlap = _linear_pattern_feature("pattern_overlap", seed, spacing=0.5)
    outside = _linear_pattern_feature("pattern_outside", seed, count=4, spacing=2)

    overlap_report = rebuild_document(_document().model_copy(update={"features": [base, seed, overlap]}))
    outside_report = rebuild_document(_document().model_copy(update={"features": [base, seed, outside]}))

    assert overlap_report.ok is False
    assert overlap_report.records[2].error is not None
    assert overlap_report.records[2].error.code == "linear_pattern_instances_overlap"
    assert outside_report.ok is False
    assert outside_report.records[2].error is not None
    assert outside_report.records[2].error.code == "linear_pattern_instance_outside_target"


def test_boolean_extrusion_requires_semantic_attachment_and_direction_into_target() -> None:
    base = _feature("feature_base")
    missing_attachment = _feature(
        "feature_add",
        profile_id="profile_boss",
        operation="add",
        dependencies=["feature_base"],
    )
    missing_report = rebuild_document(_document().model_copy(update={"features": [base, missing_attachment]}))
    assert missing_report.records[1].error.code == "feature_attachment_reference_required"

    top = next(
        item
        for item in rebuild_document(_document().model_copy(update={"features": [base]})).records[0].generated_topology
        if item.role == "top"
    )
    wrong_direction = _feature(
        "feature_cut",
        profile_id="profile_boss",
        operation="cut",
        dependencies=["feature_base"],
        direction="positive",
        topology_references=[
            {
                "reference_id": top.reference_id,
                "owner_feature_id": "feature_base",
                "topology_type": "face",
                "role": "top",
                "source_entity_id": "profile_plate",
                "expected_signature": top.geometric_signature,
            }
        ],
    )
    direction_report = rebuild_document(_document().model_copy(update={"features": [base, wrong_direction]}))
    assert direction_report.records[1].error.code == "feature_direction_away_from_target"


def test_symmetric_and_two_sided_extents_have_deterministic_bounds() -> None:
    symmetric = _feature("feature_symmetric", depth=12, extent="symmetric")
    symmetric_report = rebuild_document(_document().model_copy(update={"features": [symmetric]}))
    assert symmetric_report.records[0].measurements.bounds_mm[-2:] == pytest.approx((-6, 6))

    two_sided = _feature("feature_two_sided", depth=8, extent="two_sided", second_depth=3)
    two_sided_report = rebuild_document(_document().model_copy(update={"features": [two_sided]}))
    assert two_sided_report.records[0].measurements.bounds_mm[-2:] == pytest.approx((-3, 8))
    assert two_sided_report.records[0].measurements.volume_delta_mm3 == pytest.approx(924)


def test_full_revolve_uses_explicit_axis_and_pappus_volume() -> None:
    revolve = _revolve_feature("feature_revolve")

    first = rebuild_document(_document().model_copy(update={"features": [revolve]}))
    second = rebuild_document(_document().model_copy(update={"features": [revolve.model_copy(deep=True)]}))

    assert first == second
    assert first.ok is True
    record = first.records[0]
    assert record.measurements.net_profile_area_mm2 == pytest.approx(36)
    assert record.measurements.volume_delta_mm3 == pytest.approx(360 * math.pi)
    assert record.measurements.bounds_mm == pytest.approx((-8, 8, 2, 8, -8, 8))
    assert {item.role for item in record.generated_topology} == {"revolved_outer_face"}


def test_fillet_uses_semantic_vertical_edges_and_defers_measurements_to_kernel() -> None:
    base = _feature("feature_base")
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    vertical_edges = [item for item in base_report.records[0].generated_topology if item.role == "vertical_outer_edge"]
    fillet = _fillet_feature("feature_fillet", base, vertical_edges, radius=2)

    report = rebuild_document(_document().model_copy(update={"features": [base, fillet]}))

    assert len(vertical_edges) == 4
    assert all(edge.measurements["corner_class"] == "convex" for edge in vertical_edges)
    assert report.ok is True
    record = report.records[1]
    assert record.measurement_coverage == "kernel_required"
    assert record.measurements is None
    assert len(record.resolved_references) == 4
    assert {item.role for item in record.generated_topology} == {"fillet_surface"}


def test_fillet_reference_recovers_after_upstream_profile_edit() -> None:
    base = _feature("feature_base")
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    selected_edge = next(
        item
        for item in base_report.records[0].generated_topology
        if item.role == "vertical_outer_edge" and item.measurements["x_mm"] == 10 and item.measurements["y_mm"] == 0
    )
    fillet = _fillet_feature("feature_fillet", base, [selected_edge], radius=2)
    document = _document()
    profile = document.sketches[0].state.get_entity("profile_plate")
    edited_profile = profile.model_copy(
        update={"vertices": [(0, 0), (12, 0), (12, 10), (0, 10), (0, 0)], "area": 120}
    )
    edited_state = document.sketches[0].state.model_copy(
        update={"items": [edited_profile if item.id == profile.id else item for item in document.sketches[0].state.items]}
    )
    edited_document = document.model_copy(
        update={"sketches": [document.sketches[0].model_copy(update={"state": edited_state})], "features": [base, fillet]}
    )

    report = rebuild_document(edited_document)

    assert report.ok is True
    assert report.records[1].resolved_references[0].recovery_state == "recovered"
    assert report.records[1].resolved_references[0].current_signature != selected_edge.geometric_signature


def test_fillet_rejects_non_vertical_edge_and_excess_radius() -> None:
    base = _feature("feature_base")
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    top_edge = next(item for item in base_report.records[0].generated_topology if item.role == "top_outer_edge")
    vertical_edge = next(item for item in base_report.records[0].generated_topology if item.role == "vertical_outer_edge")

    wrong_edge = rebuild_document(
        _document().model_copy(update={"features": [base, _fillet_feature("feature_wrong_edge", base, [top_edge])]})
    )
    excess_radius = rebuild_document(
        _document().model_copy(update={"features": [base, _fillet_feature("feature_large", base, [vertical_edge], radius=5)]})
    )

    assert wrong_edge.records[1].error.code == "unsupported_fillet_edge"
    assert excess_radius.records[1].error.code == "fillet_radius_exceeds_adjacent_edges"


def test_chamfer_reuses_semantic_edge_contract_and_defers_measurements_to_kernel() -> None:
    base = _feature("feature_base")
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    vertical_edges = [item for item in base_report.records[0].generated_topology if item.role == "vertical_outer_edge"]
    chamfer = _chamfer_feature("feature_chamfer", base, vertical_edges, distance=2)

    report = rebuild_document(_document().model_copy(update={"features": [base, chamfer]}))
    too_large = rebuild_document(
        _document().model_copy(update={"features": [base, _chamfer_feature("feature_large", base, vertical_edges[:1], distance=5)]})
    )

    assert report.ok is True
    assert report.records[1].measurement_coverage == "kernel_required"
    assert report.records[1].measurements is None
    assert {item.role for item in report.records[1].generated_topology} == {"chamfer_surface"}
    assert len(report.records[1].resolved_references) == 4
    assert too_large.records[1].error.code == "chamfer_distance_exceeds_adjacent_edges"


def test_revolve_add_and_cut_require_semantic_target_faces() -> None:
    base = _revolve_feature("feature_revolve_base")
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    target_face = base_report.records[0].generated_topology[0]
    selector = {
        "reference_id": target_face.reference_id,
        "owner_feature_id": base.feature_id,
        "topology_type": "face",
        "role": target_face.role,
        "source_entity_id": target_face.source_entity_id,
        "expected_signature": target_face.geometric_signature,
    }
    add = _revolve_feature(
        "feature_revolve_add",
        profile_id="profile_revolve_add",
        operation="add",
        dependencies=[base.feature_id],
        topology_references=[selector],
    )
    cut = _revolve_feature(
        "feature_revolve_cut",
        profile_id="profile_revolve_cut",
        operation="cut",
        dependencies=[base.feature_id],
        topology_references=[selector],
    )

    add_report = rebuild_document(_document().model_copy(update={"features": [base, add]}))
    cut_report = rebuild_document(_document().model_copy(update={"features": [base, cut]}))

    assert add_report.ok is True
    assert add_report.records[1].measurements.volume_delta_mm3 == pytest.approx(216 * math.pi)
    assert add_report.records[1].resolved_references[0].recovery_state == "exact"
    assert cut_report.ok is True
    assert cut_report.records[1].measurements.volume_delta_mm3 == pytest.approx(-120 * math.pi)


def test_revolve_axis_edit_recovers_reference_and_invalid_envelopes_fail_structurally() -> None:
    base = _revolve_feature("feature_revolve_base")
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    target_face = base_report.records[0].generated_topology[0]
    add = _revolve_feature(
        "feature_revolve_add",
        profile_id="profile_revolve_add",
        operation="add",
        dependencies=[base.feature_id],
        topology_references=[
            {
                "reference_id": target_face.reference_id,
                "owner_feature_id": base.feature_id,
                "topology_type": "face",
                "role": target_face.role,
                "source_entity_id": target_face.source_entity_id,
                "expected_signature": target_face.geometric_signature,
            }
        ],
    )
    edited = _document().model_copy(update={"features": [base, add]})
    axis = edited.sketches[0].state.get_entity("axis_y")
    edited.sketches[0].state.items[edited.sketches[0].state.items.index(axis)] = axis.model_copy(update={"origin": (1, 0)})

    edited_report = rebuild_document(edited)
    partial_report = rebuild_document(
        _document().model_copy(update={"features": [_revolve_feature("feature_partial", angle=180)]})
    )
    crossing_report = rebuild_document(
        _document().model_copy(update={"features": [_revolve_feature("feature_cross", profile_id="profile_cross_axis")]})
    )
    missing_axis_report = rebuild_document(
        _document().model_copy(update={"features": [_revolve_feature("feature_missing_axis", axis_entity_id="axis_missing")]})
    )

    assert edited_report.ok is True
    assert edited_report.records[1].resolved_references[0].recovery_state == "recovered"
    assert edited_report.records[0].generated_topology[0].reference_id == target_face.reference_id
    assert edited_report.records[0].generated_topology[0].geometric_signature != target_face.geometric_signature
    assert partial_report.records[0].error.code == "unsupported_partial_revolve"
    assert crossing_report.records[0].error.code == "invalid_feature_geometry"
    assert "cross" in crossing_report.records[0].error.message
    assert missing_axis_report.records[0].error.code == "invalid_feature_geometry"
    assert "axis does not exist" in missing_axis_report.records[0].error.message


def test_add_feature_preview_and_commit_shapes_increment_revision_without_side_effects() -> None:
    document = _document()
    feature = _feature("feature_base")

    preview = apply_feature_command(document, _command("add_feature", 0, feature=feature))
    committed = apply_feature_command(document, _command("add_feature", 0, feature=feature, mode="commit"))

    assert document.features == []
    assert preview.status == "preview"
    assert committed.status == "committed"
    assert preview.after == committed.after
    assert committed.after.revision == 1
    assert committed.changed_feature_ids == ["feature_base"]


def test_replace_feature_preserves_id_and_changes_rebuild_signature() -> None:
    added = apply_feature_command(_document(), _command("add_feature", 0, feature=_feature("feature_base"), mode="commit")).after
    original_signature = added.last_rebuild.records[0].output_signature
    replacement = _feature("feature_base", depth=25)

    result = apply_feature_command(added, _command("replace_feature", 1, feature=replacement, target_id="feature_base", mode="commit"))

    assert result.after.features[0].feature_id == "feature_base"
    assert result.after.features[0].parameters.depth_mm == 25
    assert result.after.last_rebuild.records[0].output_signature != original_signature
    assert result.after.revision == 2


def test_stale_revision_is_rejected_before_proposal() -> None:
    with pytest.raises(RevisionConflictError) as exc_info:
        apply_feature_command(_document(), _command("add_feature", 3, feature=_feature("feature_base")))

    assert exc_info.value.detail["base_revision"] == 3
    assert exc_info.value.detail["current_revision"] == 0


def test_cycle_and_missing_profile_fail_with_structured_rebuild_report() -> None:
    left = _feature("feature_left", operation="add", dependencies=["feature_right"])
    right = _feature("feature_right", operation="add", dependencies=["feature_left"])
    cyclic = _document().model_copy(update={"features": [left, right]})
    cycle_report = rebuild_document(cyclic)
    assert cycle_report.ok is False
    assert {record.error.code for record in cycle_report.records if record.error} == {"feature_dependency_cycle"}

    missing = _feature("feature_missing", profile_id="profile_unknown")
    with pytest.raises(FeatureRebuildError) as exc_info:
        apply_feature_command(_document(), _command("add_feature", 0, feature=missing))
    rebuild = exc_info.value.detail["rebuild"]
    assert rebuild["records"][0]["error"]["code"] == "missing_feature_profile"


def test_delete_refuses_downstream_reference_and_suppression_is_rebuildable() -> None:
    base = _feature("feature_base")
    add = _feature("feature_add", profile_id="profile_boss", operation="add", dependencies=["feature_base"])
    document = _document().model_copy(update={"revision": 2, "features": [base, add]})

    with pytest.raises(SelectionResolutionError) as exc_info:
        apply_feature_command(document, _command("delete_feature", 2, target_id="feature_base"))
    assert exc_info.value.detail["error_code"] == "feature_still_referenced"

    suppressed = apply_feature_command(
        document,
        _command("set_feature_suppressed", 2, target_id="feature_add", parameters={"suppressed": True}),
    )
    assert suppressed.after.features[1].suppressed is True
    assert suppressed.rebuild.records[1].status == "suppressed"


def test_extrude_emits_stable_semantic_topology_with_geometry_signatures() -> None:
    first = rebuild_document(_document().model_copy(update={"features": [_feature("feature_base", depth=10)]}))
    second = rebuild_document(_document().model_copy(update={"features": [_feature("feature_base", depth=25)]}))

    first_topology = {item.reference_id: item for item in first.records[0].generated_topology}
    second_topology = {item.reference_id: item for item in second.records[0].generated_topology}
    assert first_topology.keys() == second_topology.keys()
    assert {item.role for item in first_topology.values()} >= {
        "top",
        "bottom",
        "outer_wall",
        "top_outer_edge",
        "bottom_outer_edge",
        "hole_wall",
        "top_hole_edge",
        "bottom_hole_edge",
    }
    first_top = next(item for item in first_topology.values() if item.role == "top")
    second_top = second_topology[first_top.reference_id]
    assert second_top.geometric_signature != first_top.geometric_signature
    assert second_top.source_entity_id == "profile_plate"


def test_downstream_topology_reference_recovers_after_upstream_depth_edit() -> None:
    base = _feature("feature_base", depth=10)
    base_report = rebuild_document(_document().model_copy(update={"features": [base]}))
    top = next(item for item in base_report.records[0].generated_topology if item.role == "top")
    selector = {
        "reference_id": top.reference_id,
        "owner_feature_id": "feature_base",
        "topology_type": "face",
        "role": "top",
        "source_entity_id": "profile_plate",
        "expected_signature": top.geometric_signature,
    }
    downstream = _feature(
        "feature_add",
        profile_id="profile_boss",
        operation="add",
        dependencies=["feature_base"],
        depth=4,
        topology_references=[selector],
    )

    exact = rebuild_document(_document().model_copy(update={"features": [base, downstream]}))
    assert exact.ok is True
    assert exact.records[1].resolved_references[0].recovery_state == "exact"

    edited = rebuild_document(
        _document().model_copy(update={"features": [_feature("feature_base", depth=25), downstream]})
    )
    resolved = edited.records[1].resolved_references[0]
    assert edited.ok is True
    assert resolved.recovery_state == "recovered"
    assert resolved.resolved_reference_id == top.reference_id
    assert resolved.current_signature != resolved.expected_signature


def test_simple_through_hole_uses_semantic_top_face_and_emits_stable_topology() -> None:
    base = _feature("feature_base", profile_id="profile_boss", depth=10)
    hole = _hole_feature("feature_hole", base)

    report = rebuild_document(_document().model_copy(update={"features": [base, hole]}))

    assert report.ok is True
    record = report.records[1]
    assert record.resolved_references[0].recovery_state == "exact"
    assert record.measurements.volume_delta_mm3 == pytest.approx(-10 * math.pi)
    assert record.measurements.bounds_mm == pytest.approx((4, 6, 4, 6, 0, 10))
    assert {item.role for item in record.generated_topology} == {"hole_wall", "hole_rim"}


def test_blind_counterbore_and_through_countersink_have_typed_volume_semantics() -> None:
    base = _feature("feature_base", profile_id="profile_boss", depth=10)
    counterbore = _hole_feature(
        "feature_counterbore",
        base,
        style="counterbore",
        termination="blind",
        depth=6,
        counterbore_diameter=4,
        counterbore_depth=2,
    )
    counterbore_report = rebuild_document(_document().model_copy(update={"features": [base, counterbore]}))
    counterbore_record = counterbore_report.records[1]
    assert counterbore_report.ok is True
    assert counterbore_record.measurements.volume_delta_mm3 == pytest.approx(-12 * math.pi)
    assert counterbore_record.measurements.bounds_mm == pytest.approx((3, 7, 3, 7, 4, 10))
    assert {item.role for item in counterbore_record.generated_topology} >= {
        "hole_wall",
        "hole_rim",
        "hole_bottom",
        "counterbore_wall",
        "counterbore_step_edge",
    }

    countersink = _hole_feature(
        "feature_countersink",
        base,
        style="countersink",
        countersink_diameter=4,
        countersink_angle=90,
    )
    countersink_report = rebuild_document(_document().model_copy(update={"features": [base, countersink]}))
    countersink_record = countersink_report.records[1]
    assert countersink_report.ok is True
    assert countersink_record.measurements.volume_delta_mm3 == pytest.approx(-(10 + 4 / 3) * math.pi)
    assert "countersink_face" in {item.role for item in countersink_record.generated_topology}


def test_hole_reference_recovers_after_depth_edit_and_updates_through_depth() -> None:
    base = _feature("feature_base", profile_id="profile_boss", depth=10)
    hole = _hole_feature("feature_hole", base)

    edited_base = _feature("feature_base", profile_id="profile_boss", depth=20)
    report = rebuild_document(_document().model_copy(update={"features": [edited_base, hole]}))

    assert report.ok is True
    record = report.records[1]
    assert record.resolved_references[0].recovery_state == "recovered"
    assert record.measurements.volume_delta_mm3 == pytest.approx(-20 * math.pi)
    assert record.measurements.bounds_mm[-2:] == pytest.approx((0, 20))


def test_hole_rejects_missing_top_face_edge_breakout_and_excess_blind_depth() -> None:
    base = _feature("feature_base", profile_id="profile_boss", depth=10)
    missing_reference = _hole_feature("feature_missing_reference", base).model_copy(update={"topology_references": []})
    missing_report = rebuild_document(_document().model_copy(update={"features": [base, missing_reference]}))
    assert missing_report.records[1].error.code == "hole_top_face_reference_required"

    breakout = _hole_feature("feature_breakout", base, position=(2.5, 5), diameter=2)
    breakout_report = rebuild_document(_document().model_copy(update={"features": [base, breakout]}))
    assert breakout_report.records[1].error.code == "invalid_feature_geometry"
    assert "inside target material" in breakout_report.records[1].error.message

    too_deep = _hole_feature("feature_too_deep", base, termination="blind", depth=11)
    too_deep_report = rebuild_document(_document().model_copy(update={"features": [base, too_deep]}))
    assert too_deep_report.records[1].error.code == "invalid_feature_geometry"
    assert "target thickness" in too_deep_report.records[1].error.message


@pytest.mark.parametrize(
    ("role", "source_entity_id", "expected_code"),
    [
        ("missing_role", "profile_plate", "missing_topology_reference"),
        ("top_outer_edge", "profile_plate", "ambiguous_topology_reference"),
    ],
)
def test_unrecoverable_topology_reference_fails_structurally(
    role: str,
    source_entity_id: str,
    expected_code: str,
) -> None:
    base = _feature("feature_base")
    downstream = _feature(
        "feature_add",
        profile_id="profile_boss",
        operation="add",
        dependencies=["feature_base"],
        topology_references=[
            {
                "reference_id": "topo_stale_reference",
                "owner_feature_id": "feature_base",
                "topology_type": "edge" if "edge" in role else "face",
                "role": role,
                "source_entity_id": source_entity_id,
                "expected_signature": "stale_signature",
            }
        ],
    )

    report = rebuild_document(_document().model_copy(update={"features": [base, downstream]}))

    assert report.ok is False
    assert report.records[1].error.code == expected_code
