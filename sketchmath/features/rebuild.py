from __future__ import annotations

import hashlib
import json
import math

from shapely.geometry import Point, Polygon

from sketchmath.models.document import (
    FeatureBuildError,
    FeatureBuildRecord,
    FeatureMeasurements,
    FeatureRebuildReport,
    FeatureRecord,
    HoleParameters,
    ResolvedTopologyReference,
    SemanticTopologyReference,
    SketchMathDocument,
)
from sketchmath.models.entities import Profile2DEntity


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _document_content_hash(document: SketchMathDocument) -> str:
    return _hash_payload(
        document.model_dump(
            mode="json",
            exclude={"last_rebuild": True, "artifacts": True},
        )
    )


def _ordered_features(document: SketchMathDocument) -> tuple[list[FeatureRecord], set[str], dict[str, FeatureBuildError]]:
    features = document.features
    feature_map = {feature.feature_id: feature for feature in features}
    index = {feature.feature_id: position for position, feature in enumerate(features)}
    errors: dict[str, FeatureBuildError] = {}
    indegree: dict[str, int] = {feature.feature_id: 0 for feature in features}
    dependents: dict[str, list[str]] = {feature.feature_id: [] for feature in features}
    for feature in features:
        if len(feature.dependencies) != len(set(feature.dependencies)):
            errors[feature.feature_id] = FeatureBuildError(
                code="duplicate_feature_dependency",
                message="Feature dependencies must be unique.",
                detail={"dependencies": feature.dependencies},
            )
        missing = sorted(set(feature.dependencies) - set(feature_map))
        if missing:
            errors[feature.feature_id] = FeatureBuildError(
                code="missing_feature_dependency",
                message="Feature references a missing dependency.",
                detail={"missing_feature_ids": missing},
            )
        for dependency_id in feature.dependencies:
            if dependency_id not in feature_map:
                continue
            indegree[feature.feature_id] += 1
            dependents[dependency_id].append(feature.feature_id)

    ready = sorted((feature_id for feature_id, count in indegree.items() if count == 0), key=index.__getitem__)
    ordered_ids: list[str] = []
    while ready:
        feature_id = ready.pop(0)
        ordered_ids.append(feature_id)
        for dependent_id in sorted(dependents[feature_id], key=index.__getitem__):
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                ready.append(dependent_id)
                ready.sort(key=index.__getitem__)

    cycle_ids = set(feature_map) - set(ordered_ids)
    ordered_ids.extend(sorted(cycle_ids, key=index.__getitem__))
    for feature_id in cycle_ids:
        errors[feature_id] = FeatureBuildError(
            code="feature_dependency_cycle",
            message="Feature dependency graph contains a cycle.",
            detail={"cycle_feature_ids": sorted(cycle_ids)},
        )
    return [feature_map[feature_id] for feature_id in ordered_ids], cycle_ids, errors


def _profile_for_feature(document: SketchMathDocument, feature: FeatureRecord) -> tuple[Profile2DEntity | None, list[Profile2DEntity], FeatureBuildError | None]:
    sketch = next((candidate for candidate in document.sketches if candidate.sketch_id == feature.sketch_id), None)
    if sketch is None:
        return None, [], FeatureBuildError(
            code="missing_feature_sketch",
            message="Feature source sketch does not exist.",
            detail={"sketch_id": feature.sketch_id},
        )
    try:
        profile = sketch.state.get_entity(feature.profile_id)
    except Exception:
        return None, [], FeatureBuildError(
            code="missing_feature_profile",
            message="Feature source profile does not exist.",
            detail={"sketch_id": feature.sketch_id, "profile_id": feature.profile_id},
        )
    if not isinstance(profile, Profile2DEntity) or not profile.closed:
        return None, [], FeatureBuildError(
            code="invalid_feature_profile",
            message="Feature source must be a closed profile.",
            detail={"sketch_id": feature.sketch_id, "profile_id": feature.profile_id},
        )
    if feature.source_region_id and profile.source_region_id != feature.source_region_id:
        return None, [], FeatureBuildError(
            code="stale_feature_region_reference",
            message="Feature source region no longer matches the profile reference.",
            detail={
                "profile_id": profile.id,
                "expected_source_region_id": feature.source_region_id,
                "actual_source_region_id": profile.source_region_id,
            },
        )
    holes: list[Profile2DEntity] = []
    for hole_id in profile.holes:
        try:
            hole = sketch.state.get_entity(hole_id)
        except Exception:
            return None, [], FeatureBuildError(
                code="missing_feature_profile_hole",
                message="Feature source profile references a missing hole.",
                detail={"profile_id": profile.id, "hole_id": hole_id},
            )
        if not isinstance(hole, Profile2DEntity) or not hole.closed:
            return None, [], FeatureBuildError(
                code="invalid_feature_profile_hole",
                message="Feature source hole must be a closed profile.",
                detail={"profile_id": profile.id, "hole_id": hole_id},
            )
        holes.append(hole)
    return profile, holes, None


