from __future__ import annotations

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
                "direction": "positive",
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


def test_legacy_selection_wrap_preserves_entity_ids_and_creates_one_body_sketch() -> None:
    document = _document()

    assert document.schema_version == "1.0"
    assert document.revision == 0
    assert [body.body_id for body in document.bodies] == ["body_main"]
    assert [sketch.sketch_id for sketch in document.sketches] == ["sketch_main"]
    assert [entity.id for entity in document.sketches[0].state.items] == ["profile_plate_hole", "profile_plate", "profile_boss"]


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
    add = _feature("feature_add", profile_id="profile_boss", operation="add", dependencies=["feature_base"], depth=4)
    cut = _feature("feature_cut", profile_id="profile_boss", operation="cut", dependencies=["feature_add"], depth=2)
    document = _document().model_copy(update={"features": [cut, add, base]})

    report = rebuild_document(document)

    assert report.ok is True
    assert report.rebuild_order == ["feature_base", "feature_add", "feature_cut"]
    assert [record.measurements.volume_delta_mm3 for record in report.records if record.measurements] == pytest.approx([840, 144, -72])


def test_symmetric_and_two_sided_extents_have_deterministic_bounds() -> None:
    symmetric = _feature("feature_symmetric", depth=12, extent="symmetric")
    symmetric_report = rebuild_document(_document().model_copy(update={"features": [symmetric]}))
    assert symmetric_report.records[0].measurements.bounds_mm[-2:] == pytest.approx((-6, 6))

    two_sided = _feature("feature_two_sided", depth=8, extent="two_sided", second_depth=3)
    two_sided_report = rebuild_document(_document().model_copy(update={"features": [two_sided]}))
    assert two_sided_report.records[0].measurements.bounds_mm[-2:] == pytest.approx((-3, 8))
    assert two_sided_report.records[0].measurements.volume_delta_mm3 == pytest.approx(924)


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
