from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any


def _vector(start: list[float], end: list[float]) -> tuple[float, float, float]:
    return (end[0] - start[0], end[1] - start[1], end[2] - start[2])


def _cross(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normal(a: list[float], b: list[float], c: list[float]) -> tuple[float, float, float]:
    value = _cross(_vector(a, b), _vector(a, c))
    magnitude = math.sqrt(sum(component * component for component in value))
    if magnitude == 0:
        return (0.0, 0.0, 0.0)
    return tuple(component / magnitude for component in value)  # type: ignore[return-value]


def _format(value: float) -> str:
    rounded = 0.0 if abs(value) < 5e-10 else value
    return f"{rounded:.9f}"


def render_ascii_stl(mesh: dict[str, Any], *, solid_name: str) -> str:
    vertices = mesh.get("vertices") or []
    triangles = mesh.get("triangles") or []
    lines = [f"solid {solid_name}"]
    for triangle in triangles:
        indices = triangle["indices"]
        a, b, c = (vertices[int(index)] for index in indices)
        normal = _normal(a, b, c)
        lines.append(f"  facet normal {_format(normal[0])} {_format(normal[1])} {_format(normal[2])}")
        lines.append("    outer loop")
        for vertex in (a, b, c):
            lines.append(f"      vertex {_format(vertex[0])} {_format(vertex[1])} {_format(vertex[2])}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {solid_name}")
    return "\n".join(lines) + "\n"


def mesh_measurements(mesh: dict[str, Any]) -> dict[str, Any]:
    vertices = mesh.get("vertices") or []
    triangles = mesh.get("triangles") or []
    if not vertices or not triangles:
        raise ValueError("STL mesh requires vertices and triangles")
    xs = [float(vertex[0]) for vertex in vertices]
    ys = [float(vertex[1]) for vertex in vertices]
    zs = [float(vertex[2]) for vertex in vertices]
    signed_volume = 0.0
    edge_counts: dict[tuple[int, int], int] = {}
    for triangle in triangles:
        indices = tuple(int(index) for index in triangle["indices"])
        a, b, c = (vertices[index] for index in indices)
        for start, end in ((indices[0], indices[1]), (indices[1], indices[2]), (indices[2], indices[0])):
            edge = (min(start, end), max(start, end))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
        signed_volume += (
            float(a[0]) * (float(b[1]) * float(c[2]) - float(b[2]) * float(c[1]))
            - float(a[1]) * (float(b[0]) * float(c[2]) - float(b[2]) * float(c[0]))
            + float(a[2]) * (float(b[0]) * float(c[1]) - float(b[1]) * float(c[0]))
        ) / 6.0
    return {
        "bbox": {
            "xmin": min(xs),
            "xmax": max(xs),
            "ymin": min(ys),
            "ymax": max(ys),
            "zmin": min(zs),
            "zmax": max(zs),
        },
        "volume_mm3": round(abs(signed_volume), 9),
        "triangle_count": len(triangles),
        "vertex_count": len(vertices),
        "is_closed_mesh": bool(edge_counts) and all(count == 2 for count in edge_counts.values()),
        "nonmanifold_edge_count": sum(1 for count in edge_counts.values() if count != 2),
    }


def write_ascii_stl(mesh: dict[str, Any], path: Path, *, solid_name: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = render_ascii_stl(mesh, solid_name=solid_name)
    path.write_text(payload, encoding="ascii")
    measurements = mesh_measurements(mesh)
    measurements.update(
        {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "content_hash": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        }
    )
    return measurements