def _extrude_measurements(feature: FeatureRecord, profile: Profile2DEntity, holes: list[Profile2DEntity]) -> FeatureMeasurements:
    parameters = feature.parameters
    net_area = profile.area - sum(hole.area for hole in holes)
    if net_area <= 0:
        raise ValueError("profile net area must be positive")
    if parameters.extent == "symmetric":
        z_min, z_max = -parameters.depth_mm / 2.0, parameters.depth_mm / 2.0
    elif parameters.extent == "two_sided":
        second = float(parameters.second_depth_mm or 0.0)
        z_min, z_max = (-second, parameters.depth_mm) if parameters.direction == "positive" else (-parameters.depth_mm, second)
    elif parameters.direction == "negative":
        z_min, z_max = -parameters.depth_mm, 0.0
    else:
        z_min, z_max = 0.0, parameters.depth_mm
    total_depth = z_max - z_min
    xs = [vertex[0] for vertex in profile.vertices]
    ys = [vertex[1] for vertex in profile.vertices]
    sign = -1.0 if parameters.operation == "cut" else 1.0
    return FeatureMeasurements(
        net_profile_area_mm2=net_area,
        volume_delta_mm3=sign * net_area * total_depth,
        bounds_mm=(min(xs), max(xs), min(ys), max(ys), z_min, z_max),
        hole_count=len(holes),
    )


def _semantic_reference(
    feature: FeatureRecord,
    *,
    topology_type: str,
    role: str,
    source_entity_id: str | None,
    ordinal: int,
    geometry: object,
    measurements: dict[str, float | int | str] | None = None,
) -> SemanticTopologyReference:
    identity = {
        "owner_feature_id": feature.feature_id,
        "topology_type": topology_type,
        "role": role,
        "source_entity_id": source_entity_id,
        "ordinal": ordinal,
    }
    return SemanticTopologyReference(
        reference_id=f"topo_{_hash_payload(identity)[:20]}",
        owner_feature_id=feature.feature_id,
        topology_type=topology_type,
        role=role,
        source_entity_id=source_entity_id,
        ordinal=ordinal,
        geometric_signature=_hash_payload({"identity": identity, "geometry": geometry}),
        measurements=measurements or {},
    )


