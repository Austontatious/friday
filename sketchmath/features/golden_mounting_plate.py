from __future__ import annotations

import math
from dataclasses import dataclass

from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import FeatureRecord, SketchMathDocument, wrap_legacy_selection_context
from sketchmath.models.selection_context import SelectionContext


@dataclass(frozen=True)
class GoldenMountingPlateExpectation:
    feature_count: int
    body_bounds_mm: tuple[float, float, float, float, float, float]
    cumulative_volume_mm3: float
    through_hole_count: int
    maximum_z_mm: float


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
                    "vertices": [[0, 0], [100, 0], [100, 60], [0, 60], [0, 0]],
                    "area": 6000,
                    "winding": "counterclockwise",
                    "source_region_id": "region_plate",
                },
                {
                    "id": "profile_boss",
                    "type": "profile_2d",
                    "vertices": [[35, 20], [65, 20], [65, 40], [35, 40], [35, 20]],
                    "area": 600,
                    "winding": "counterclockwise",
                    "source_region_id": "region_boss",
                },
            ],
            "constraints": [],
            "named_references": {"plate": "profile_plate", "boss": "profile_boss"},
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
            "source_region_id": "region_plate",
            "parameters": {"depth_mm": 8, "operation": "new_body"},
        }
    )
    document = document.model_copy(update={"features": [base]})
    plate_top = _top_selector(document, base.feature_id)
    mounting_holes = [
        _hole("feature_mount_hole_1", base, plate_top, (12, 12), 6),
        _hole("feature_mount_hole_2", base, plate_top, (88, 12), 6),
        _hole("feature_mount_hole_3", base, plate_top, (88, 48), 6),
        _hole("feature_mount_hole_4", base, plate_top, (12, 48), 6),
    ]
    boss = FeatureRecord.model_validate(
        {
            "feature_id": "feature_boss",
            "name": "Raised boss",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": "profile_boss",
            "source_region_id": "region_boss",
            "dependencies": [base.feature_id],
            "topology_references": [plate_top],
            "parameters": {"depth_mm": 5, "direction": "positive", "operation": "add"},
        }
    )
    document = document.model_copy(update={"features": [base, *mounting_holes, boss]})
    boss_top = _top_selector(document, boss.feature_id)
    boss_hole = _hole("feature_boss_hole", boss, boss_top, (50, 30), 10)
    features = [base, *mounting_holes, boss, boss_hole]
    body = document.bodies[0].model_copy(update={"feature_ids": [feature.feature_id for feature in features]})
    document = document.model_copy(update={"revision": len(features), "features": features, "bodies": [body]})
    return document.model_copy(update={"last_rebuild": rebuild_document(document)})


def golden_mounting_plate_expectation() -> GoldenMountingPlateExpectation:
    return GoldenMountingPlateExpectation(
        feature_count=7,
        body_bounds_mm=(0, 100, 0, 60, 0, 13),
        cumulative_volume_mm3=51000 - 613 * math.pi,
        through_hole_count=5,
        maximum_z_mm=13,
    )
