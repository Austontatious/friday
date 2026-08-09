from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from sketchmath.cad.adapter import CadAdapter
from sketchmath.cad.feature_mesh import build_feature_body_mesh
from sketchmath.cad.solid_validation import validate_solid_measurements
from sketchmath.cad.stl_export import write_ascii_stl
from sketchmath.executor.errors import CadExportError, FeatureRebuildError, MissingEntityError, UnsupportedCadFormatError
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import ExtrudeParameters, FeatureBuildRecord, FeatureRecord, FilletParameters, SketchMathDocument
from sketchmath.models.entities import Profile2DEntity


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("._")
    return cleaned[:96] or "unnamed"


def _source_geometry(document: SketchMathDocument, feature: FeatureRecord) -> tuple[Profile2DEntity, list[Profile2DEntity]]:
    sketch = next((item for item in document.sketches if item.sketch_id == feature.sketch_id), None)
    if sketch is None:
        raise MissingEntityError("Feature sketch does not exist", detail={"sketch_id": feature.sketch_id})
    profile = sketch.state.get_entity(feature.profile_id)
    if not isinstance(profile, Profile2DEntity):
        raise CadExportError("Feature source is not a profile", detail={"profile_id": feature.profile_id})
    holes: list[Profile2DEntity] = []
    for hole_id in profile.holes:
        hole = sketch.state.get_entity(hole_id)
        if not isinstance(hole, Profile2DEntity):
            raise CadExportError("Feature hole source is not a profile", detail={"hole_id": hole_id})
        holes.append(hole)
    return profile, holes


def _validated_feature(document: SketchMathDocument, feature_id: str) -> tuple[FeatureRecord, FeatureBuildRecord]:
    feature = next((item for item in document.features if item.feature_id == feature_id), None)
    if feature is None:
        raise MissingEntityError("Feature does not exist", detail={"feature_id": feature_id})
    report = rebuild_document(document)
    record = next((item for item in report.records if item.feature_id == feature_id), None)
    if not report.ok or record is None or record.status != "succeeded":
        raise FeatureRebuildError(
            "Feature must rebuild successfully before artifact generation",
            detail={"feature_id": feature_id, "rebuild": report.model_dump(mode="json")},
        )
    if feature.suppressed:
        raise CadExportError("Suppressed feature cannot produce an artifact", detail={"feature_id": feature_id})
    if record.measurements is None and feature.feature_type != "fillet":
        raise FeatureRebuildError(
            "Feature rebuild did not produce required analytic measurements",
            detail={"feature_id": feature_id, "measurement_coverage": record.measurement_coverage},
        )
    return feature, record


