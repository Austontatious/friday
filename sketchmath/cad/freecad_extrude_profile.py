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

from sketchmath.cad.solid_validation import expected_bbox_from_outer, expected_volume_mm3, validate_solid_measurements


def _bbox(shape: Any) -> dict[str, float | None]:
    bb = getattr(shape, "BoundBox", None)
    if bb is None:
        return {"xmin": None, "ymin": None, "zmin": None, "xmax": None, "ymax": None, "zmax": None}
    return {
        "xmin": float(getattr(bb, "XMin", 0.0)),
        "ymin": float(getattr(bb, "YMin", 0.0)),
        "zmin": float(getattr(bb, "ZMin", 0.0)),
        "xmax": float(getattr(bb, "XMax", 0.0)),
        "ymax": float(getattr(bb, "YMax", 0.0)),
        "zmax": float(getattr(bb, "ZMax", 0.0)),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extrude a SketchMath 2D profile to STEP")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def _vertices_to_points(vertices: list[list[float] | tuple[float, float]]) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in vertices]


def _signed_area(vertices: list[tuple[float, float]]) -> float:
    total = 0.0
    for index, point in enumerate(vertices):
        next_point = vertices[(index + 1) % len(vertices)]
        total += point[0] * next_point[1] - next_point[0] * point[1]
    return total / 2.0


def _normalize_winding(vertices: list[tuple[float, float]], *, clockwise: bool) -> tuple[list[tuple[float, float]], str]:
    closed = list(vertices)
    if closed[0] != closed[-1]:
        closed.append(closed[0])
    signed_area = _signed_area(closed[:-1])
    winding = "counterclockwise" if signed_area > 0 else "clockwise"
    target = "clockwise" if clockwise else "counterclockwise"
    if winding == target:
        return closed, winding
    reversed_vertices = list(reversed(closed))
    if reversed_vertices[0] != reversed_vertices[-1]:
        reversed_vertices.append(reversed_vertices[0])
    return reversed_vertices, winding


def _point_on_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float], *, tol: float = 1e-9) -> bool:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > tol:
        return False
    dot = (px - x1) * (px - x2) + (py - y1) * (py - y2)
    return dot <= tol


def _segments_intersect(
    a_start: tuple[float, float],
    a_end: tuple[float, float],
    b_start: tuple[float, float],
    b_end: tuple[float, float],
    *,
    strict: bool = True,
) -> bool:
    def orientation(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1 = orientation(a_start, a_end, b_start)
    o2 = orientation(a_start, a_end, b_end)
    o3 = orientation(b_start, b_end, a_start)
    o4 = orientation(b_start, b_end, a_end)

    if strict:
        return (o1 * o2 < 0.0) and (o3 * o4 < 0.0)

    if o1 == 0 and _point_on_segment(b_start, a_start, a_end):
        return True
    if o2 == 0 and _point_on_segment(b_end, a_start, a_end):
        return True
    if o3 == 0 and _point_on_segment(a_start, b_start, b_end):
        return True
    if o4 == 0 and _point_on_segment(a_end, b_start, b_end):
        return True
    return (o1 * o2 <= 0.0) and (o3 * o4 <= 0.0)


def _polygon_edges(vertices: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(vertices, vertices[1:]))


def _is_simple_polygon(vertices: list[tuple[float, float]]) -> bool:
    edges = _polygon_edges(vertices)
    for index, (a_start, a_end) in enumerate(edges):
        for other_index, (b_start, b_end) in enumerate(edges):
            if other_index <= index + 1:
                continue
            if index == 0 and other_index == len(edges) - 1:
                continue
            if _segments_intersect(a_start, a_end, b_start, b_end, strict=False):
                return False
    return True


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    for start, end in _polygon_edges(polygon):
        if _point_on_segment(point, start, end):
            return False
        x1, y1 = start
        x2, y2 = end
        intersects = ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / ((y2 - y1) or math.copysign(1e-12, y2 - y1)) + x1
        )
        if intersects:
            inside = not inside
    return inside


