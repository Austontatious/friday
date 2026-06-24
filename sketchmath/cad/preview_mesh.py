from __future__ import annotations

from typing import Any

from sketchmath.cad.profile_holes import ProfileHoleValidationResult, validate_profile_holes
from sketchmath.models.entities import Profile2DEntity


def _load_shapely() -> tuple[Any, Any, Any]:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate
        from shapely.prepared import prep
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError("shapely is required for SketchMath preview mesh generation") from exc
    return Polygon, triangulate, prep


def _rounded_point(point: tuple[float, float], z: float) -> list[float]:
    return [round(float(point[0]), 6), round(float(point[1]), 6), round(float(z), 6)]


def _ring_without_duplicate(vertices: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(vertices) > 1 and vertices[0] == vertices[-1]:
        return vertices[:-1]
    return vertices


def _append_vertex(vertices: list[list[float]], index_by_key: dict[tuple[float, float, float], int], point: tuple[float, float], z: float) -> int:
    rounded = _rounded_point(point, z)
    key = (rounded[0], rounded[1], rounded[2])
    existing = index_by_key.get(key)
    if existing is not None:
        return existing
    index = len(vertices)
    vertices.append(rounded)
    index_by_key[key] = index
    return index


def _append_triangle(
    triangles: list[dict[str, Any]],
    indices: tuple[int, int, int],
    *,
    surface: str,
    ring_id: str | None = None,
) -> None:
    if len({indices[0], indices[1], indices[2]}) < 3:
        return
    triangle: dict[str, Any] = {"indices": [indices[0], indices[1], indices[2]], "surface": surface}
    if ring_id:
        triangle["ring_id"] = ring_id
    triangles.append(triangle)


def _append_wall(
    vertices: list[list[float]],
    index_by_key: dict[tuple[float, float, float], int],
    triangles: list[dict[str, Any]],
    ring: list[tuple[float, float]],
    *,
    depth: float,
    surface: str,
    ring_id: str,
) -> list[int]:
    bottom_loop: list[int] = []
    top_loop: list[int] = []
    loop = _ring_without_duplicate(ring)
    for point in loop:
        bottom_loop.append(_append_vertex(vertices, index_by_key, point, 0.0))
        top_loop.append(_append_vertex(vertices, index_by_key, point, depth))
    for index, current in enumerate(loop):
        next_index = (index + 1) % len(loop)
        bottom_a = bottom_loop[index]
        bottom_b = bottom_loop[next_index]
        top_a = top_loop[index]
        top_b = top_loop[next_index]
        if surface == "hole_wall":
            _append_triangle(triangles, (bottom_a, top_b, bottom_b), surface=surface, ring_id=ring_id)
            _append_triangle(triangles, (bottom_a, top_a, top_b), surface=surface, ring_id=ring_id)
        else:
            _append_triangle(triangles, (bottom_a, bottom_b, top_b), surface=surface, ring_id=ring_id)
            _append_triangle(triangles, (bottom_a, top_b, top_a), surface=surface, ring_id=ring_id)
    return top_loop


def build_preview_mesh(
    profile: Profile2DEntity,
    *,
    holes: list[Profile2DEntity] | None = None,
    depth: float,
    depth_unit: str = "mm",
    validation: ProfileHoleValidationResult | None = None,
) -> dict[str, Any]:
    """Build a deterministic browser mesh for the current MVP extrusion path."""

    if depth <= 0:
        raise ValueError("Preview extrusion depth must be positive")
    validation = validation or validate_profile_holes(profile, holes or [])
    if not validation.ok or validation.outer is None:
        raise ValueError(validation.message or "Invalid profile hole configuration")

    Polygon, triangulate, prep = _load_shapely()
    outer_ring = _ring_without_duplicate(validation.outer.vertices)
    hole_rings = [_ring_without_duplicate(hole.vertices) for hole in validation.holes]
    polygon = Polygon(outer_ring, hole_rings)
    prepared_polygon = prep(polygon)

    vertices: list[list[float]] = []
    index_by_key: dict[tuple[float, float, float], int] = {}
    triangles: list[dict[str, Any]] = []

    for triangle in triangulate(polygon):
        if not prepared_polygon.contains(triangle.representative_point()):
            continue
        coords = [(float(x), float(y)) for x, y in triangle.exterior.coords[:-1]]
        if len(coords) != 3:
            continue
        bottom = tuple(_append_vertex(vertices, index_by_key, point, 0.0) for point in coords)
        top = tuple(_append_vertex(vertices, index_by_key, point, depth) for point in coords)
        _append_triangle(triangles, (top[0], top[1], top[2]), surface="top")
        _append_triangle(triangles, (bottom[2], bottom[1], bottom[0]), surface="bottom")

    outer_loop = _append_wall(
        vertices,
        index_by_key,
        triangles,
        validation.outer.vertices,
        depth=depth,
        surface="outer_wall",
        ring_id=validation.outer.id,
    )
    hole_loops = [
        {
            "id": hole.id,
            "top": _append_wall(vertices, index_by_key, triangles, hole.vertices, depth=depth, surface="hole_wall", ring_id=hole.id),
        }
        for hole in validation.holes
    ]

    xs = [vertex[0] for vertex in vertices] or [0.0]
    ys = [vertex[1] for vertex in vertices] or [0.0]
    zs = [vertex[2] for vertex in vertices] or [0.0]
    return {
        "version": "0.1",
        "units": depth_unit,
        "profile_id": profile.id,
        "depth": round(float(depth), 6),
        "vertices": vertices,
        "triangles": triangles,
        "loops": {
            "outer_top": outer_loop,
            "hole_tops": hole_loops,
        },
        "metadata": {
            "profile_id": profile.id,
            "extrusion_depth": round(float(depth), 6),
            "extrusion_depth_unit": depth_unit,
            "hole_count": len(validation.holes),
            "triangle_count": len(triangles),
            "vertex_count": len(vertices),
            "bbox": {
                "xmin": min(xs),
                "xmax": max(xs),
                "ymin": min(ys),
                "ymax": max(ys),
                "zmin": min(zs),
                "zmax": max(zs),
            },
        },
    }