def _extrude_topology(
    feature: FeatureRecord,
    profile: Profile2DEntity,
    holes: list[Profile2DEntity],
    measurements: FeatureMeasurements,
) -> list[SemanticTopologyReference]:
    z_min, z_max = measurements.bounds_mm[-2:]
    topology: list[SemanticTopologyReference] = []
    face_geometry = {
        "outer": profile.vertices,
        "holes": [{"id": hole.id, "vertices": hole.vertices} for hole in holes],
    }
    for ordinal, (role, z_value) in enumerate((("bottom", z_min), ("top", z_max))):
        topology.append(
            _semantic_reference(
                feature,
                topology_type="face",
                role=role,
                source_entity_id=profile.id,
                ordinal=ordinal,
                geometry={**face_geometry, "z": z_value},
                measurements={"area_mm2": measurements.net_profile_area_mm2, "z_mm": z_value},
            )
        )

    segment_count = max(1, len(profile.vertices) - 1)
    source_ids = list(profile.source_curve_ids or profile.source_line_ids)
    if profile.source_circle_id:
        source_ids = [profile.source_circle_id]
    if not source_ids:
        source_ids = [profile.id] * segment_count
    for ordinal, source_id in enumerate(source_ids):
        segment = (
            [profile.vertices[ordinal], profile.vertices[ordinal + 1]]
            if len(source_ids) == segment_count and ordinal + 1 < len(profile.vertices)
            else profile.vertices
        )
        side_geometry = {"segment": segment, "z_min": z_min, "z_max": z_max}
        topology.append(
            _semantic_reference(
                feature,
                topology_type="face",
                role="outer_wall",
                source_entity_id=source_id,
                ordinal=ordinal,
                geometry=side_geometry,
                measurements={"height_mm": z_max - z_min},
            )
        )
        for edge_role, z_value in (("bottom_outer_edge", z_min), ("top_outer_edge", z_max)):
            topology.append(
                _semantic_reference(
                    feature,
                    topology_type="edge",
                    role=edge_role,
                    source_entity_id=source_id,
                    ordinal=ordinal,
                    geometry={"segment": segment, "z": z_value},
                    measurements={"z_mm": z_value},
                )
            )

    for ordinal, hole in enumerate(holes):
        topology.append(
            _semantic_reference(
                feature,
                topology_type="face",
                role="hole_wall",
                source_entity_id=hole.id,
                ordinal=ordinal,
                geometry={"vertices": hole.vertices, "z_min": z_min, "z_max": z_max},
                measurements={"height_mm": z_max - z_min, "area_mm2": hole.area},
            )
        )
        for edge_role, z_value in (("bottom_hole_edge", z_min), ("top_hole_edge", z_max)):
            topology.append(
                _semantic_reference(
                    feature,
                    topology_type="edge",
                    role=edge_role,
                    source_entity_id=hole.id,
                    ordinal=ordinal,
                    geometry={"vertices": hole.vertices, "z": z_value},
                    measurements={"z_mm": z_value},
                )
            )
    return topology


def _hole_measurements(
    feature: FeatureRecord,
    target: FeatureBuildRecord,
    target_profile: Profile2DEntity,
    target_holes: list[Profile2DEntity],
) -> FeatureMeasurements:
    parameters = feature.parameters
    if not isinstance(parameters, HoleParameters) or target.measurements is None:
        raise ValueError("hole feature requires a built target")
    bounds = target.measurements.bounds_mm
    target_depth = bounds[5] - bounds[4]
    shaft_depth = target_depth if parameters.termination == "through" else float(parameters.depth_mm or 0.0)
    if shaft_depth > target_depth:
        raise ValueError("hole depth cannot exceed target thickness")
    shaft_radius = parameters.diameter_mm / 2.0
    outer_radius = shaft_radius
    style_depth = 0.0
    if parameters.style == "counterbore":
        outer_radius = float(parameters.counterbore_diameter_mm or 0.0) / 2.0
        style_depth = float(parameters.counterbore_depth_mm or 0.0)
    elif parameters.style == "countersink":
        outer_radius = float(parameters.countersink_diameter_mm or 0.0) / 2.0
        half_angle = math.radians(float(parameters.countersink_angle_deg or 0.0) / 2.0)
        style_depth = (outer_radius - shaft_radius) / math.tan(half_angle)
    if style_depth > shaft_depth:
        raise ValueError(f"{parameters.style} depth cannot exceed hole depth")

    target_polygon = Polygon(
        target_profile.vertices,
        holes=[hole.vertices for hole in target_holes],
    )
    center = Point(parameters.position_mm)
    if not target_polygon.is_valid or not target_polygon.covers(center):
        raise ValueError("hole center must lie on target material")
    if target_polygon.boundary.distance(center) + 1e-9 < outer_radius:
        raise ValueError("hole profile must remain inside target material")

    shaft_area = math.pi * shaft_radius * shaft_radius
    volume = shaft_area * shaft_depth
    if parameters.style == "counterbore":
        volume += math.pi * (outer_radius * outer_radius - shaft_radius * shaft_radius) * style_depth
    elif parameters.style == "countersink":
        volume += (
            math.pi
            * style_depth
            * (outer_radius * outer_radius + outer_radius * shaft_radius - 2.0 * shaft_radius * shaft_radius)
            / 3.0
        )
    x, y = parameters.position_mm
    z_max = bounds[5]
    return FeatureMeasurements(
        net_profile_area_mm2=shaft_area,
        volume_delta_mm3=-volume,
        bounds_mm=(x - outer_radius, x + outer_radius, y - outer_radius, y + outer_radius, z_max - shaft_depth, z_max),
        hole_count=1,
    )


