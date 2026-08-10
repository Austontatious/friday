from __future__ import annotations

import hashlib
import json
import math

from shapely.geometry import Point, Polygon

from sketchmath.models.document import (
    ChamferParameters,
    CircularPatternParameters,
    FeatureBuildError,
    FeatureBuildRecord,
    FeatureMeasurements,
    FeatureRebuildReport,
    FeatureRecord,
    FilletParameters,
    HoleParameters,
    LinearPatternParameters,
    MirrorParameters,
    RevolveParameters,
    ResolvedTopologyReference,
    SemanticTopologyReference,
    SketchMathDocument,
)
from sketchmath.models.entities import Axis2DEntity, ConstructionLine2DEntity, Line2DEntity, Profile2DEntity


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


def _extrude_measurements(
    feature: FeatureRecord,
    profile: Profile2DEntity,
    holes: list[Profile2DEntity],
    *,
    attachment_z: float = 0.0,
) -> FeatureMeasurements:
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
    z_min += attachment_z
    z_max += attachment_z
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

    if not profile.source_circle_id and len(source_ids) == segment_count:
        ring = profile.vertices[:-1] if profile.vertices[0] == profile.vertices[-1] else profile.vertices
        signed_area = sum(
            ring[index][0] * ring[(index + 1) % len(ring)][1]
            - ring[(index + 1) % len(ring)][0] * ring[index][1]
            for index in range(len(ring))
        ) / 2.0
        for ordinal, vertex in enumerate(ring):
            previous_vertex = ring[(ordinal - 1) % len(ring)]
            next_vertex = ring[(ordinal + 1) % len(ring)]
            incoming = (vertex[0] - previous_vertex[0], vertex[1] - previous_vertex[1])
            outgoing = (next_vertex[0] - vertex[0], next_vertex[1] - vertex[1])
            turn = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
            corner_class = "convex" if turn * signed_area > 0 else "concave"
            before_source = source_ids[(ordinal - 1) % len(source_ids)]
            after_source = source_ids[ordinal % len(source_ids)]
            source_id = (
                f"{before_source}|{after_source}"
                if before_source != profile.id or after_source != profile.id
                else f"{profile.id}:vertex:{ordinal}"
            )
            before_length = math.hypot(*incoming)
            after_length = math.hypot(*outgoing)
            topology.append(
                _semantic_reference(
                    feature,
                    topology_type="edge",
                    role="vertical_outer_edge",
                    source_entity_id=source_id,
                    ordinal=ordinal,
                    geometry={
                        "endpoints": [[vertex[0], vertex[1], z_min], [vertex[0], vertex[1], z_max]],
                        "adjacent_source_ids": [before_source, after_source],
                        "corner_class": corner_class,
                    },
                    measurements={
                        "x_mm": vertex[0],
                        "y_mm": vertex[1],
                        "z_min_mm": z_min,
                        "z_max_mm": z_max,
                        "length_mm": z_max - z_min,
                        "max_radius_mm": min(before_length, after_length) / 2.0,
                        "corner_class": corner_class,
                    },
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


def _revolve_axis(document: SketchMathDocument, feature: FeatureRecord) -> tuple[tuple[float, float], tuple[float, float]]:
    parameters = feature.parameters
    if not isinstance(parameters, RevolveParameters):
        raise ValueError("revolve feature requires revolve parameters")
    sketch = next((candidate for candidate in document.sketches if candidate.sketch_id == feature.sketch_id), None)
    if sketch is None:
        raise ValueError("revolve sketch does not exist")
    try:
        axis = sketch.state.get_entity(parameters.axis_entity_id)
    except Exception as exc:
        raise ValueError("revolve axis does not exist") from exc
    if isinstance(axis, Axis2DEntity):
        origin = axis.origin
        vector = axis.direction
    elif isinstance(axis, (Line2DEntity, ConstructionLine2DEntity)):
        origin = axis.start
        vector = (axis.end[0] - axis.start[0], axis.end[1] - axis.start[1])
    else:
        raise ValueError("revolve axis must be an axis, line, or construction line")
    magnitude = math.hypot(*vector)
    if not math.isfinite(magnitude) or magnitude <= 1e-9:
        raise ValueError("revolve axis must have non-zero finite direction")
    return (float(origin[0]), float(origin[1])), (float(vector[0] / magnitude), float(vector[1] / magnitude))


def _revolve_measurements(
    document: SketchMathDocument,
    feature: FeatureRecord,
    profile: Profile2DEntity,
    holes: list[Profile2DEntity],
) -> tuple[FeatureMeasurements, dict[str, object]]:
    parameters = feature.parameters
    if not isinstance(parameters, RevolveParameters):
        raise ValueError("revolve feature requires revolve parameters")
    origin, axis_direction = _revolve_axis(document, feature)
    perpendicular = (-axis_direction[1], axis_direction[0])
    polygon = Polygon(profile.vertices, holes=[hole.vertices for hole in holes])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("revolve profile must define a valid positive material region")
    all_vertices = [*profile.vertices, *(vertex for hole in holes for vertex in hole.vertices)]
    signed_distances = [
        (vertex[0] - origin[0]) * perpendicular[0] + (vertex[1] - origin[1]) * perpendicular[1]
        for vertex in all_vertices
    ]
    if min(signed_distances) < -1e-9 and max(signed_distances) > 1e-9:
        raise ValueError("revolve profile cannot cross its axis")
    centroid = polygon.centroid
    centroid_distance = abs(
        (centroid.x - origin[0]) * perpendicular[0]
        + (centroid.y - origin[1]) * perpendicular[1]
    )
    if centroid_distance <= 1e-9:
        raise ValueError("revolve profile centroid must remain off axis")
    sign = -1.0 if parameters.operation == "cut" else 1.0
    volume = sign * polygon.area * 2.0 * math.pi * centroid_distance

    x_min = math.inf
    x_max = -math.inf
    y_min = math.inf
    y_max = -math.inf
    maximum_radius = 0.0
    for vertex in profile.vertices:
        relative = (vertex[0] - origin[0], vertex[1] - origin[1])
        along = relative[0] * axis_direction[0] + relative[1] * axis_direction[1]
        radius = abs(relative[0] * perpendicular[0] + relative[1] * perpendicular[1])
        center_x = origin[0] + along * axis_direction[0]
        center_y = origin[1] + along * axis_direction[1]
        x_min = min(x_min, center_x - abs(perpendicular[0]) * radius)
        x_max = max(x_max, center_x + abs(perpendicular[0]) * radius)
        y_min = min(y_min, center_y - abs(perpendicular[1]) * radius)
        y_max = max(y_max, center_y + abs(perpendicular[1]) * radius)
        maximum_radius = max(maximum_radius, radius)
    return (
        FeatureMeasurements(
            net_profile_area_mm2=polygon.area,
            volume_delta_mm3=volume,
            bounds_mm=(x_min, x_max, y_min, y_max, -maximum_radius, maximum_radius),
            hole_count=len(holes),
        ),
        {
            "axis_entity_id": parameters.axis_entity_id,
            "origin": origin,
            "direction": axis_direction,
            "centroid_distance_mm": centroid_distance,
        },
    )


def _revolve_topology(
    feature: FeatureRecord,
    profile: Profile2DEntity,
    holes: list[Profile2DEntity],
    axis_geometry: dict[str, object],
) -> list[SemanticTopologyReference]:
    source_ids = list(profile.source_curve_ids or profile.source_line_ids)
    if profile.source_circle_id:
        source_ids = [profile.source_circle_id]
    if not source_ids:
        source_ids = [profile.id]
    topology = [
        _semantic_reference(
            feature,
            topology_type="face",
            role="revolved_outer_face",
            source_entity_id=source_id,
            ordinal=ordinal,
            geometry={"profile_vertices": profile.vertices, "axis": axis_geometry},
            measurements={"angle_deg": 360.0},
        )
        for ordinal, source_id in enumerate(source_ids)
    ]
    topology.extend(
        _semantic_reference(
            feature,
            topology_type="face",
            role="revolved_inner_face",
            source_entity_id=hole.id,
            ordinal=ordinal,
            geometry={"profile_vertices": hole.vertices, "axis": axis_geometry},
            measurements={"angle_deg": 360.0},
        )
        for ordinal, hole in enumerate(holes)
    )
    return topology


def _hole_measurements(
    feature: FeatureRecord,
    target: FeatureBuildRecord,
    target_profile: Profile2DEntity,
    target_holes: list[Profile2DEntity],
    target_body_bounds: tuple[float, float, float, float, float, float],
) -> FeatureMeasurements:
    parameters = feature.parameters
    if not isinstance(parameters, HoleParameters) or target.measurements is None:
        raise ValueError("hole feature requires a built target")
    bounds = target.measurements.bounds_mm
    target_depth = bounds[5] - target_body_bounds[4]
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


def _dependency_body_bounds(
    feature_id: str,
    records_by_id: dict[str, FeatureBuildRecord],
    feature_map: dict[str, FeatureRecord],
) -> tuple[float, float, float, float, float, float] | None:
    pending = [feature_id]
    visited: set[str] = set()
    bounds: list[tuple[float, float, float, float, float, float]] = []
    while pending:
        current_id = pending.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        record = records_by_id.get(current_id)
        current = feature_map.get(current_id)
        if record is not None and record.measurements is not None and current is not None and current.parameters.operation != "cut":
            bounds.append(record.measurements.bounds_mm)
        if current is not None:
            pending.extend(current.dependencies)
    if not bounds:
        return None
    return (
        min(item[0] for item in bounds),
        max(item[1] for item in bounds),
        min(item[2] for item in bounds),
        max(item[3] for item in bounds),
        min(item[4] for item in bounds),
        max(item[5] for item in bounds),
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


def _linear_pattern_contract(
    feature: FeatureRecord,
    records_by_id: dict[str, FeatureBuildRecord],
    feature_map: dict[str, FeatureRecord],
    document: SketchMathDocument,
) -> tuple[FeatureMeasurements | None, list[SemanticTopologyReference], dict[str, object], FeatureBuildError | None]:
    parameters = feature.parameters
    if not isinstance(parameters, LinearPatternParameters):
        return None, [], {}, FeatureBuildError(
            code="invalid_linear_pattern_parameters",
            message="Linear pattern feature requires matching parameters.",
        )
    if len(feature.dependencies) != 1:
        return None, [], {}, FeatureBuildError(
            code="linear_pattern_seed_dependency_required",
            message="A linear pattern requires exactly one seed feature dependency.",
            detail={"dependency_ids": feature.dependencies},
        )
    seed_id = feature.dependencies[0]
    seed_feature = feature_map.get(seed_id)
    seed_record = records_by_id.get(seed_id)
    if (
        seed_feature is None
        or seed_record is None
        or seed_record.measurements is None
        or seed_feature.feature_type != "hole"
        or not isinstance(seed_feature.parameters, HoleParameters)
    ):
        return None, [], {}, FeatureBuildError(
            code="unsupported_linear_pattern_seed",
            message="Canonical linear pattern currently supports a built hole seed.",
            detail={"seed_feature_id": seed_id, "feature_type": seed_feature.feature_type if seed_feature else None},
        )
    if not seed_feature.dependencies:
        return None, [], {}, FeatureBuildError(
            code="linear_pattern_seed_target_missing",
            message="The hole seed must retain its target dependency.",
            detail={"seed_feature_id": seed_id},
        )
    target_feature = feature_map.get(seed_feature.dependencies[0])
    if target_feature is None or target_feature.feature_type != "extrude":
        return None, [], {}, FeatureBuildError(
            code="unsupported_linear_pattern_target",
            message="Canonical hole patterns currently require an extrusion target.",
            detail={"target_feature_id": seed_feature.dependencies[0], "feature_type": target_feature.feature_type if target_feature else None},
        )
    target_profile, target_holes, target_error = _profile_for_feature(document, target_feature)
    if target_error is not None or target_profile is None:
        return None, [], {}, target_error

    magnitude = math.hypot(*parameters.direction_xy)
    direction = (parameters.direction_xy[0] / magnitude, parameters.direction_xy[1] / magnitude)
    target_polygon = Polygon(target_profile.vertices, holes=[hole.vertices for hole in target_holes])
    seed_center = seed_feature.parameters.position_mm
    radius = max(
        seed_feature.parameters.diameter_mm,
        float(seed_feature.parameters.counterbore_diameter_mm or 0.0),
        float(seed_feature.parameters.countersink_diameter_mm or 0.0),
    ) / 2.0
    centers = [
        (
            seed_center[0] + direction[0] * parameters.spacing_mm * index,
            seed_center[1] + direction[1] * parameters.spacing_mm * index,
        )
        for index in range(parameters.count)
    ]
    for index, center in enumerate(centers[1:], start=1):
        point = Point(center)
        if not target_polygon.covers(point) or target_polygon.boundary.distance(point) + 1e-9 < radius:
            return None, [], {}, FeatureBuildError(
                code="linear_pattern_instance_outside_target",
                message="Every patterned hole must remain inside target material.",
                detail={"instance_index": index, "center_mm": center, "radius_mm": radius},
            )
        if any(math.dist(center, previous) < 2.0 * radius - 1e-9 for previous in centers[:index]):
            return None, [], {}, FeatureBuildError(
                code="linear_pattern_instances_overlap",
                message="Patterned holes cannot overlap.",
                detail={"instance_index": index, "center_mm": center, "radius_mm": radius},
            )

    seed_measurements = seed_record.measurements
    new_centers = centers[1:]
    seed_bounds = seed_measurements.bounds_mm
    translated_bounds = [
        (
            seed_bounds[0] + center[0] - seed_center[0],
            seed_bounds[1] + center[0] - seed_center[0],
            seed_bounds[2] + center[1] - seed_center[1],
            seed_bounds[3] + center[1] - seed_center[1],
            seed_bounds[4],
            seed_bounds[5],
        )
        for center in new_centers
    ]
    measurements = FeatureMeasurements(
        net_profile_area_mm2=seed_measurements.net_profile_area_mm2 * len(new_centers),
        volume_delta_mm3=seed_measurements.volume_delta_mm3 * len(new_centers),
        bounds_mm=(
            min(bounds[0] for bounds in translated_bounds),
            max(bounds[1] for bounds in translated_bounds),
            min(bounds[2] for bounds in translated_bounds),
            max(bounds[3] for bounds in translated_bounds),
            min(bounds[4] for bounds in translated_bounds),
            max(bounds[5] for bounds in translated_bounds),
        ),
        hole_count=seed_measurements.hole_count * len(new_centers),
    )
    generated_topology: list[SemanticTopologyReference] = []
    for instance_index, center in enumerate(new_centers, start=1):
        offset = (center[0] - seed_center[0], center[1] - seed_center[1])
        for seed_topology in seed_record.generated_topology:
            generated_topology.append(
                _semantic_reference(
                    feature,
                    topology_type=seed_topology.topology_type,
                    role=seed_topology.role,
                    source_entity_id=seed_topology.reference_id,
                    ordinal=len(generated_topology),
                    geometry={
                        "seed_reference_id": seed_topology.reference_id,
                        "instance_index": instance_index,
                        "offset_mm": offset,
                    },
                    measurements={
                        **seed_topology.measurements,
                        "instance_index": instance_index,
                        "offset_x_mm": offset[0],
                        "offset_y_mm": offset[1],
                    },
                )
            )
    source_geometry = {
        "seed_feature_id": seed_id,
        "seed_signature": seed_record.output_signature,
        "count": parameters.count,
        "spacing_mm": parameters.spacing_mm,
        "direction": direction,
        "centers_mm": centers,
    }
    return measurements, generated_topology, source_geometry, None


def _circular_pattern_contract(
    feature: FeatureRecord,
    records_by_id: dict[str, FeatureBuildRecord],
    feature_map: dict[str, FeatureRecord],
    document: SketchMathDocument,
) -> tuple[FeatureMeasurements | None, list[SemanticTopologyReference], dict[str, object], FeatureBuildError | None]:
    parameters = feature.parameters
    if not isinstance(parameters, CircularPatternParameters):
        return None, [], {}, FeatureBuildError(
            code="invalid_circular_pattern_parameters",
            message="Circular pattern feature requires matching parameters.",
        )
    if len(feature.dependencies) != 1:
        return None, [], {}, FeatureBuildError(
            code="circular_pattern_seed_dependency_required",
            message="A circular pattern requires exactly one seed feature dependency.",
            detail={"dependency_ids": feature.dependencies},
        )
    seed_id = feature.dependencies[0]
    seed_feature = feature_map.get(seed_id)
    seed_record = records_by_id.get(seed_id)
    if (
        seed_feature is None
        or seed_record is None
        or seed_record.measurements is None
        or seed_feature.feature_type != "hole"
        or not isinstance(seed_feature.parameters, HoleParameters)
    ):
        return None, [], {}, FeatureBuildError(
            code="unsupported_circular_pattern_seed",
            message="Canonical circular pattern currently supports a built hole seed.",
            detail={"seed_feature_id": seed_id, "feature_type": seed_feature.feature_type if seed_feature else None},
        )
    if not seed_feature.dependencies:
        return None, [], {}, FeatureBuildError(
            code="circular_pattern_seed_target_missing",
            message="The hole seed must retain its target dependency.",
            detail={"seed_feature_id": seed_id},
        )
    target_feature = feature_map.get(seed_feature.dependencies[0])
    if target_feature is None or target_feature.feature_type != "extrude":
        return None, [], {}, FeatureBuildError(
            code="unsupported_circular_pattern_target",
            message="Canonical circular hole patterns currently require an extrusion target.",
            detail={"target_feature_id": seed_feature.dependencies[0], "feature_type": target_feature.feature_type if target_feature else None},
        )
    target_profile, target_holes, target_error = _profile_for_feature(document, target_feature)
    if target_error is not None or target_profile is None:
        return None, [], {}, target_error

    seed_center = seed_feature.parameters.position_mm
    center = parameters.center_mm
    radial_vector = (seed_center[0] - center[0], seed_center[1] - center[1])
    radial_distance = math.hypot(*radial_vector)
    if radial_distance <= 1e-9:
        return None, [], {}, FeatureBuildError(
            code="circular_pattern_seed_on_axis",
            message="Circular pattern seed must remain away from the pattern center.",
            detail={"seed_center_mm": seed_center, "pattern_center_mm": center},
        )
    direction_sign = 1.0 if parameters.direction == "counterclockwise" else -1.0
    angle_step = direction_sign * 2.0 * math.pi / parameters.count
    centers: list[tuple[float, float]] = []
    for index in range(parameters.count):
        angle = angle_step * index
        cosine, sine = math.cos(angle), math.sin(angle)
        centers.append(
            (
                center[0] + radial_vector[0] * cosine - radial_vector[1] * sine,
                center[1] + radial_vector[0] * sine + radial_vector[1] * cosine,
            )
        )

    target_polygon = Polygon(target_profile.vertices, holes=[hole.vertices for hole in target_holes])
    radius = max(
        seed_feature.parameters.diameter_mm,
        float(seed_feature.parameters.counterbore_diameter_mm or 0.0),
        float(seed_feature.parameters.countersink_diameter_mm or 0.0),
    ) / 2.0
    for index, instance_center in enumerate(centers[1:], start=1):
        point = Point(instance_center)
        if not target_polygon.covers(point) or target_polygon.boundary.distance(point) + 1e-9 < radius:
            return None, [], {}, FeatureBuildError(
                code="circular_pattern_instance_outside_target",
                message="Every patterned hole must remain inside target material.",
                detail={"instance_index": index, "center_mm": instance_center, "radius_mm": radius},
            )
        if any(math.dist(instance_center, previous) < 2.0 * radius - 1e-9 for previous in centers[:index]):
            return None, [], {}, FeatureBuildError(
                code="circular_pattern_instances_overlap",
                message="Patterned holes cannot overlap.",
                detail={"instance_index": index, "center_mm": instance_center, "radius_mm": radius},
            )

    seed_measurements = seed_record.measurements
    new_centers = centers[1:]
    translated_bounds = [
        (
            instance_center[0] - radius,
            instance_center[0] + radius,
            instance_center[1] - radius,
            instance_center[1] + radius,
            seed_measurements.bounds_mm[4],
            seed_measurements.bounds_mm[5],
        )
        for instance_center in new_centers
    ]
    measurements = FeatureMeasurements(
        net_profile_area_mm2=seed_measurements.net_profile_area_mm2 * len(new_centers),
        volume_delta_mm3=seed_measurements.volume_delta_mm3 * len(new_centers),
        bounds_mm=(
            min(bounds[0] for bounds in translated_bounds),
            max(bounds[1] for bounds in translated_bounds),
            min(bounds[2] for bounds in translated_bounds),
            max(bounds[3] for bounds in translated_bounds),
            min(bounds[4] for bounds in translated_bounds),
            max(bounds[5] for bounds in translated_bounds),
        ),
        hole_count=seed_measurements.hole_count * len(new_centers),
    )
    generated_topology: list[SemanticTopologyReference] = []
    for instance_index, instance_center in enumerate(new_centers, start=1):
        rotation_deg = math.degrees(angle_step * instance_index)
        offset = (instance_center[0] - seed_center[0], instance_center[1] - seed_center[1])
        for seed_topology in seed_record.generated_topology:
            generated_topology.append(
                _semantic_reference(
                    feature,
                    topology_type=seed_topology.topology_type,
                    role=seed_topology.role,
                    source_entity_id=seed_topology.reference_id,
                    ordinal=len(generated_topology),
                    geometry={
                        "seed_reference_id": seed_topology.reference_id,
                        "instance_index": instance_index,
                        "pattern_center_mm": center,
                        "rotation_deg": rotation_deg,
                        "center_mm": instance_center,
                    },
                    measurements={
                        **seed_topology.measurements,
                        "instance_index": instance_index,
                        "rotation_deg": rotation_deg,
                        "offset_x_mm": offset[0],
                        "offset_y_mm": offset[1],
                    },
                )
            )
    source_geometry = {
        "seed_feature_id": seed_id,
        "seed_signature": seed_record.output_signature,
        "count": parameters.count,
        "center_mm": center,
        "direction": parameters.direction,
        "angle_deg": parameters.angle_deg,
        "centers_mm": centers,
    }
    return measurements, generated_topology, source_geometry, None


def _mirror_line(document: SketchMathDocument, feature: FeatureRecord) -> tuple[tuple[float, float], tuple[float, float]]:
    parameters = feature.parameters
    if not isinstance(parameters, MirrorParameters):
        raise ValueError("mirror feature requires mirror parameters")
    sketch = next((candidate for candidate in document.sketches if candidate.sketch_id == feature.sketch_id), None)
    if sketch is None:
        raise ValueError("mirror sketch does not exist")
    try:
        axis = sketch.state.get_entity(parameters.mirror_line_entity_id)
    except Exception as exc:
        raise ValueError("mirror line does not exist") from exc
    if isinstance(axis, Axis2DEntity):
        origin = axis.origin
        vector = axis.direction
    elif isinstance(axis, (Line2DEntity, ConstructionLine2DEntity)):
        origin = axis.start
        vector = (axis.end[0] - axis.start[0], axis.end[1] - axis.start[1])
    else:
        raise ValueError("mirror reference must be an axis, line, or construction line")
    magnitude = math.hypot(*vector)
    if not math.isfinite(magnitude) or magnitude <= 1e-9:
        raise ValueError("mirror line must have non-zero finite direction")
    return (float(origin[0]), float(origin[1])), (float(vector[0] / magnitude), float(vector[1] / magnitude))


def _mirror_contract(
    feature: FeatureRecord,
    records_by_id: dict[str, FeatureBuildRecord],
    feature_map: dict[str, FeatureRecord],
    document: SketchMathDocument,
) -> tuple[FeatureMeasurements | None, list[SemanticTopologyReference], dict[str, object], FeatureBuildError | None]:
    if not isinstance(feature.parameters, MirrorParameters):
        return None, [], {}, FeatureBuildError(
            code="invalid_mirror_parameters",
            message="Mirror feature requires matching parameters.",
        )
    if len(feature.dependencies) != 1:
        return None, [], {}, FeatureBuildError(
            code="mirror_seed_dependency_required",
            message="A feature mirror requires exactly one seed feature dependency.",
            detail={"dependency_ids": feature.dependencies},
        )
    seed_id = feature.dependencies[0]
    seed_feature = feature_map.get(seed_id)
    seed_record = records_by_id.get(seed_id)
    if (
        seed_feature is None
        or seed_record is None
        or seed_record.measurements is None
        or seed_feature.feature_type != "hole"
        or not isinstance(seed_feature.parameters, HoleParameters)
    ):
        return None, [], {}, FeatureBuildError(
            code="unsupported_mirror_seed",
            message="Canonical feature mirror currently supports a built hole seed.",
            detail={"seed_feature_id": seed_id, "feature_type": seed_feature.feature_type if seed_feature else None},
        )
    if not seed_feature.dependencies:
        return None, [], {}, FeatureBuildError(
            code="mirror_seed_target_missing",
            message="The hole seed must retain its target dependency.",
            detail={"seed_feature_id": seed_id},
        )
    target_feature = feature_map.get(seed_feature.dependencies[0])
    if target_feature is None or target_feature.feature_type != "extrude":
        return None, [], {}, FeatureBuildError(
            code="unsupported_mirror_target",
            message="Canonical mirrored holes currently require an extrusion target.",
            detail={"target_feature_id": seed_feature.dependencies[0], "feature_type": target_feature.feature_type if target_feature else None},
        )
    target_profile, target_holes, target_error = _profile_for_feature(document, target_feature)
    if target_error is not None or target_profile is None:
        return None, [], {}, target_error
    try:
        line_origin, line_direction = _mirror_line(document, feature)
    except ValueError as exc:
        return None, [], {}, FeatureBuildError(
            code="invalid_mirror_line",
            message=str(exc),
            detail={"mirror_line_entity_id": feature.parameters.mirror_line_entity_id},
        )

    seed_center = seed_feature.parameters.position_mm
    relative = (seed_center[0] - line_origin[0], seed_center[1] - line_origin[1])
    along = relative[0] * line_direction[0] + relative[1] * line_direction[1]
    projection = (line_origin[0] + along * line_direction[0], line_origin[1] + along * line_direction[1])
    mirrored_center = (2.0 * projection[0] - seed_center[0], 2.0 * projection[1] - seed_center[1])
    distance_to_line = math.dist(seed_center, projection)
    if distance_to_line <= 1e-9:
        return None, [], {}, FeatureBuildError(
            code="mirror_seed_on_line",
            message="Mirror seed must remain away from the mirror line.",
            detail={"seed_center_mm": seed_center, "mirror_line_entity_id": feature.parameters.mirror_line_entity_id},
        )
    radius = max(
        seed_feature.parameters.diameter_mm,
        float(seed_feature.parameters.counterbore_diameter_mm or 0.0),
        float(seed_feature.parameters.countersink_diameter_mm or 0.0),
    ) / 2.0
    if math.dist(seed_center, mirrored_center) < 2.0 * radius - 1e-9:
        return None, [], {}, FeatureBuildError(
            code="mirror_instance_overlaps_seed",
            message="Mirrored hole cannot overlap its seed.",
            detail={"seed_center_mm": seed_center, "mirrored_center_mm": mirrored_center, "radius_mm": radius},
        )
    target_polygon = Polygon(target_profile.vertices, holes=[hole.vertices for hole in target_holes])
    point = Point(mirrored_center)
    if not target_polygon.covers(point) or target_polygon.boundary.distance(point) + 1e-9 < radius:
        return None, [], {}, FeatureBuildError(
            code="mirror_instance_outside_target",
            message="Mirrored hole must remain inside target material.",
            detail={"mirrored_center_mm": mirrored_center, "radius_mm": radius},
        )

    seed_measurements = seed_record.measurements
    measurements = FeatureMeasurements(
        net_profile_area_mm2=seed_measurements.net_profile_area_mm2,
        volume_delta_mm3=seed_measurements.volume_delta_mm3,
        bounds_mm=(
            mirrored_center[0] - radius,
            mirrored_center[0] + radius,
            mirrored_center[1] - radius,
            mirrored_center[1] + radius,
            seed_measurements.bounds_mm[4],
            seed_measurements.bounds_mm[5],
        ),
        hole_count=seed_measurements.hole_count,
    )
    offset = (mirrored_center[0] - seed_center[0], mirrored_center[1] - seed_center[1])
    generated_topology = [
        _semantic_reference(
            feature,
            topology_type=seed_topology.topology_type,
            role=seed_topology.role,
            source_entity_id=seed_topology.reference_id,
            ordinal=ordinal,
            geometry={
                "seed_reference_id": seed_topology.reference_id,
                "mirror_line_entity_id": feature.parameters.mirror_line_entity_id,
                "line_origin": line_origin,
                "line_direction": line_direction,
                "mirrored_center_mm": mirrored_center,
            },
            measurements={
                **seed_topology.measurements,
                "offset_x_mm": offset[0],
                "offset_y_mm": offset[1],
                "mirrored_center_x_mm": mirrored_center[0],
                "mirrored_center_y_mm": mirrored_center[1],
            },
        )
        for ordinal, seed_topology in enumerate(seed_record.generated_topology)
    ]
    source_geometry = {
        "seed_feature_id": seed_id,
        "seed_signature": seed_record.output_signature,
        "mirror_line_entity_id": feature.parameters.mirror_line_entity_id,
        "line_origin": line_origin,
        "line_direction": line_direction,
        "seed_center_mm": seed_center,
        "mirrored_center_mm": mirrored_center,
    }
    return measurements, generated_topology, source_geometry, None


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


def _edge_finish_contract(
    feature: FeatureRecord,
    records_by_id: dict[str, FeatureBuildRecord],
    feature_map: dict[str, FeatureRecord],
    resolved_references: list[ResolvedTopologyReference],
) -> tuple[list[SemanticTopologyReference], FeatureBuildError | None]:
    parameters = feature.parameters
    if feature.feature_type == "fillet" and isinstance(parameters, FilletParameters):
        size_mm = parameters.radius_mm
        size_name = "radius"
        surface_role = "fillet_surface"
    elif feature.feature_type == "chamfer" and isinstance(parameters, ChamferParameters):
        size_mm = parameters.distance_mm
        size_name = "distance"
        surface_role = "chamfer_surface"
    else:
        return [], FeatureBuildError(
            code=f"invalid_{feature.feature_type}_parameters",
            message=f"{feature.feature_type.title()} feature requires matching parameters.",
        )
    feature_name = feature.feature_type
    if len(feature.dependencies) != 1:
        return [], FeatureBuildError(
            code=f"{feature_name}_target_dependency_required",
            message=f"A {feature_name} requires exactly one target feature dependency.",
            detail={"dependency_ids": feature.dependencies},
        )
    target_id = feature.dependencies[0]
    target_feature = feature_map.get(target_id)
    target_record = records_by_id.get(target_id)
    if target_feature is None or target_record is None or target_feature.feature_type != "extrude":
        return [], FeatureBuildError(
            code=f"unsupported_{feature_name}_target",
            message=f"Canonical {feature_name} currently targets an extrusion feature.",
            detail={"dependency_id": target_id, "feature_type": target_feature.feature_type if target_feature else None},
        )
    selectors = [
        selector
        for selector in feature.topology_references
        if selector.owner_feature_id == target_id and selector.topology_type == "edge"
    ]
    if not selectors:
        return [], FeatureBuildError(
            code=f"{feature_name}_edge_reference_required",
            message=f"A {feature_name} requires at least one semantic target-edge reference.",
            detail={"dependency_id": target_id},
        )
    if len({selector.reference_id for selector in selectors}) != len(selectors):
        return [], FeatureBuildError(
            code=f"duplicate_{feature_name}_edge_reference",
            message=f"A {feature_name} edge may only be selected once.",
            detail={"reference_ids": [selector.reference_id for selector in selectors]},
        )
    generated: list[SemanticTopologyReference] = []
    for ordinal, selector in enumerate(selectors):
        resolved = next(
            (item for item in resolved_references if item.requested_reference_id == selector.reference_id),
            None,
        )
        target_edge = next(
            (
                item
                for item in target_record.generated_topology
                if resolved is not None and item.reference_id == resolved.resolved_reference_id
            ),
            None,
        )
        if target_edge is None or target_edge.role != "vertical_outer_edge":
            return [], FeatureBuildError(
                code=f"unsupported_{feature_name}_edge",
                message=f"Canonical {feature_name} currently supports convex outer vertical extrusion edges.",
                detail={"reference_id": selector.reference_id, "role": target_edge.role if target_edge else selector.role},
            )
        if target_edge.measurements.get("corner_class") != "convex":
            return [], FeatureBuildError(
                code=f"unsupported_concave_{feature_name}",
                message=f"Canonical {feature_name} currently supports convex outer corners only.",
                detail={"reference_id": selector.reference_id},
            )
        max_radius = target_edge.measurements.get("max_radius_mm")
        if not isinstance(max_radius, (int, float)) or size_mm >= float(max_radius) - 1e-9:
            return [], FeatureBuildError(
                code=f"{feature_name}_{size_name}_exceeds_adjacent_edges",
                message=f"{feature_name.title()} {size_name} must be smaller than half both adjacent edge lengths.",
                detail={"reference_id": selector.reference_id, f"{size_name}_mm": size_mm, "max_size_mm": max_radius},
            )
        generated.append(
            _semantic_reference(
                feature,
                topology_type="face",
                role=surface_role,
                source_entity_id=target_edge.source_entity_id,
                ordinal=ordinal,
                geometry={"target_signature": target_edge.geometric_signature, f"{size_name}_mm": size_mm},
                measurements={f"{size_name}_mm": size_mm, "target_edge_reference_id": target_edge.reference_id},
            )
        )
    return generated, None


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
        if error is None and feature.feature_type in {"extrude", "revolve"}:
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
        edge_finish_topology: list[SemanticTopologyReference] = []
        if error is None and feature.feature_type in {"fillet", "chamfer"}:
            edge_finish_topology, error = _edge_finish_contract(feature, records_by_id, feature_map, resolved_references)
        pattern_measurements: FeatureMeasurements | None = None
        pattern_topology: list[SemanticTopologyReference] = []
        pattern_source_geometry: dict[str, object] = {}
        if error is None and feature.feature_type == "linear_pattern":
            pattern_measurements, pattern_topology, pattern_source_geometry, error = _linear_pattern_contract(
                feature,
                records_by_id,
                feature_map,
                document,
            )
        if error is None and feature.feature_type == "circular_pattern":
            pattern_measurements, pattern_topology, pattern_source_geometry, error = _circular_pattern_contract(
                feature,
                records_by_id,
                feature_map,
                document,
            )
        if error is None and feature.feature_type == "mirror":
            pattern_measurements, pattern_topology, pattern_source_geometry, error = _mirror_contract(
                feature,
                records_by_id,
                feature_map,
                document,
            )
        if error is None and feature.feature_type == "revolve":
            assert isinstance(feature.parameters, RevolveParameters)
            if not math.isclose(feature.parameters.angle_deg, 360.0, abs_tol=1e-9):
                error = FeatureBuildError(
                    code="unsupported_partial_revolve",
                    message="Canonical revolve currently supports a full 360-degree sweep.",
                    detail={"angle_deg": feature.parameters.angle_deg},
                )
            elif feature.parameters.operation != "new_body":
                if len(feature.dependencies) != 1:
                    error = FeatureBuildError(
                        code="boolean_target_dependency_required",
                        message="An add or cut revolve requires exactly one target feature dependency.",
                        detail={"dependency_ids": feature.dependencies},
                    )
                else:
                    dependency_id = feature.dependencies[0]
                    face_selectors = [
                        selector
                        for selector in feature.topology_references
                        if selector.owner_feature_id == dependency_id and selector.topology_type == "face"
                    ]
                    if len(face_selectors) != 1:
                        error = FeatureBuildError(
                            code="feature_attachment_reference_required",
                            message="An add or cut revolve requires exactly one semantic target-face reference.",
                            detail={
                                "dependency_id": dependency_id,
                                "attachment_reference_ids": [selector.reference_id for selector in face_selectors],
                            },
                        )
        attachment_z = 0.0
        if error is None and feature.feature_type == "extrude" and feature.parameters.operation != "new_body":
            if len(feature.dependencies) != 1:
                error = FeatureBuildError(
                    code="boolean_target_dependency_required",
                    message="An add or cut extrusion requires exactly one target feature dependency.",
                    detail={"dependency_ids": feature.dependencies},
                )
            else:
                dependency_id = feature.dependencies[0]
                face_selectors = [
                    selector
                    for selector in feature.topology_references
                    if selector.owner_feature_id == dependency_id
                    and selector.topology_type == "face"
                    and selector.role in {"top", "bottom"}
                ]
                if len(face_selectors) != 1:
                    error = FeatureBuildError(
                        code="feature_attachment_reference_required",
                        message="An add or cut extrusion requires exactly one semantic top- or bottom-face attachment.",
                        detail={
                            "dependency_id": dependency_id,
                            "attachment_reference_ids": [selector.reference_id for selector in face_selectors],
                        },
                    )
                else:
                    selector = face_selectors[0]
                    resolved = next(
                        (item for item in resolved_references if item.requested_reference_id == selector.reference_id),
                        None,
                    )
                    owner_record = records_by_id.get(dependency_id)
                    attachment = next(
                        (
                            item
                            for item in owner_record.generated_topology
                            if resolved is not None and item.reference_id == resolved.resolved_reference_id
                        ),
                        None,
                    ) if owner_record is not None else None
                    z_value = attachment.measurements.get("z_mm") if attachment is not None else None
                    if not isinstance(z_value, (int, float)):
                        error = FeatureBuildError(
                            code="invalid_feature_attachment",
                            message="Feature attachment does not provide a usable face position.",
                            detail={"reference_id": selector.reference_id},
                        )
                    else:
                        attachment_z = float(z_value)
                        if feature.parameters.extent == "one_sided":
                            expected_direction = (
                                "positive"
                                if (selector.role == "top") == (feature.parameters.operation == "add")
                                else "negative"
                            )
                            if feature.parameters.direction != expected_direction:
                                error = FeatureBuildError(
                                    code="feature_direction_away_from_target",
                                    message="One-sided add/cut direction must enter or extend from the attached target face.",
                                    detail={
                                        "operation": feature.parameters.operation,
                                        "face_role": selector.role,
                                        "direction": feature.parameters.direction,
                                        "expected_direction": expected_direction,
                                    },
                                )
        target_profile: Profile2DEntity | None = None
        target_holes: list[Profile2DEntity] = []
        target_record: FeatureBuildRecord | None = None
        target_body_bounds: tuple[float, float, float, float, float, float] | None = None
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
                        target_body_bounds = _dependency_body_bounds(dependency_id, records_by_id, feature_map)
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
                    assert target_record is not None and target_profile is not None and target_body_bounds is not None
                    measurements = _hole_measurements(feature, target_record, target_profile, target_holes, target_body_bounds)
                    generated_topology = _hole_topology(feature, measurements)
                    source_geometry: object = {
                        "target_feature_id": feature.dependencies[0],
                        "target_signature": target_record.output_signature,
                    }
                elif feature.feature_type == "revolve":
                    assert profile is not None
                    measurements, axis_geometry = _revolve_measurements(document, feature, profile, holes)
                    generated_topology = _revolve_topology(feature, profile, holes, axis_geometry)
                    source_geometry = {
                        "profile": profile.model_dump(mode="json"),
                        "holes": [hole.model_dump(mode="json") for hole in holes],
                        "axis": axis_geometry,
                    }
                elif feature.feature_type == "fillet":
                    assert isinstance(feature.parameters, FilletParameters)
                    measurements = None
                    generated_topology = edge_finish_topology
                    source_geometry = {
                        "target_feature_id": feature.dependencies[0],
                        "target_signature": records_by_id[feature.dependencies[0]].output_signature,
                        "radius_mm": feature.parameters.radius_mm,
                    }
                elif feature.feature_type == "chamfer":
                    assert isinstance(feature.parameters, ChamferParameters)
                    measurements = None
                    generated_topology = edge_finish_topology
                    source_geometry = {
                        "target_feature_id": feature.dependencies[0],
                        "target_signature": records_by_id[feature.dependencies[0]].output_signature,
                        "distance_mm": feature.parameters.distance_mm,
                    }
                elif feature.feature_type in {"linear_pattern", "circular_pattern", "mirror"}:
                    assert pattern_measurements is not None
                    measurements = pattern_measurements
                    generated_topology = pattern_topology
                    source_geometry = pattern_source_geometry
                else:
                    assert profile is not None
                    measurements = _extrude_measurements(feature, profile, holes, attachment_z=attachment_z)
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
                        "measurements": measurements.model_dump(mode="json") if measurements is not None else None,
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
                    measurement_coverage="kernel_required" if feature.feature_type in {"fillet", "chamfer"} else "exact",
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
