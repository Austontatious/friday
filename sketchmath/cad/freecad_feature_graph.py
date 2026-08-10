from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import FreeCAD  # type: ignore
import Part  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sketchmath.cad.freecad_extrude_profile import (
    _extrude_shape,
    _face_with_holes,
    _normalize_winding,
    _solid_measurements,
    _validate_hole_geometry,
    _vertices_to_points,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a guarded canonical SketchMath edge-finish graph")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def _profile_face(profile: dict[str, Any], holes: list[dict[str, Any]]) -> tuple[Any, str]:
    analytic_circle = profile.get("analytic_circle")
    if analytic_circle:
        if holes:
            raise ValueError("Analytic circular extrusion with profile holes is not supported")
        center = analytic_circle["center_mm"]
        radius_mm = float(analytic_circle["radius_mm"])
        if not math.isfinite(radius_mm) or radius_mm <= 0:
            raise ValueError("Analytic circle radius must be positive and finite")
        edge = Part.makeCircle(radius_mm, FreeCAD.Vector(float(center[0]), float(center[1]), 0.0))
        return Part.Face(Part.Wire([edge])), "analytic_circle"
    outer_vertices = _vertices_to_points(profile["vertices"])
    hole_vertices = [_vertices_to_points(hole["vertices"]) for hole in holes]
    if len(outer_vertices) < 4 or outer_vertices[0] != outer_vertices[-1]:
        raise ValueError("Extrusion profile must be a closed polygon")
    ok, reason = _validate_hole_geometry(outer_vertices, hole_vertices)
    if not ok:
        raise ValueError(reason or "Invalid base extrusion profile")
    normalized_outer, _ = _normalize_winding(outer_vertices, clockwise=False)
    normalized_holes = [_normalize_winding(vertices, clockwise=True)[0] for vertices in hole_vertices]
    try:
        return _face_with_holes(normalized_outer, normalized_holes), "face_with_holes"
    except Exception:
        face = _face_with_holes(normalized_outer, [])
        for vertices in normalized_holes:
            cutter = _face_with_holes(vertices, [])
            face = face.cut(cutter)
        return face, "boolean_subtraction"


def _build_extrusion(operation: dict[str, Any]) -> tuple[Any, str]:
    z_min = float(operation["z_min_mm"])
    z_max = float(operation["z_max_mm"])
    depth_mm = z_max - z_min
    if not math.isfinite(depth_mm) or depth_mm <= 0:
        raise ValueError("Extrusion bounds must define a positive finite depth")
    face, strategy = _profile_face(operation["profile"], operation.get("holes") or [])
    solid = _extrude_shape(face, depth_mm, "positive_normal")
    if abs(z_min) > 1e-12:
        solid.translate(FreeCAD.Vector(0.0, 0.0, z_min))
    return solid, strategy


def _build_revolve(operation: dict[str, Any]) -> tuple[Any, str]:
    angle_deg = float(operation["angle_deg"])
    if not math.isfinite(angle_deg) or abs(angle_deg - 360.0) > 1e-9:
        raise ValueError("Feature-graph revolve currently requires exactly 360 degrees")
    origin = operation["axis_origin_mm"]
    direction = operation["axis_direction"]
    direction_x = float(direction[0])
    direction_y = float(direction[1])
    magnitude = math.hypot(direction_x, direction_y)
    if not all(math.isfinite(value) for value in (float(origin[0]), float(origin[1]), magnitude)) or magnitude <= 1e-9:
        raise ValueError("Revolve axis must be finite and non-zero")
    face, strategy = _profile_face(operation["profile"], operation.get("holes") or [])
    solid = face.revolve(
        FreeCAD.Vector(float(origin[0]), float(origin[1]), 0.0),
        FreeCAD.Vector(direction_x / magnitude, direction_y / magnitude, 0.0),
        angle_deg,
    )
    return solid, strategy


def _build_body(operations: list[dict[str, Any]]) -> tuple[Any, list[dict[str, Any]]]:
    if not operations:
        raise ValueError("Feature graph requires at least one pre-finish operation")
    solid = None
    execution: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        feature_type = operation.get("feature_type")
        if feature_type == "extrude":
            candidate, strategy = _build_extrusion(operation)
            mode = operation.get("operation")
            if index == 0:
                if mode != "new_body":
                    raise ValueError("First feature-graph operation must be a new-body extrusion")
                solid = candidate
            elif mode == "add":
                solid = solid.fuse(candidate)
            elif mode == "cut":
                solid = solid.cut(candidate)
            else:
                raise ValueError("Feature-graph extrusions after the base must be additive or subtractive")
            execution.append(
                {
                    "feature_id": operation.get("feature_id"),
                    "feature_type": feature_type,
                    "operation": mode,
                    "strategy": strategy,
                }
            )
        elif feature_type == "revolve":
            candidate, strategy = _build_revolve(operation)
            mode = operation.get("operation")
            if index != 0 or mode != "new_body":
                raise ValueError("Feature-graph revolve currently supports one new-body operation")
            solid = candidate
            execution.append(
                {
                    "feature_id": operation.get("feature_id"),
                    "feature_type": feature_type,
                    "operation": mode,
                    "angle_deg": float(operation["angle_deg"]),
                    "strategy": strategy,
                }
            )
        elif feature_type == "hole":
            if solid is None:
                raise ValueError("Hole operation requires an existing solid")
            center = operation["center_mm"]
            radius_mm = float(operation["diameter_mm"]) / 2.0
            z_min = float(operation["z_min_mm"])
            z_max = float(operation["z_max_mm"])
            depth_mm = z_max - z_min
            if not all(math.isfinite(value) for value in (float(center[0]), float(center[1]), radius_mm, depth_mm)):
                raise ValueError("Hole geometry must be finite")
            if radius_mm <= 0 or depth_mm <= 0:
                raise ValueError("Hole diameter and depth must be positive")
            shaft = Part.makeCylinder(
                radius_mm,
                depth_mm,
                FreeCAD.Vector(float(center[0]), float(center[1]), z_min),
            )
            style = str(operation.get("style") or "simple")
            cutter = shaft
            style_metadata: dict[str, Any] = {"style": style}
            if style == "counterbore":
                outer_radius = float(operation["counterbore_diameter_mm"]) / 2.0
                style_depth = float(operation["counterbore_depth_mm"])
                if outer_radius <= radius_mm or style_depth <= 0 or style_depth > depth_mm:
                    raise ValueError("Counterbore geometry is outside the supported hole bounds")
                counterbore = Part.makeCylinder(
                    outer_radius,
                    style_depth,
                    FreeCAD.Vector(float(center[0]), float(center[1]), z_max - style_depth),
                )
                cutter = cutter.fuse(counterbore)
                style_metadata.update({"outer_diameter_mm": outer_radius * 2.0, "style_depth_mm": style_depth})
            elif style == "countersink":
                outer_radius = float(operation["countersink_diameter_mm"]) / 2.0
                half_angle = math.radians(float(operation["countersink_angle_deg"]) / 2.0)
                style_depth = (outer_radius - radius_mm) / math.tan(half_angle)
                if outer_radius <= radius_mm or not math.isfinite(style_depth) or style_depth <= 0 or style_depth > depth_mm:
                    raise ValueError("Countersink geometry is outside the supported hole bounds")
                countersink = Part.makeCone(
                    radius_mm,
                    outer_radius,
                    style_depth,
                    FreeCAD.Vector(float(center[0]), float(center[1]), z_max - style_depth),
                )
                cutter = cutter.fuse(countersink)
                style_metadata.update({
                    "outer_diameter_mm": outer_radius * 2.0,
                    "style_depth_mm": style_depth,
                    "angle_deg": float(operation["countersink_angle_deg"]),
                })
            elif style != "simple":
                raise ValueError(f"Unsupported hole style: {style}")
            solid = solid.cut(cutter)
            execution.append(
                {
                    "feature_id": operation.get("feature_id"),
                    "feature_type": feature_type,
                    "operation": "cut",
                    "diameter_mm": radius_mm * 2.0,
                    "depth_mm": depth_mm,
                    **style_metadata,
                }
            )
        elif feature_type == "shell":
            if solid is None:
                raise ValueError("Shell operation requires an existing solid")
            bounds = [float(value) for value in operation["cavity_bounds_mm"]]
            if len(bounds) != 6 or not all(math.isfinite(value) for value in bounds):
                raise ValueError("Shell cavity bounds must contain six finite values")
            x_min, x_max, y_min, y_max, z_min, z_max = bounds
            width, height, depth = x_max - x_min, y_max - y_min, z_max - z_min
            thickness_mm = float(operation["thickness_mm"])
            if min(width, height, depth, thickness_mm) <= 0:
                raise ValueError("Shell cavity dimensions and thickness must be positive")
            cutter = Part.makeBox(width, height, depth, FreeCAD.Vector(x_min, y_min, z_min))
            solid = solid.cut(cutter)
            execution.append(
                {
                    "feature_id": operation.get("feature_id"),
                    "feature_type": feature_type,
                    "operation": "cut",
                    "opening": operation.get("opening"),
                    "thickness_mm": thickness_mm,
                    "cavity_bounds_mm": bounds,
                }
            )
        else:
            raise ValueError(f"Unsupported feature-graph operation: {feature_type}")
        if hasattr(solid, "removeSplitter"):
            solid = solid.removeSplitter()
        intermediate = _solid_measurements(solid)
        if intermediate["is_valid_solid"] is not True or intermediate["volume_mm3"] <= 0:
            raise ValueError(f"Feature-graph operation {operation.get('feature_id')} produced an invalid solid")
    return solid, execution


def _point(edge_vertex: Any) -> tuple[float, float, float]:
    point = edge_vertex.Point
    return float(point.x), float(point.y), float(point.z)


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _edge_matches(edge: Any, endpoints: list[list[float]], *, tolerance: float = 1e-6) -> bool:
    vertices = list(getattr(edge, "Vertexes", []))
    if len(vertices) != 2 or len(endpoints) != 2:
        return False
    actual = [_point(vertex) for vertex in vertices]
    expected = [tuple(float(value) for value in endpoint) for endpoint in endpoints]
    direct = _distance(actual[0], expected[0]) <= tolerance and _distance(actual[1], expected[1]) <= tolerance
    reverse = _distance(actual[0], expected[1]) <= tolerance and _distance(actual[1], expected[0]) <= tolerance
    return direct or reverse


def _resolve_edges(solid: Any, selectors: list[dict[str, Any]]) -> tuple[list[Any], list[dict[str, Any]]]:
    edges = list(getattr(solid, "Edges", []))
    selected: list[Any] = []
    resolution: list[dict[str, Any]] = []
    used_ordinals: set[int] = set()
    for selector in selectors:
        endpoints = selector.get("endpoints") or []
        candidates = [index for index, edge in enumerate(edges) if _edge_matches(edge, endpoints)]
        if len(candidates) != 1:
            raise ValueError(
                f"Semantic edge {selector.get('reference_id')} resolved to {len(candidates)} kernel edges"
            )
        kernel_ordinal = candidates[0]
        if kernel_ordinal in used_ordinals:
            raise ValueError("Two semantic selectors resolved to the same kernel edge")
        used_ordinals.add(kernel_ordinal)
        selected.append(edges[kernel_ordinal])
        resolution.append(
            {
                "reference_id": selector.get("reference_id"),
                "source_entity_id": selector.get("source_entity_id"),
                "expected_signature": selector.get("geometric_signature"),
                "kernel_edge_ordinal": kernel_ordinal,
                "match_basis": "unordered_endpoints_mm",
                "endpoints": endpoints,
            }
        )
    return selected, resolution


def _bounds_equal(left: dict[str, float | None], right: dict[str, float | None], *, tolerance: float = 1e-6) -> bool:
    return all(
        left.get(name) is not None
        and right.get(name) is not None
        and abs(float(left[name]) - float(right[name])) <= tolerance
        for name in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    )


def _cylindrical_face_radii(solid: Any) -> list[float]:
    radii: list[float] = []
    for face in getattr(solid, "Faces", []):
        surface = getattr(face, "Surface", None)
        radius = getattr(surface, "Radius", None)
        if radius is None:
            continue
        value = float(radius)
        if math.isfinite(value) and value > 0:
            radii.append(value)
    return sorted(radii)


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    feature_type = payload.get("feature_type")
    if feature_type not in {"solid", "fillet", "chamfer"}:
        raise ValueError("Feature-graph worker currently supports solid, fillet, and chamfer graphs")
    if str(payload.get("output_format") or "step").lower() != "step":
        raise ValueError("Feature-graph worker currently exports STEP only")

    operations = payload.get("operations") or []
    base_solid, operation_execution = _build_body(operations)
    base_measurements = _solid_measurements(base_solid)
    expected = payload.get("expected_pre_finish") or {}
    expected_bbox = expected.get("bbox")
    expected_volume = expected.get("volume_mm3")
    if expected_bbox and not _bounds_equal(base_measurements["bbox"], expected_bbox):
        raise ValueError("Feature graph did not preserve canonical pre-finish bounds")
    if expected_volume is not None:
        volume_tolerance = max(1e-5, abs(float(expected_volume)) * 1e-8)
        if abs(base_measurements["volume_mm3"] - float(expected_volume)) > volume_tolerance:
            raise ValueError("Feature graph did not preserve canonical pre-finish volume")

    if feature_type == "solid":
        finished = base_solid
        measurements = base_measurements
        metadata = {
            "freecad_version": getattr(FreeCAD, "__version__", None),
            "operation_execution": operation_execution,
            "canonical_volume_mm3": measurements["volume_mm3"],
            "canonical_bbox": measurements["bbox"],
            "canonical_hole_count": int(expected.get("hole_count") or 0),
        }
    else:
        edge_finish = payload[feature_type]
        size_name = "radius" if feature_type == "fillet" else "distance"
        size_mm = float(edge_finish[f"{size_name}_mm"])
        if not math.isfinite(size_mm) or size_mm <= 0:
            raise ValueError(f"{feature_type.title()} {size_name} must be positive and finite")
        selectors = edge_finish.get("edges") or []
        if not selectors:
            raise ValueError(f"{feature_type.title()} requires at least one semantic edge selector")
        selected_edges, edge_resolution = _resolve_edges(base_solid, selectors)
        finished = (
            base_solid.makeFillet(size_mm, selected_edges)
            if feature_type == "fillet"
            else base_solid.makeChamfer(size_mm, selected_edges)
        )
        if hasattr(finished, "removeSplitter"):
            finished = finished.removeSplitter()
        measurements = _solid_measurements(finished)
        if measurements["is_valid_solid"] is not True or measurements["volume_mm3"] <= 0:
            raise ValueError(f"FreeCAD {feature_type} did not produce a valid positive solid")
        if measurements["volume_mm3"] >= base_measurements["volume_mm3"] - 1e-7:
            raise ValueError(f"Convex outer-edge {feature_type} did not remove measurable material")
        if not _bounds_equal(measurements["bbox"], base_measurements["bbox"]):
            raise ValueError(f"{feature_type.title()} changed the supported base extrusion bounds")
        metadata = {
            "freecad_version": getattr(FreeCAD, "__version__", None),
            "operation_execution": operation_execution,
            "pre_finish_volume_mm3": base_measurements["volume_mm3"],
            "pre_finish_bbox": base_measurements["bbox"],
            "volume_delta_mm3": measurements["volume_mm3"] - base_measurements["volume_mm3"],
            f"{size_name}_mm": size_mm,
            "selected_edge_count": len(selected_edges),
            "semantic_edge_resolution": edge_resolution,
            "reference_policy": "semantic_endpoints_unique_match",
            "canonical_hole_count": int(expected.get("hole_count") or 0),
            "cylindrical_face_radii_mm": _cylindrical_face_radii(finished),
        }

    step_path = out_dir / "export.step"
    validation_path = out_dir / "validation.json"
    finished.exportStep(str(step_path))
    validation = {
        "status": "export_ready",
        "profile_id": operations[0]["profile"]["id"],
        "command_id": payload["command_id"],
        "command_type": f"{feature_type}_feature_graph",
        "artifacts": {
            "step_path": str(step_path),
            "validation_json": str(validation_path),
            "preview_path": None,
        },
        "measurements": measurements,
        "warnings": [],
        "metadata": metadata,
    }
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