def _hole_topology(feature: FeatureRecord, measurements: FeatureMeasurements) -> list[SemanticTopologyReference]:
    parameters = feature.parameters
    assert isinstance(parameters, HoleParameters)
    x, y = parameters.position_mm
    z_min, z_max = measurements.bounds_mm[-2:]
    topology = [
        _semantic_reference(
            feature,
            topology_type="face",
            role="hole_wall",
            source_entity_id=feature.feature_id,
            ordinal=0,
            geometry={"center": [x, y], "diameter_mm": parameters.diameter_mm, "z_min": z_min, "z_max": z_max},
            measurements={"diameter_mm": parameters.diameter_mm, "depth_mm": z_max - z_min},
        ),
        _semantic_reference(
            feature,
            topology_type="edge",
            role="hole_rim",
            source_entity_id=feature.feature_id,
            ordinal=0,
            geometry={"center": [x, y], "diameter_mm": parameters.diameter_mm, "z": z_max},
            measurements={"diameter_mm": parameters.diameter_mm, "z_mm": z_max},
        ),
    ]
    if parameters.termination == "blind":
        topology.append(
            _semantic_reference(
                feature,
                topology_type="face",
                role="hole_bottom",
                source_entity_id=feature.feature_id,
                ordinal=0,
                geometry={"center": [x, y], "diameter_mm": parameters.diameter_mm, "z": z_min},
                measurements={"area_mm2": measurements.net_profile_area_mm2, "z_mm": z_min},
            )
        )
    if parameters.style == "counterbore":
        topology.extend(
            [
                _semantic_reference(
                    feature,
                    topology_type="face",
                    role="counterbore_wall",
                    source_entity_id=feature.feature_id,
                    ordinal=0,
                    geometry={
                        "center": [x, y],
                        "diameter_mm": parameters.counterbore_diameter_mm,
                        "depth_mm": parameters.counterbore_depth_mm,
                    },
                ),
                _semantic_reference(
                    feature,
                    topology_type="edge",
                    role="counterbore_step_edge",
                    source_entity_id=feature.feature_id,
                    ordinal=0,
                    geometry={
                        "center": [x, y],
                        "diameter_mm": parameters.counterbore_diameter_mm,
                        "z": z_max - float(parameters.counterbore_depth_mm or 0.0),
                    },
                ),
            ]
        )
    elif parameters.style == "countersink":
        topology.append(
            _semantic_reference(
                feature,
                topology_type="face",
                role="countersink_face",
                source_entity_id=feature.feature_id,
                ordinal=0,
                geometry={
                    "center": [x, y],
                    "diameter_mm": parameters.countersink_diameter_mm,
                    "angle_deg": parameters.countersink_angle_deg,
                },
            )
        )
    return topology


