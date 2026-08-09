from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from shapely.geometry import GeometryCollection, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import triangulate

from sketchmath.executor.errors import CadExportError
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import ExtrudeParameters, HoleParameters, SketchMathDocument
from sketchmath.models.entities import Profile2DEntity


def _polygons(geometry: Any) -> Iterable[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    return [item for item in geometry.geoms if isinstance(item, Polygon)]


def _profile_polygon(document: SketchMathDocument, sketch_id: str, profile_id: str) -> Polygon:
    sketch = next((item for item in document.sketches if item.sketch_id == sketch_id), None)
    if sketch is None:
        raise CadExportError("Feature sketch does not exist", detail={"sketch_id": sketch_id})
    profile = sketch.state.get_entity(profile_id)
    if not isinstance(profile, Profile2DEntity):
        raise CadExportError("Feature source is not a profile", detail={"profile_id": profile_id})
    hole_vertices: list[list[tuple[float, float]]] = []
    for hole_id in profile.holes:
        hole = sketch.state.get_entity(hole_id)
        if not isinstance(hole, Profile2DEntity):
            raise CadExportError("Feature hole source is not a profile", detail={"hole_id": hole_id})
        hole_vertices.append(hole.vertices)
    polygon = Polygon(profile.vertices, holes=hole_vertices)
    if not polygon.is_valid or polygon.area <= 0:
        raise CadExportError("Feature profile is not a valid material region", detail={"profile_id": profile_id})
    return polygon


def _append_vertex(vertices: list[list[float]], index_by_key: dict[tuple[float, float, float], int], point: tuple[float, float, float]) -> int:
    key = tuple(round(float(value), 12) for value in point)
    index = index_by_key.get(key)
    if index is None:
        index = len(vertices)
        index_by_key[key] = index
        vertices.append([float(key[0]), float(key[1]), float(key[2])])
    return index


def _append_triangle(
    vertices: list[list[float]],
    index_by_key: dict[tuple[float, float, float], int],
    triangles: list[dict[str, Any]],
    points: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    *,
    surface: str,
    ring_id: str,
) -> None:
    triangles.append(
        {
            "indices": [_append_vertex(vertices, index_by_key, point) for point in points],
            "surface": surface,
            "ring_id": ring_id,
        }
    )


def _append_horizontal_face(
    geometry: Any,
    z_value: float,
    *,
    upward: bool,
    vertices: list[list[float]],
    index_by_key: dict[tuple[float, float, float], int],
    triangles: list[dict[str, Any]],
    surface: str,
) -> None:
    for polygon_index, polygon in enumerate(_polygons(geometry)):
        accepted = [triangle for triangle in triangulate(polygon) if polygon.covers(triangle)]
        if abs(sum(triangle.area for triangle in accepted) - polygon.area) > 1e-7:
            raise CadExportError(
                "Layer face triangulation did not preserve area",
                detail={"surface": surface, "expected_area": polygon.area, "triangulated_area": sum(item.area for item in accepted)},
            )
        for triangle_index, triangle in enumerate(accepted):
            coordinates = list(triangle.exterior.coords)[:3]
            signed_area = sum(
                coordinates[index][0] * coordinates[(index + 1) % 3][1]
                - coordinates[(index + 1) % 3][0] * coordinates[index][1]
                for index in range(3)
            )
            if signed_area < 0:
                coordinates[1], coordinates[2] = coordinates[2], coordinates[1]
            if not upward:
                coordinates[1], coordinates[2] = coordinates[2], coordinates[1]
            _append_triangle(
                vertices,
                index_by_key,
                triangles,
                tuple((float(x), float(y), z_value) for x, y in coordinates),  # type: ignore[arg-type]
                surface=surface,
                ring_id=f"layer_{polygon_index}_{triangle_index}",
            )


def _append_ring_walls(
    coordinates: list[tuple[float, float]],
    z_min: float,
    z_max: float,
    *,
    vertices: list[list[float]],
    index_by_key: dict[tuple[float, float, float], int],
    triangles: list[dict[str, Any]],
    surface: str,
    ring_id: str,
) -> None:
    points = coordinates[:-1] if coordinates and coordinates[0] == coordinates[-1] else coordinates
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        bottom_start = (float(start[0]), float(start[1]), z_min)
        bottom_end = (float(end[0]), float(end[1]), z_min)
        top_start = (float(start[0]), float(start[1]), z_max)
        top_end = (float(end[0]), float(end[1]), z_max)
        _append_triangle(
            vertices,
            index_by_key,
            triangles,
            (bottom_start, bottom_end, top_end),
            surface=surface,
            ring_id=ring_id,
        )
        _append_triangle(
            vertices,
            index_by_key,
            triangles,
            (bottom_start, top_end, top_start),
            surface=surface,
            ring_id=ring_id,
        )


def _layered_mesh(slabs: list[tuple[float, float, Any]], *, units: str, terminal_feature_id: str) -> dict[str, Any]:
    vertices: list[list[float]] = []
    index_by_key: dict[tuple[float, float, float], int] = {}
    triangles: list[dict[str, Any]] = []
    for slab_index, (z_min, z_max, geometry) in enumerate(slabs):
        for polygon_index, polygon in enumerate(_polygons(geometry)):
            oriented = orient(polygon, sign=1.0)
            _append_ring_walls(
                list(oriented.exterior.coords),
                z_min,
                z_max,
                vertices=vertices,
                index_by_key=index_by_key,
                triangles=triangles,
                surface="outer_wall",
                ring_id=f"slab_{slab_index}_outer_{polygon_index}",
            )
            for hole_index, ring in enumerate(oriented.interiors):
                _append_ring_walls(
                    list(ring.coords),
                    z_min,
                    z_max,
                    vertices=vertices,
                    index_by_key=index_by_key,
                    triangles=triangles,
                    surface="hole_wall",
                    ring_id=f"slab_{slab_index}_hole_{polygon_index}_{hole_index}",
                )

    levels = [slabs[0][0], *[slab[1] for slab in slabs]]
    empty = GeometryCollection()
    for level_index, z_value in enumerate(levels):
        below = slabs[level_index - 1][2] if level_index > 0 else empty
        above = slabs[level_index][2] if level_index < len(slabs) else empty
        _append_horizontal_face(
            below.difference(above),
            z_value,
            upward=True,
            vertices=vertices,
            index_by_key=index_by_key,
            triangles=triangles,
            surface="top",
        )
        _append_horizontal_face(
            above.difference(below),
            z_value,
            upward=False,
            vertices=vertices,
            index_by_key=index_by_key,
            triangles=triangles,
            surface="bottom",
        )
    return {
        "version": "1.0",
        "units": units,
        "profile_id": terminal_feature_id,
        "depth": max(levels) - min(levels),
        "vertices": vertices,
        "triangles": triangles,
        "loops": {},
        "metadata": {
            "terminal_feature_id": terminal_feature_id,
            "layer_count": len(slabs),
            "triangle_count": len(triangles),
            "vertex_count": len(vertices),
        },
    }


def build_feature_body_mesh(document: SketchMathDocument, terminal_feature_id: str) -> dict[str, Any]:
    report = rebuild_document(document)
    if not report.ok:
        raise CadExportError("Feature body must rebuild before meshing", detail={"rebuild": report.model_dump(mode="json")})
    terminal_index = next((index for index, feature in enumerate(document.features) if feature.feature_id == terminal_feature_id), None)
    if terminal_index is None:
        raise CadExportError("Terminal feature does not exist", detail={"feature_id": terminal_feature_id})
    terminal = document.features[terminal_index]
    later_body_features = [
        feature.feature_id
        for feature in document.features[terminal_index + 1 :]
        if feature.body_id == terminal.body_id and not feature.suppressed
    ]
    if later_body_features:
        raise CadExportError(
            "Artifact feature must be the terminal body feature",
            detail={"feature_id": terminal_feature_id, "later_feature_ids": later_body_features, "error_code": "artifact_feature_not_terminal"},
        )
    features = [
        feature
        for feature in document.features[: terminal_index + 1]
        if feature.body_id == terminal.body_id and not feature.suppressed
    ]
    records = {record.feature_id: record for record in report.records}
    levels = sorted(
        {
            value
            for feature in features
            for value in (records[feature.feature_id].measurements.bounds_mm[-2:])
            if records[feature.feature_id].measurements is not None
        }
    )
    if len(levels) < 2:
        raise CadExportError("Feature body does not span a solid interval", detail={"feature_id": terminal_feature_id})
    profile_polygons: dict[str, Polygon] = {}
    slabs: list[tuple[float, float, Any]] = []
    for z_min, z_max in zip(levels, levels[1:]):
        midpoint = (z_min + z_max) / 2.0
        material: Any = GeometryCollection()
        for feature in features:
            record = records[feature.feature_id]
            if record.measurements is None:
                continue
            feature_z_min, feature_z_max = record.measurements.bounds_mm[-2:]
            if not (feature_z_min < midpoint < feature_z_max):
                continue
            if isinstance(feature.parameters, ExtrudeParameters):
                polygon = profile_polygons.setdefault(
                    feature.feature_id,
                    _profile_polygon(document, feature.sketch_id, str(feature.profile_id)),
                )
                if feature.parameters.operation == "new_body":
                    material = polygon
                elif feature.parameters.operation == "add":
                    material = material.union(polygon)
                else:
                    material = material.difference(polygon)
            elif isinstance(feature.parameters, HoleParameters):
                if feature.parameters.style != "simple":
                    raise CadExportError(
                        "Layered STL currently supports simple hole features",
                        detail={"feature_id": feature.feature_id, "style": feature.parameters.style, "error_code": "unsupported_layered_hole_style"},
                    )
                cutter = Point(feature.parameters.position_mm).buffer(feature.parameters.diameter_mm / 2.0, quad_segs=90)
                material = material.difference(cutter)
        if material.is_empty or not material.is_valid:
            raise CadExportError(
                "Feature graph produced an empty or invalid material layer",
                detail={"z_min": z_min, "z_max": z_max, "feature_id": terminal_feature_id},
            )
        slabs.append((z_min, z_max, material))

    mesh = _layered_mesh(slabs, units=document.units, terminal_feature_id=terminal_feature_id)
    positive_bounds = [
        records[feature.feature_id].measurements.bounds_mm
        for feature in features
        if records[feature.feature_id].measurements is not None
        and records[feature.feature_id].measurements.volume_delta_mm3 > 0
    ]
    mesh["metadata"].update(
        {
            "expected_volume_mm3": sum(records[feature.feature_id].measurements.volume_delta_mm3 for feature in features),
            "expected_bounds_mm": (
                min(item[0] for item in positive_bounds),
                max(item[1] for item in positive_bounds),
                min(item[2] for item in positive_bounds),
                max(item[3] for item in positive_bounds),
                min(item[4] for item in positive_bounds),
                max(item[5] for item in positive_bounds),
            ),
            "feature_ids": [feature.feature_id for feature in features],
            "circle_segments": 360,
        }
    )
    return mesh
