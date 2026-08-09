from __future__ import annotations

import math
from dataclasses import dataclass

from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import (
    DesignParameter,
    FeatureRecord,
    SketchMathDocument,
    wrap_legacy_selection_context,
)
from sketchmath.models.selection_context import SelectionContext


@dataclass(frozen=True)
class GoldenMountingPlateExpectation:
    feature_count: int
    body_bounds_mm: tuple[float, float, float, float, float, float]
    pre_fillet_volume_mm3: float
    final_volume_mm3: float
    through_hole_count: int
    maximum_z_mm: float
    fillet_radius_mm: float


def _circle_vertices(center: tuple[float, float], radius: float, *, segments: int = 360) -> list[tuple[float, float]]:
    points = [
        (
            center[0] + radius * math.cos(2 * math.pi * index / segments),
            center[1] + radius * math.sin(2 * math.pi * index / segments),
        )
        for index in range(segments)
    ]
    return [*points, points[0]]


def _top_selector(document: SketchMathDocument, owner_feature_id: str) -> dict[str, object]:
    report = rebuild_document(document)
    owner = next(record for record in report.records if record.feature_id == owner_feature_id)
    top = next(reference for reference in owner.generated_topology if reference.topology_type == "face" and reference.role == "top")
    return {
        "reference_id": top.reference_id,
        "owner_feature_id": owner_feature_id,
        "topology_type": "face",
        "role": "top",
        "source_entity_id": top.source_entity_id,
        "expected_signature": top.geometric_signature,
    }


def _hole(feature_id: str, owner: FeatureRecord, selector: dict[str, object], position: tuple[float, float], diameter: float) -> FeatureRecord:
    return FeatureRecord.model_validate(
        {
            "feature_id": feature_id,
            "feature_type": "hole",
            "name": feature_id.replace("_", " ").title(),
            "body_id": owner.body_id,
            "sketch_id": owner.sketch_id,
            "dependencies": [owner.feature_id],
            "topology_references": [selector],
            "parameters": {
                "style": "simple",
                "termination": "through",
                "position_mm": position,
                "diameter_mm": diameter,
                "operation": "cut",
            },
        }
    )