def _resolve_topology_references(
    feature: FeatureRecord,
    records_by_id: dict[str, FeatureBuildRecord],
) -> tuple[list[ResolvedTopologyReference], FeatureBuildError | None]:
    resolved: list[ResolvedTopologyReference] = []
    for selector in feature.topology_references:
        if selector.owner_feature_id not in feature.dependencies:
            return [], FeatureBuildError(
                code="topology_reference_dependency_required",
                message="A topology reference owner must be an explicit feature dependency.",
                detail={
                    "reference_id": selector.reference_id,
                    "owner_feature_id": selector.owner_feature_id,
                    "dependency_ids": feature.dependencies,
                },
            )
        owner_record = records_by_id.get(selector.owner_feature_id)
        candidates = owner_record.generated_topology if owner_record is not None else []
        match = next((item for item in candidates if item.reference_id == selector.reference_id), None)
        if match is None:
            semantic_matches = [
                item
                for item in candidates
                if item.topology_type == selector.topology_type
                and item.role == selector.role
                and item.source_entity_id == selector.source_entity_id
            ]
            if len(semantic_matches) > 1:
                return [], FeatureBuildError(
                    code="ambiguous_topology_reference",
                    message="Topology reference recovery matched more than one candidate.",
                    detail={
                        "reference_id": selector.reference_id,
                        "candidate_reference_ids": [item.reference_id for item in semantic_matches],
                    },
                )
            match = semantic_matches[0] if semantic_matches else None
        if match is None:
            return [], FeatureBuildError(
                code="missing_topology_reference",
                message="Topology reference could not be resolved.",
                detail={
                    "reference_id": selector.reference_id,
                    "owner_feature_id": selector.owner_feature_id,
                    "topology_type": selector.topology_type,
                    "role": selector.role,
                    "source_entity_id": selector.source_entity_id,
                },
            )
        exact = match.reference_id == selector.reference_id and match.geometric_signature == selector.expected_signature
        resolved.append(
            ResolvedTopologyReference(
                requested_reference_id=selector.reference_id,
                resolved_reference_id=match.reference_id,
                owner_feature_id=selector.owner_feature_id,
                topology_type=match.topology_type,
                role=match.role,
                source_entity_id=match.source_entity_id,
                recovery_state="exact" if exact else "recovered",
                expected_signature=selector.expected_signature,
                current_signature=match.geometric_signature,
            )
        )
    return resolved, None