def _validate_hole_geometry(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> tuple[bool, str | None]:
    if not _is_simple_polygon(outer):
        return False, "outer polygon is self-intersecting"
    for hole in holes:
        if not _is_simple_polygon(hole):
            return False, "hole polygon is self-intersecting"
    for hole in holes:
        if not _point_in_polygon(hole[0], outer):
            if any(_point_on_segment(hole[0], start, end) for start, end in _polygon_edges(outer)):
                return False, "hole touches the outer boundary"
            return False, "hole is outside the outer boundary"
        for vertex in hole[:-1]:
            if any(_point_on_segment(vertex, start, end) for start, end in _polygon_edges(outer)):
                return False, "hole touches the outer boundary"
            if not _point_in_polygon(vertex, outer):
                return False, "hole is outside the outer boundary"
    for index, hole in enumerate(holes):
        for other in holes[index + 1 :]:
            for a_start, a_end in _polygon_edges(hole):
                for b_start, b_end in _polygon_edges(other):
                    if _segments_intersect(a_start, a_end, b_start, b_end, strict=False):
                        return False, "holes intersect or touch"
            if _point_in_polygon(hole[0], other) or _point_in_polygon(other[0], hole):
                return False, "holes overlap"
    return True, None


def _make_wire(vertices: list[tuple[float, float]]):
    points = [FreeCAD.Vector(float(x), float(y), 0.0) for x, y in vertices]
    return Part.makePolygon(points)


def _face_with_holes(outer_vertices: list[tuple[float, float]], hole_vertices: list[list[tuple[float, float]]]):
    outer_wire = _make_wire(outer_vertices)
    hole_wires = [_make_wire(vertices) for vertices in hole_vertices]
    last_exc: Exception | None = None
    for builder in (
        lambda: Part.Face([outer_wire] + hole_wires),
        lambda: Part.Face([outer_wire, *hole_wires]),
        lambda: Part.Face(outer_wire, hole_wires),  # type: ignore[misc]
    ):
        try:
            return builder()
        except Exception as exc:  # pragma: no cover - FreeCAD-specific fallback path
            last_exc = exc
    if last_exc is None:
        raise RuntimeError("Unable to build face with holes")
    raise last_exc


def _extrude_shape(face: Any, depth_mm: float, direction: str):
    sign = 1.0 if direction == "positive_normal" else -1.0
    return face.extrude(FreeCAD.Vector(0.0, 0.0, sign * depth_mm))


def _solid_measurements(solid: Any) -> dict[str, Any]:
    return {
        "bbox": _bbox(solid),
        "volume_mm3": float(getattr(solid, "Volume", 0.0)),
        "area_mm2": float(getattr(solid, "Area", 0.0)),
        "is_valid_solid": bool(solid.isValid()) if hasattr(solid, "isValid") else None,
    }


def _write_validation(
    *,
    out_dir: Path,
    payload: dict[str, Any],
    solid: Any,
    strategy: str,
    fallback_reason: str | None,
    outer_vertices: list[tuple[float, float]],
    hole_vertices: list[list[tuple[float, float]]],
    outer_winding: str,
    hole_windings: list[str],
):
    depth_mm = float(payload["depth_mm"])
    direction = str(payload.get("direction") or "positive_normal")
    outer_area = abs(_signed_area(outer_vertices[:-1]))
    hole_areas = [abs(_signed_area(hole[:-1])) for hole in hole_vertices]
    expected_bbox = expected_bbox_from_outer(outer_vertices, depth_mm, direction)
    expected_volume = expected_volume_mm3(outer_area, hole_areas, depth_mm)
    measurements = _solid_measurements(solid)
    validation = validate_solid_measurements(
        actual_bbox=measurements["bbox"],
        actual_volume_mm3=measurements["volume_mm3"],
        actual_is_valid_solid=measurements["is_valid_solid"],
        expected_bbox=expected_bbox,
        expected_volume_mm3=expected_volume,
    )
    if not validation.ok:
        raise ValueError(validation.message or "Solid validation failed")
    step_path = out_dir / "export.step"
    validation_path = out_dir / "validation.json"
    solid.exportStep(str(step_path))
    validation_payload = {
        "status": "export_ready",
        "profile_id": payload["profile"]["id"],
        "command_id": payload["command_id"],
        "command_type": "extrude_profile",
        "artifacts": {
            "step_path": str(step_path),
            "validation_json": str(validation_path),
            "preview_path": None,
        },
        "measurements": measurements,
        "warnings": [],
        "metadata": {
            "freecad_version": getattr(FreeCAD, "__version__", None),
            "direction": direction,
            "depth_mm": depth_mm,
            "adapter_strategy": strategy,
            "fallback_reason": fallback_reason,
            "outer_winding": outer_winding,
            "normalized_outer_winding": "counterclockwise",
            "hole_windings": hole_windings,
            "normalized_hole_windings": ["clockwise" for _ in hole_windings],
            "expected_bbox": expected_bbox,
            "expected_volume_mm3": expected_volume,
            "hole_count": len(hole_vertices),
        },
    }
    validation_path.write_text(json.dumps(validation_payload, indent=2, sort_keys=True), encoding="utf-8")


def _attempt_strategy(
    *,
    payload: dict[str, Any],
    out_dir: Path,
    strategy: str,
    outer_vertices: list[tuple[float, float]],
    hole_vertices: list[list[tuple[float, float]]],
    outer_winding: str,
    hole_windings: list[str],
) -> None:
    depth_mm = float(payload["depth_mm"])
    direction = str(payload.get("direction") or "positive_normal")
    if strategy == "face_with_holes":
        face = _face_with_holes(outer_vertices, hole_vertices)
        solid = _extrude_shape(face, depth_mm, direction)
    elif strategy == "boolean_subtraction":
        outer_face = _face_with_holes(outer_vertices, [])
        solid = _extrude_shape(outer_face, depth_mm, direction)
        for hole_vertices_one in hole_vertices:
            hole_face = _face_with_holes(hole_vertices_one, [])
            hole_solid = _extrude_shape(hole_face, depth_mm, direction)
            solid = solid.cut(hole_solid)
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unsupported strategy: {strategy}")
    _write_validation(
        out_dir=out_dir,
        payload=payload,
        solid=solid,
        strategy=strategy,
        fallback_reason=None,
        outer_vertices=outer_vertices,
        hole_vertices=hole_vertices,
        outer_winding=outer_winding,
        hole_windings=hole_windings,
    )


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    profile = payload["profile"]
    holes = payload.get("holes") or []
    outer_vertices = _vertices_to_points(profile["vertices"])
    hole_vertices = [_vertices_to_points(hole["vertices"]) for hole in holes]

    if len(outer_vertices) < 4:
        raise ValueError("Profile requires at least three edges and a closing vertex")
    if outer_vertices[0] != outer_vertices[-1]:
        raise ValueError("Profile must be closed")
    for hole_vertices_one in hole_vertices:
        if len(hole_vertices_one) < 4:
            raise ValueError("Hole profile requires at least three edges and a closing vertex")
        if hole_vertices_one[0] != hole_vertices_one[-1]:
            raise ValueError("Hole profile must be closed")

    ok, reason = _validate_hole_geometry(outer_vertices, hole_vertices)
    if not ok:
        raise ValueError(reason or "Invalid hole geometry")

    depth_mm = float(payload["depth_mm"])
    direction = str(payload.get("direction") or "positive_normal")
    if direction not in {"positive_normal", "negative_normal"}:
        raise ValueError(f"Unsupported direction: {direction}")

    normalized_outer, outer_original_winding = _normalize_winding(outer_vertices, clockwise=False)
    normalized_holes: list[list[tuple[float, float]]] = []
    hole_windings: list[str] = []
    for vertices in hole_vertices:
        normalized, original_winding = _normalize_winding(vertices, clockwise=True)
        normalized_holes.append(normalized)
        hole_windings.append(original_winding)

    face_failure: Exception | None = None
    try:
        _attempt_strategy(
            payload=payload,
            out_dir=out_dir,
            strategy="face_with_holes",
            outer_vertices=normalized_outer,
            hole_vertices=normalized_holes,
            outer_winding=outer_original_winding,
            hole_windings=hole_windings,
        )
        return 0
    except Exception as exc:  # pragma: no cover - FreeCAD-specific fallback
        face_failure = exc

    try:
        _attempt_strategy(
            payload=payload,
            out_dir=out_dir,
            strategy="boolean_subtraction",
            outer_vertices=normalized_outer,
            hole_vertices=normalized_holes,
            outer_winding=outer_original_winding,
            hole_windings=hole_windings,
        )
        # rewrite validation metadata with the fallback reason after success
        validation_path = out_dir / "validation.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        validation["metadata"]["fallback_reason"] = str(face_failure) if face_failure is not None else None
        validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
        return 0
    except Exception as fallback_exc:
        raise ValueError(f"Face-with-holes failed: {face_failure}; boolean fallback failed: {fallback_exc}") from fallback_exc


if __name__ == "__main__":
    raise SystemExit(main())
