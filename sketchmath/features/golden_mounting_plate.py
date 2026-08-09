from __future__ import annotations

import math
from dataclasses import dataclass

from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import FeatureRecord, HoleParameters, SketchMathDocument, wrap_legacy_selection_context
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
                    "source_region_id": "region_plate",
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
                    "source_region_id": "region_boss",
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
            "source_region_id": "region_plate",
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
            "source_region_id": "region_boss",
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
    document = document.model_copy(update={"revision": len(features), "features": features, "bodies": [body]})
    return document.model_copy(update={"last_rebuild": rebuild_document(document)})


def edit_golden_mounting_plate_parameters(
    document: SketchMathDocument,
    *,
    plate_width_mm: float | None = None,
    corner_hole_diameter_mm: float | None = None,
) -> SketchMathDocument:
    """Apply the golden fixture's declared edge-offset/center intent without replacing stable IDs."""
    edited = document.model_copy(deep=True)
    sketch = edited.sketches[0]
    plate = sketch.state.get_entity("profile_plate")
    boss_circle = sketch.state.get_entity("circle_boss")
    boss_profile = sketch.state.get_entity("profile_boss")
    current_width = max(point[0] for point in plate.vertices)
    width = float(plate_width_mm if plate_width_mm is not None else current_width)
    diameter = float(
        corner_hole_diameter_mm
        if corner_hole_diameter_mm is not None
        else next(
            feature.parameters.diameter_mm
            for feature in edited.features
            if feature.feature_id == "feature_mount_hole_1" and isinstance(feature.parameters, HoleParameters)
        )
    )
    if not math.isfinite(width) or width <= 30:
        raise ValueError("Golden plate width must be finite and greater than the 30 mm boss diameter")
    if not math.isfinite(diameter) or diameter <= 0 or diameter >= 14:
        raise ValueError("Golden corner-hole diameter must be finite, positive, and smaller than twice the 7 mm edge offset")

    plate_replacement = plate.model_copy(
        update={
            "vertices": [(0, 0), (width, 0), (width, 50), (0, 50), (0, 0)],
            "area": width * 50,
        }
    )
    center = (width / 2.0, 25.0)
    boss_circle_replacement = boss_circle.model_copy(update={"center": center})
    boss_profile_replacement = boss_profile.model_copy(update={"vertices": _circle_vertices(center, 15)})
    replacements = {
        plate.id: plate_replacement,
        boss_circle.id: boss_circle_replacement,
        boss_profile.id: boss_profile_replacement,
    }
    sketch.state.items = [replacements.get(item.id, item) for item in sketch.state.items]

    hole_positions = {
        "feature_mount_hole_1": (7.0, 7.0),
        "feature_mount_hole_2": (width - 7.0, 7.0),
        "feature_mount_hole_3": (width - 7.0, 43.0),
        "feature_mount_hole_4": (7.0, 43.0),
        "feature_boss_hole": center,
    }
    next_features: list[FeatureRecord] = []
    for feature in edited.features:
        if feature.feature_id not in hole_positions or not isinstance(feature.parameters, HoleParameters):
            next_features.append(feature)
            continue
        updates: dict[str, object] = {"position_mm": hole_positions[feature.feature_id]}
        if feature.feature_id.startswith("feature_mount_hole_"):
            updates["diameter_mm"] = diameter
        next_features.append(feature.model_copy(update={"parameters": feature.parameters.model_copy(update=updates)}))
    edited.features = next_features
    edited.revision += 1
    edited.last_rebuild = rebuild_document(edited)
    if not edited.last_rebuild.ok:
        raise ValueError("Golden mounting-plate parameter edit did not rebuild")
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