def rebuild_document(document: SketchMathDocument) -> FeatureRebuildReport:
    ordered, _, graph_errors = _ordered_features(document)
    records: list[FeatureBuildRecord] = []
    records_by_id: dict[str, FeatureBuildRecord] = {}
    body_has_base: set[str] = set()
    feature_map = {feature.feature_id: feature for feature in document.features}

    for order, feature in enumerate(ordered):
        base_payload = {
            "feature": feature.model_dump(mode="json"),
            "dependency_signatures": [
                records_by_id[dependency_id].output_signature
                for dependency_id in feature.dependencies
                if dependency_id in records_by_id
            ],
        }
        input_hash = _hash_payload(base_payload)
        error = graph_errors.get(feature.feature_id)
        failed_dependencies = [
            dependency_id
            for dependency_id in feature.dependencies
            if dependency_id in records_by_id and records_by_id[dependency_id].status in {"failed", "blocked"}
        ]
        if error is None and failed_dependencies:
            error = FeatureBuildError(
                code="blocked_feature_dependency",
                message="Feature is blocked by a failed dependency.",
                detail={"failed_dependency_ids": failed_dependencies},
            )
            status = "blocked"
        else:
            status = "failed" if error is not None else "succeeded"

        if error is None and feature.suppressed:
            status = "suppressed"
            output_signature = _hash_payload({"suppressed": feature.feature_id, "input": base_payload})
            record = FeatureBuildRecord(
                feature_id=feature.feature_id,
                order=order,
                status=status,
                input_hash=input_hash,
                output_signature=output_signature,
            )
            records.append(record)
            records_by_id[feature.feature_id] = record
            continue

        profile: Profile2DEntity | None = None
        holes: list[Profile2DEntity] = []
        if error is None and feature.feature_type == "extrude":
            profile, holes, error = _profile_for_feature(document, feature)
            status = "failed" if error is not None else status
        if error is None and feature.parameters.operation == "new_body":
            if feature.dependencies:
                error = FeatureBuildError(
                    code="new_body_dependency_not_allowed",
                    message="A new-body extrusion cannot depend on an existing feature.",
                    detail={"dependency_ids": feature.dependencies},
                )
            elif feature.body_id in body_has_base:
                error = FeatureBuildError(
                    code="body_base_feature_exists",
                    message="Body already has a base feature.",
                    detail={"body_id": feature.body_id},
                )
        elif error is None:
            if not feature.dependencies:
                error = FeatureBuildError(
                    code="boolean_feature_dependency_required",
                    message="Boolean features require an explicit prior feature dependency.",
                    detail={"operation": feature.parameters.operation},
                )
            elif any(feature_map[dependency_id].body_id != feature.body_id for dependency_id in feature.dependencies if dependency_id in feature_map):
                error = FeatureBuildError(
                    code="cross_body_feature_dependency",
                    message="Boolean feature dependencies must belong to the same body.",
                    detail={"body_id": feature.body_id, "dependency_ids": feature.dependencies},
                )
        resolved_references: list[ResolvedTopologyReference] = []
        if error is None:
            resolved_references, error = _resolve_topology_references(feature, records_by_id)
        target_profile: Profile2DEntity | None = None
        target_holes: list[Profile2DEntity] = []
        target_record: FeatureBuildRecord | None = None
        if error is None and feature.feature_type == "hole":
            if len(feature.dependencies) != 1:
                error = FeatureBuildError(
                    code="hole_target_dependency_required",
                    message="A hole feature requires exactly one target feature dependency.",
                    detail={"dependency_ids": feature.dependencies},
                )
            else:
                dependency_id = feature.dependencies[0]
                top_selectors = [
                    selector
                    for selector in feature.topology_references
                    if selector.owner_feature_id == dependency_id
                    and selector.topology_type == "face"
                    and selector.role == "top"
                ]
                if len(top_selectors) != 1:
                    error = FeatureBuildError(
                        code="hole_top_face_reference_required",
                        message="A hole feature requires exactly one semantic top-face reference to its target.",
                        detail={
                            "dependency_id": dependency_id,
                            "top_face_reference_ids": [selector.reference_id for selector in top_selectors],
                        },
                    )
                else:
                    target_feature = feature_map[dependency_id]
                    if target_feature.feature_type != "extrude":
                        error = FeatureBuildError(
                            code="unsupported_hole_target",
                            message="Hole targets are currently limited to extrusion features.",
                            detail={"dependency_id": dependency_id, "feature_type": target_feature.feature_type},
                        )
                    else:
                        target_record = records_by_id.get(dependency_id)
                        target_profile, target_holes, target_error = _profile_for_feature(document, target_feature)
                        if target_error is not None:
                            error = target_error
        if error is not None:
            record = FeatureBuildRecord(
                feature_id=feature.feature_id,
                order=order,
                status="blocked" if status == "blocked" else "failed",
                input_hash=input_hash,
                error=error,
            )
        else:
            try:
                if feature.feature_type == "hole":
                    assert target_record is not None and target_profile is not None
                    measurements = _hole_measurements(feature, target_record, target_profile, target_holes)
                    generated_topology = _hole_topology(feature, measurements)
                    source_geometry: object = {
                        "target_feature_id": feature.dependencies[0],
                        "target_signature": target_record.output_signature,
                    }
                else:
                    assert profile is not None
                    measurements = _extrude_measurements(feature, profile, holes)
                    generated_topology = _extrude_topology(feature, profile, holes, measurements)
                    source_geometry = {
                        "profile": profile.model_dump(mode="json"),
                        "holes": [hole.model_dump(mode="json") for hole in holes],
                    }
            except ValueError as exc:
                record = FeatureBuildRecord(
                    feature_id=feature.feature_id,
                    order=order,
                    status="failed",
                    input_hash=input_hash,
                    error=FeatureBuildError(
                        code="invalid_feature_geometry",
                        message=str(exc),
                        detail={"feature_id": feature.feature_id, "profile_id": profile.id if profile else None},
                    ),
                )
            else:
                output_signature = _hash_payload(
                    {
                        "input": base_payload,
                        "source_geometry": source_geometry,
                        "measurements": measurements.model_dump(mode="json"),
                        "generated_topology": [item.model_dump(mode="json") for item in generated_topology],
                        "resolved_references": [item.model_dump(mode="json") for item in resolved_references],
                    }
                )
                record = FeatureBuildRecord(
                    feature_id=feature.feature_id,
                    order=order,
                    status="succeeded",
                    input_hash=input_hash,
                    output_signature=output_signature,
                    measurements=measurements,
                    generated_topology=generated_topology,
                    resolved_references=resolved_references,
                )
                body_has_base.add(feature.body_id)
        records.append(record)
        records_by_id[feature.feature_id] = record

    return FeatureRebuildReport(
        document_id=document.document_id,
        input_revision=document.revision,
        ok=all(record.status in {"succeeded", "suppressed"} for record in records),
        rebuild_order=[feature.feature_id for feature in ordered],
        records=records,
        content_hash=_document_content_hash(document),
    )
