from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import FreeCAD  # type: ignore

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


def _build_base(payload: dict[str, Any]) -> tuple[Any, str]:
    base = payload["base_extrusion"]
    profile = base["profile"]
    holes = base.get("holes") or []
    outer_vertices = _vertices_to_points(profile["vertices"])
    hole_vertices = [_vertices_to_points(hole["vertices"]) for hole in holes]
    if len(outer_vertices) < 4 or outer_vertices[0] != outer_vertices[-1]:
        raise ValueError("Base extrusion profile must be a closed polygon")
    ok, reason = _validate_hole_geometry(outer_vertices, hole_vertices)
    if not ok:
        raise ValueError(reason or "Invalid base extrusion profile")
    normalized_outer, _ = _normalize_winding(outer_vertices, clockwise=False)
    normalized_holes = [_normalize_winding(vertices, clockwise=True)[0] for vertices in hole_vertices]
    depth_mm = float(base["depth_mm"])
    if not math.isfinite(depth_mm) or depth_mm <= 0:
        raise ValueError("Base extrusion depth must be positive and finite")
    try:
        face = _face_with_holes(normalized_outer, normalized_holes)
        return _extrude_shape(face, depth_mm, "positive_normal"), "face_with_holes"
    except Exception:
        face = _face_with_holes(normalized_outer, [])
        solid = _extrude_shape(face, depth_mm, "positive_normal")
        for vertices in normalized_holes:
            cutter = _extrude_shape(_face_with_holes(vertices, []), depth_mm, "positive_normal")
            solid = solid.cut(cutter)
        return solid, "boolean_subtraction"


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


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    feature_type = payload.get("feature_type")
    if feature_type not in {"fillet", "chamfer"}:
        raise ValueError("Feature-graph worker currently supports fillet and chamfer only")
    if str(payload.get("output_format") or "step").lower() != "step":
        raise ValueError("Feature-graph worker currently exports STEP only")

    edge_finish = payload[feature_type]
    size_name = "radius" if feature_type == "fillet" else "distance"
    size_mm = float(edge_finish[f"{size_name}_mm"])
    if not math.isfinite(size_mm) or size_mm <= 0:
        raise ValueError(f"{feature_type.title()} {size_name} must be positive and finite")
    selectors = edge_finish.get("edges") or []
    if not selectors:
        raise ValueError(f"{feature_type.title()} requires at least one semantic edge selector")

    base_solid, base_strategy = _build_base(payload)
    base_measurements = _solid_measurements(base_solid)
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

    step_path = out_dir / "export.step"
    validation_path = out_dir / "validation.json"
    finished.exportStep(str(step_path))
    validation = {
        "status": "export_ready",
        "profile_id": payload["base_extrusion"]["profile"]["id"],
        "command_id": payload["command_id"],
        "command_type": f"{feature_type}_feature_graph",
        "artifacts": {
            "step_path": str(step_path),
            "validation_json": str(validation_path),
            "preview_path": None,
        },
        "measurements": measurements,
        "warnings": [],
        "metadata": {
            "freecad_version": getattr(FreeCAD, "__version__", None),
            "base_strategy": base_strategy,
            "base_volume_mm3": base_measurements["volume_mm3"],
            "volume_delta_mm3": measurements["volume_mm3"] - base_measurements["volume_mm3"],
            f"{size_name}_mm": size_mm,
            "selected_edge_count": len(selected_edges),
            "semantic_edge_resolution": edge_resolution,
            "reference_policy": "semantic_endpoints_unique_match",
        },
    }
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