def _fillet_step_payload(document: SketchMathDocument, feature: FeatureRecord) -> dict[str, Any]:
    if not isinstance(feature.parameters, FilletParameters) or len(feature.dependencies) != 1:
        raise CadExportError(
            "Canonical fillet STEP requires one target extrusion",
            detail={"feature_id": feature.feature_id, "error_code": "unsupported_fillet_graph"},
        )
    terminal_index = document.features.index(feature)
    later = [
        item.feature_id
        for item in document.features[terminal_index + 1 :]
        if item.body_id == feature.body_id and not item.suppressed
    ]
    if later:
        raise CadExportError(
            "Canonical fillet STEP requires the fillet to be the terminal body feature",
            detail={"feature_id": feature.feature_id, "later_feature_ids": later, "error_code": "artifact_feature_not_terminal"},
        )
    target = next((item for item in document.features if item.feature_id == feature.dependencies[0]), None)
    if target is None or not isinstance(target.parameters, ExtrudeParameters):
        raise CadExportError(
            "Canonical fillet STEP currently requires an extrusion target",
            detail={"feature_id": feature.feature_id, "error_code": "unsupported_fillet_target"},
        )
    if (
        target.parameters.operation != "new_body"
        or target.dependencies
        or target.parameters.extent != "one_sided"
        or target.parameters.direction != "positive"
    ):
        raise CadExportError(
            "Canonical fillet STEP currently requires an independent positive one-sided base extrusion",
            detail={"feature_id": feature.feature_id, "target_feature_id": target.feature_id, "error_code": "unsupported_fillet_graph"},
        )
    body_features = [
        item
        for item in document.features[: terminal_index + 1]
        if item.body_id == feature.body_id and not item.suppressed
    ]
    if [item.feature_id for item in body_features] != [target.feature_id, feature.feature_id]:
        raise CadExportError(
            "Canonical fillet STEP currently supports exactly one base extrusion followed by one fillet",
            detail={"feature_ids": [item.feature_id for item in body_features], "error_code": "unsupported_fillet_graph"},
        )
    report = rebuild_document(document)
    target_record = next(item for item in report.records if item.feature_id == target.feature_id)
    fillet_record = next(item for item in report.records if item.feature_id == feature.feature_id)
    edge_payloads: list[dict[str, Any]] = []
    for resolved in fillet_record.resolved_references:
        edge = next(
            item for item in target_record.generated_topology if item.reference_id == resolved.resolved_reference_id
        )
        values = edge.measurements
        edge_payloads.append(
            {
                "reference_id": edge.reference_id,
                "source_entity_id": edge.source_entity_id,
                "geometric_signature": edge.geometric_signature,
                "endpoints": [
                    [values["x_mm"], values["y_mm"], values["z_min_mm"]],
                    [values["x_mm"], values["y_mm"], values["z_max_mm"]],
                ],
            }
        )
    profile, holes = _source_geometry(document, target)
    return {
        "feature_type": "fillet",
        "base_extrusion": {
            "feature_id": target.feature_id,
            "profile": profile.model_dump(mode="json"),
            "holes": [hole.model_dump(mode="json") for hole in holes],
            "depth_mm": target.parameters.depth_mm,
        },
        "fillet": {
            "feature_id": feature.feature_id,
            "radius_mm": feature.parameters.radius_mm,
            "edges": edge_payloads,
        },
    }


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_feature_artifact(
    document: SketchMathDocument,
    feature_id: str,
    artifact_format: str,
    *,
    output_root: Path,
    cad_adapter: CadAdapter | None = None,
) -> dict[str, Any]:
    normalized_format = artifact_format.strip().lower()
    if normalized_format not in {"step", "stl"}:
        raise UnsupportedCadFormatError(
            "Canonical feature artifacts support STEP and STL",
            detail={"format": artifact_format},
        )
    feature, _ = _validated_feature(document, feature_id)
    feature_root = (
        output_root.resolve()
        / _safe_segment(document.document_id)
        / f"revision_{document.revision}"
        / _safe_segment(feature.feature_id)
    )
    feature_root.mkdir(parents=True, exist_ok=True)

    if normalized_format == "stl":
        mesh = build_feature_body_mesh(document, feature.feature_id)
        path = feature_root / f"{_safe_segment(document.document_id)}_{_safe_segment(feature.feature_id)}_r{document.revision}.stl"
        measurements = write_ascii_stl(mesh, path, solid_name=_safe_segment(feature.feature_id))
        bounds = mesh["metadata"]["expected_bounds_mm"]
        expected_volume = float(mesh["metadata"]["expected_volume_mm3"])
        validation = validate_solid_measurements(
            actual_bbox=measurements["bbox"],
            actual_volume_mm3=measurements["volume_mm3"],
            actual_is_valid_solid=measurements["is_closed_mesh"],
            expected_bbox={
                "xmin": bounds[0],
                "xmax": bounds[1],
                "ymin": bounds[2],
                "ymax": bounds[3],
                "zmin": bounds[4],
                "zmax": bounds[5],
            },
            expected_volume_mm3=expected_volume,
            volume_tolerance_mm3=max(1e-4, abs(expected_volume) * 1e-5),
        )
        if not validation.ok:
            path.unlink(missing_ok=True)
            raise CadExportError(
                validation.message or "STL validation failed",
                detail={"error_code": validation.error_code, **validation.details, **validation.measurements},
            )
        measurements.update(
            {
                "analytic_volume_mm3": expected_volume,
                "volume_error_mm3": measurements["volume_mm3"] - expected_volume,
                "feature_ids": mesh["metadata"]["feature_ids"],
                "layer_count": mesh["metadata"]["layer_count"],
            }
        )
    else:
        if feature.feature_type == "fillet":
            adapter = cad_adapter or CadAdapter(export_dir=feature_root)
            result = adapter.fillet_feature_graph(
                _fillet_step_payload(document, feature),
                selection_set_id=_safe_segment(document.document_id),
                command_id=f"feature_{_safe_segment(feature.feature_id)}_r{document.revision}",
            )
            if result.artifacts is None:
                raise CadExportError("STEP worker did not return an artifact path", detail={"feature_id": feature_id})
            path = Path(result.artifacts.step_path).resolve()
            measurements = {
                **(result.measurements.model_dump(mode="json") if result.measurements is not None else {}),
                **result.metadata,
            }
        elif feature.feature_type != "extrude":
            raise CadExportError(
                "Canonical STEP materialization currently supports extrusion features",
                detail={"feature_id": feature_id, "feature_type": feature.feature_type, "error_code": "unsupported_artifact_feature_type"},
            )
        elif feature.parameters.operation != "new_body" or feature.dependencies:
            raise CadExportError(
                "Canonical STEP materialization currently requires one independent new-body extrusion",
                detail={
                    "feature_id": feature_id,
                    "operation": feature.parameters.operation,
                    "dependency_ids": feature.dependencies,
                    "error_code": "unsupported_feature_graph_for_artifact",
                },
            )
        elif feature.parameters.extent != "one_sided" or feature.parameters.direction != "positive":
            raise CadExportError(
                "Canonical STEP materialization currently supports positive one-sided extrusion",
                detail={
                    "feature_id": feature_id,
                    "extent": feature.parameters.extent,
                    "direction": feature.parameters.direction,
                    "error_code": "unsupported_extrusion_extent_for_artifact",
                },
            )
        else:
            profile, holes = _source_geometry(document, feature)
            adapter = cad_adapter or CadAdapter(export_dir=feature_root)
            result = adapter.extrude_profile(
                profile,
                holes=holes,
                depth=feature.parameters.depth_mm,
                depth_unit=document.units,
                direction="positive_normal",
                output_format="step",
                selection_set_id=_safe_segment(document.document_id),
                command_id=f"feature_{_safe_segment(feature.feature_id)}_r{document.revision}",
            )
            if result.artifacts is None:
                raise CadExportError("STEP worker did not return an artifact path", detail={"feature_id": feature_id})
            path = Path(result.artifacts.step_path).resolve()
            measurements = {
                **(result.measurements.model_dump(mode="json") if result.measurements is not None else {}),
                **result.metadata,
            }

    return {
        "path": str(path.resolve()),
        "format": normalized_format,
        "content_hash": _content_hash(path),
        "size_bytes": path.stat().st_size,
        "measurements": measurements,
        "feature_id": feature.feature_id,
        "document_id": document.document_id,
        "revision": document.revision,
    }