def build_golden_mounting_plate() -> SketchMathDocument:
    selection = SelectionContext.model_validate(
        {
            "selection_set_id": "golden_mounting_plate_v1",
            "units": "mm",
            "frame": "canvas_2d",
            "items": [
                {
                    "id": "profile_plate",
                    "type": "profile_2d",
                    "vertices": [[0, 0], [80, 0], [80, 50], [0, 50], [0, 0]],
                    "area": 4000,
                    "winding": "counterclockwise",
                },
                {
                    "id": "circle_boss",
                    "type": "circle_2d",
                    "center": [40, 25],
                    "radius": 15,
                },
                {
                    "id": "profile_boss",
                    "type": "profile_2d",
                    "vertices": _circle_vertices((40, 25), 15),
                    "area": math.pi * 15**2,
                    "winding": "counterclockwise",
                    "source_circle_id": "circle_boss",
                },
            ],
            "constraints": [],
            "named_references": {"plate": "profile_plate", "boss": "profile_boss", "boss_circle": "circle_boss"},
        }
    )
    document = wrap_legacy_selection_context(selection, document_id="golden_mounting_plate_v1")
    base = FeatureRecord.model_validate(
        {
            "feature_id": "feature_plate",
            "name": "Plate",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": "profile_plate",
            "parameters": {"depth_mm": 5, "operation": "new_body"},
        }
    )
    document = document.model_copy(update={"features": [base]})
    plate_top = _top_selector(document, base.feature_id)
    mounting_holes = [
        _hole("feature_mount_hole_1", base, plate_top, (7, 7), 5),
        _hole("feature_mount_hole_2", base, plate_top, (73, 7), 5),
        _hole("feature_mount_hole_3", base, plate_top, (73, 43), 5),
        _hole("feature_mount_hole_4", base, plate_top, (7, 43), 5),
    ]
    boss = FeatureRecord.model_validate(
        {
            "feature_id": "feature_boss",
            "name": "Raised boss",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": "profile_boss",
            "dependencies": [base.feature_id],
            "topology_references": [plate_top],
            "parameters": {"depth_mm": 8, "direction": "positive", "operation": "add"},
        }
    )
    document = document.model_copy(update={"features": [base, *mounting_holes, boss]})
    boss_top = _top_selector(document, boss.feature_id)
    boss_hole = _hole("feature_boss_hole", boss, boss_top, (40, 25), 10)
    pre_finish_features = [base, *mounting_holes, boss, boss_hole]
    pre_finish_document = document.model_copy(update={"features": pre_finish_features})
    base_record = next(
        record for record in rebuild_document(pre_finish_document).records if record.feature_id == base.feature_id
    )
    base_edges = [reference for reference in base_record.generated_topology if reference.role == "vertical_outer_edge"]
    fillet = FeatureRecord.model_validate(
        {
            "feature_id": "feature_outer_fillet",
            "feature_type": "fillet",
            "name": "Outer edge fillets",
            "body_id": base.body_id,
            "sketch_id": base.sketch_id,
            "profile_id": None,
            "dependencies": [base.feature_id],
            "topology_references": [
                {
                    "reference_id": edge.reference_id,
                    "owner_feature_id": base.feature_id,
                    "topology_type": "edge",
                    "role": edge.role,
                    "source_entity_id": edge.source_entity_id,
                    "expected_signature": edge.geometric_signature,
                }
                for edge in base_edges
            ],
            "parameters": {"radius_mm": 2, "operation": "modify"},
        }
    )
    features = [*pre_finish_features, fillet]
    body = document.bodies[0].model_copy(update={"feature_ids": [feature.feature_id for feature in features]})
    design_parameters = [
        DesignParameter.model_validate(
            {
                "parameter_id": "plate_width_mm",
                "name": "Plate width",
                "value": 80,
                "minimum": 31,
                "bindings": [
                    {"binding_type": "rectangle_profile_width", "target_id": "profile_plate"},
                    {"binding_type": "circle_center_x", "target_id": "circle_boss", "scale": 0.5},
                    {"binding_type": "hole_position_x", "target_id": "feature_mount_hole_2", "offset": -7},
                    {"binding_type": "hole_position_x", "target_id": "feature_mount_hole_3", "offset": -7},
                    {"binding_type": "hole_position_x", "target_id": "feature_boss_hole", "scale": 0.5},
                ],
            }
        ),
        DesignParameter.model_validate(
            {
                "parameter_id": "corner_hole_diameter_mm",
                "name": "Corner-hole diameter",
                "value": 5,
                "minimum": 0.01,
                "maximum": 13.99,
                "bindings": [
                    {"binding_type": "hole_diameter", "target_id": f"feature_mount_hole_{index}"}
                    for index in range(1, 5)
                ],
            }
        ),
    ]
    document = document.model_copy(
        update={
            "revision": len(features),
            "features": features,
            "bodies": [body],
            "design_parameters": design_parameters,
        }
    )
    return document.model_copy(update={"last_rebuild": rebuild_document(document)})


def edit_golden_mounting_plate_parameters(
    document: SketchMathDocument,
    *,
    plate_width_mm: float | None = None,
    corner_hole_diameter_mm: float | None = None,
) -> SketchMathDocument:
    """Apply the fixture's canonical design parameters through typed feature operations."""
    from sketchmath.features.executor import apply_feature_command
    from sketchmath.models.feature_command import FeatureCommand

    edited = document.model_copy(deep=True)
    edits = (
        ("plate_width_mm", plate_width_mm),
        ("corner_hole_diameter_mm", corner_hole_diameter_mm),
    )
    for parameter_id, value in edits:
        if value is None:
            continue
        command = FeatureCommand(
            operation_id=f"golden_set_{parameter_id}_{edited.revision}",
            mode="commit",
            base_revision=edited.revision,
            operation_type="set_design_parameter",
            target_id=parameter_id,
            parameters={"value": value},
        )
        edited = apply_feature_command(edited, command).after
    return edited


def golden_mounting_plate_expectation() -> GoldenMountingPlateExpectation:
    pre_fillet_volume = 20_000 + 1_350 * math.pi
    fillet_removal = 4 * (1 - math.pi / 4) * 2**2 * 5
    return GoldenMountingPlateExpectation(
        feature_count=8,
        body_bounds_mm=(0, 80, 0, 50, 0, 13),
        pre_fillet_volume_mm3=pre_fillet_volume,
        final_volume_mm3=pre_fillet_volume - fillet_removal,
        through_hole_count=5,
        maximum_z_mm=13,
        fillet_radius_mm=2,
    )
