from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Iterable

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polygonize_full, unary_union

from sketchmath.geometry.profiles import analyze_closed_polygon
from sketchmath.geometry.tolerances import DEFAULT_TOLERANCE_POLICY
from sketchmath.geometry.vectors import Point2D
from sketchmath.models.constraints import CoincidentConstraint
from sketchmath.models.entities import Arc2DEntity, Circle2DEntity, Line2DEntity, Point2DEntity
from sketchmath.models.selection_context import SelectionContext
from sketchmath.models.topology import PlanarLoop, PlanarRegion, PlanarTopologyResult, RegionSelection, TopologyDiagnostic


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        root = self.parent.setdefault(value, value)
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            value, self.parent[value] = self.parent[value], root
        return root

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


@dataclass(frozen=True)
class _Edge:
    line_id: str
    start_key: str
    end_key: str
    start: Point2D
    end: Point2D
    start_point_id: str | None
    end_point_id: str | None


@dataclass(frozen=True)
class _TopologyCurve:
    curve_id: str
    points: tuple[Point2D, ...]
    geometry: LineString


def _coord_key(point: Point2D) -> str:
    return f"coord:{point[0]!r},{point[1]!r}"


def _endpoint_key(line: Line2DEntity, start: bool) -> str:
    point_id = line.start_point_id if start else line.end_point_id
    coords = line.start if start else line.end
    return point_id or _coord_key(coords)


def _segments_cross(vertices: list[Point2D]) -> bool:
    def orient(a: Point2D, b: Point2D, c: Point2D) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    segments = list(zip(vertices[:-1], vertices[1:]))
    for i, (a, b) in enumerate(segments):
        for j, (c, d) in enumerate(segments):
            if j <= i or j in {i - 1, i + 1} or (i == 0 and j == len(segments) - 1):
                continue
            if orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0:
                return True
    return False


def detect_line_profiles(state: SelectionContext) -> list[dict[str, object]]:
    lines = sorted((item for item in state.items if isinstance(item, Line2DEntity)), key=lambda item: item.id)
    keys = [_endpoint_key(line, start) for line in lines for start in (True, False)]
    uf = _UnionFind(keys)
    for constraint in state.constraints:
        if isinstance(constraint, CoincidentConstraint):
            uf.union(*constraint.points)

    point_map = {item.id: item.coords for item in state.items if isinstance(item, Point2DEntity)}
    edges = [
        _Edge(
            line.id,
            uf.find(_endpoint_key(line, True)),
            uf.find(_endpoint_key(line, False)),
            point_map.get(line.start_point_id or "", line.start),
            point_map.get(line.end_point_id or "", line.end),
            line.start_point_id,
            line.end_point_id,
        )
        for line in lines
    ]
    adjacency: dict[str, list[_Edge]] = {}
    for edge in edges:
        if edge.start_key == edge.end_key:
            continue
        adjacency.setdefault(edge.start_key, []).append(edge)
        adjacency.setdefault(edge.end_key, []).append(edge)

    candidates: list[dict[str, object]] = []
    visited_nodes: set[str] = set()
    for seed in sorted(adjacency):
        if seed in visited_nodes:
            continue
        component: set[str] = set()
        stack = [seed]
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(
                edge.end_key if edge.start_key == node else edge.start_key
                for edge in adjacency.get(node, [])
            )
        visited_nodes.update(component)
        if len(component) < 3 or any(len(adjacency[node]) != 2 for node in component):
            continue

        start = min(component)
        node = start
        previous_line: str | None = None
        ordered_edges: list[_Edge] = []
        vertices: list[Point2D] = []
        point_ids: list[str] = []
        for _ in range(len(component) + 1):
            choices = sorted((edge for edge in adjacency[node] if edge.line_id != previous_line), key=lambda edge: edge.line_id)
            if not choices:
                break
            edge = choices[0]
            forward = edge.start_key == node
            vertices.append(edge.start if forward else edge.end)
            point_id = edge.start_point_id if forward else edge.end_point_id
            if point_id:
                point_ids.append(point_id)
            ordered_edges.append(edge)
            previous_line = edge.line_id
            node = edge.end_key if forward else edge.start_key
            if node == start:
                vertices.append(vertices[0])
                break
        if node != start or len(ordered_edges) != len(component):
            continue
        analysis = analyze_closed_polygon(vertices)
        warnings = list(analysis.warnings)
        valid = analysis.area > 0 and not _segments_cross(vertices)
        if not valid and "self-intersecting profile" not in warnings:
            warnings.append("self-intersecting profile" if _segments_cross(vertices) else "profile area is zero")
        candidates.append(
            {
                "candidate_id": "profile_candidate_" + "_".join(sorted(edge.line_id for edge in ordered_edges)),
                "line_ids": [edge.line_id for edge in ordered_edges],
                "point_ids": point_ids,
                "vertices": vertices,
                "valid": valid,
                "area": analysis.area,
                "winding": analysis.winding,
                "warnings": warnings,
            }
        )
    return sorted(candidates, key=lambda item: str(item["candidate_id"]))


TOPOLOGY_NODE_TOLERANCE_MM = max(DEFAULT_TOLERANCE_POLICY.coordinate_abs_mm * 100.0, 1e-7)
TOPOLOGY_NEAR_VERTEX_MM = 1e-5
TOPOLOGY_ARC_STEP_DEG = 2.0


def _node_point(point: Point2D) -> Point2D:
    decimal_places = max(0, int(round(-math.log10(TOPOLOGY_NODE_TOLERANCE_MM))))
    return (round(float(point[0]), decimal_places), round(float(point[1]), decimal_places))


def _sample_arc(entity: Arc2DEntity) -> tuple[Point2D, ...]:
    segment_count = max(2, int(math.ceil(abs(entity.sweep_angle_deg) / TOPOLOGY_ARC_STEP_DEG)))
    return tuple(
        (
            entity.center[0] + entity.radius * math.cos(math.radians(entity.start_angle_deg + entity.sweep_angle_deg * index / segment_count)),
            entity.center[1] + entity.radius * math.sin(math.radians(entity.start_angle_deg + entity.sweep_angle_deg * index / segment_count)),
        )
        for index in range(segment_count + 1)
    )


def _sample_circle(entity: Circle2DEntity) -> tuple[Point2D, ...]:
    segment_count = max(24, int(math.ceil(360.0 / TOPOLOGY_ARC_STEP_DEG)))
    points = tuple(
        (
            entity.center[0] + entity.radius * math.cos(2.0 * math.pi * index / segment_count),
            entity.center[1] + entity.radius * math.sin(2.0 * math.pi * index / segment_count),
        )
        for index in range(segment_count)
    )
    return (*points, points[0])


def _topology_curves(state: SelectionContext) -> tuple[list[_TopologyCurve], list[TopologyDiagnostic]]:
    point_map = {item.id: item.coords for item in state.items if isinstance(item, Point2DEntity)}
    curves: list[_TopologyCurve] = []
    diagnostics: list[TopologyDiagnostic] = []
    for entity in sorted(state.items, key=lambda item: item.id):
        if isinstance(entity, Line2DEntity):
            points = (
                point_map.get(entity.start_point_id or "", entity.start),
                point_map.get(entity.end_point_id or "", entity.end),
            )
        elif isinstance(entity, Circle2DEntity):
            points = _sample_circle(entity)
        elif isinstance(entity, Arc2DEntity):
            points = _sample_arc(entity)
        else:
            continue
        points = tuple(_node_point(point) for point in points)
        geometry = LineString(points)
        if geometry.length <= TOPOLOGY_NODE_TOLERANCE_MM:
            diagnostics.append(
                TopologyDiagnostic(
                    code="degenerate_curve",
                    severity="error",
                    message="Curve length is below the topology tolerance.",
                    curve_ids=[entity.id],
                )
            )
            continue
        if not geometry.is_simple:
            diagnostics.append(
                TopologyDiagnostic(
                    code="self_intersecting_curve",
                    severity="error",
                    message="A source curve intersects itself.",
                    curve_ids=[entity.id],
                )
            )
        curves.append(_TopologyCurve(entity.id, tuple(points), geometry))
    return curves, diagnostics


def _geometry_points(geometry: object) -> list[Point2D]:
    geom_type = getattr(geometry, "geom_type", "")
    if geom_type == "Point":
        return [(float(geometry.x), float(geometry.y))]  # type: ignore[attr-defined]
    if geom_type in {"MultiPoint", "GeometryCollection"}:
        points: list[Point2D] = []
        for item in geometry.geoms:  # type: ignore[attr-defined]
            points.extend(_geometry_points(item))
        return points
    return []


def _endpoint_distance(point: Point2D, curve: _TopologyCurve) -> float:
    return min(math.dist(point, curve.points[0]), math.dist(point, curve.points[-1]))


def _pair_diagnostics(curves: list[_TopologyCurve]) -> list[TopologyDiagnostic]:
    diagnostics: list[TopologyDiagnostic] = []
    for left_index, left in enumerate(curves):
        for right in curves[left_index + 1 :]:
            for left_point in (left.points[0], left.points[-1]):
                for right_point in (right.points[0], right.points[-1]):
                    gap = math.dist(left_point, right_point)
                    if TOPOLOGY_NODE_TOLERANCE_MM < gap <= TOPOLOGY_NEAR_VERTEX_MM:
                        diagnostics.append(
                            TopologyDiagnostic(
                                code="near_vertex_gap",
                                severity="warning",
                                message="Curve endpoints are near but not coincident; no automatic snap was applied.",
                                curve_ids=sorted([left.curve_id, right.curve_id]),
                                point=((left_point[0] + right_point[0]) / 2.0, (left_point[1] + right_point[1]) / 2.0),
                                detail={"gap_mm": gap},
                            )
                        )
            intersection = left.geometry.intersection(right.geometry)
            if intersection.is_empty:
                continue
            if intersection.length > TOPOLOGY_NODE_TOLERANCE_MM:
                diagnostics.append(
                    TopologyDiagnostic(
                        code="overlapping_curves",
                        severity="warning",
                        message="Curves share a finite segment; the overlap is noded once for region extraction.",
                        curve_ids=sorted([left.curve_id, right.curve_id]),
                        detail={"overlap_length_mm": float(intersection.length)},
                    )
                )
                continue
            for point in _geometry_points(intersection):
                left_at_endpoint = _endpoint_distance(point, left) <= TOPOLOGY_NODE_TOLERANCE_MM
                right_at_endpoint = _endpoint_distance(point, right) <= TOPOLOGY_NODE_TOLERANCE_MM
                if left_at_endpoint and right_at_endpoint:
                    continue
                diagnostics.append(
                    TopologyDiagnostic(
                        code="t_junction" if left_at_endpoint != right_at_endpoint else "curve_intersection",
                        severity="warning" if left_at_endpoint != right_at_endpoint else "info",
                        message=(
                            "A curve endpoint terminates on another curve; planar noding preserved the branch."
                            if left_at_endpoint != right_at_endpoint
                            else "Curves intersect inside their finite spans and were deterministically noded."
                        ),
                        curve_ids=sorted([left.curve_id, right.curve_id]),
                        point=point,
                    )
                )
    return diagnostics


def _curve_components(curves: list[_TopologyCurve]) -> list[list[str]]:
    uf = _UnionFind(curve.curve_id for curve in curves)
    for left_index, left in enumerate(curves):
        for right in curves[left_index + 1 :]:
            if left.geometry.distance(right.geometry) <= TOPOLOGY_NODE_TOLERANCE_MM:
                uf.union(left.curve_id, right.curve_id)
    groups: dict[str, list[str]] = {}
    for curve in curves:
        groups.setdefault(uf.find(curve.curve_id), []).append(curve.curve_id)
    return sorted((sorted(group) for group in groups.values()), key=lambda group: group[0])


def _canonical_vertices(coordinates: Iterable[tuple[float, float]]) -> list[Point2D]:
    rounded = [(round(float(x), 9), round(float(y), 9)) for x, y in coordinates]
    if rounded and rounded[0] != rounded[-1]:
        rounded.append(rounded[0])
    if len(rounded) <= 1:
        return rounded
    open_ring = rounded[:-1]
    rotations = [open_ring[index:] + open_ring[:index] for index in range(len(open_ring))]
    canonical = min(rotations)
    return [*canonical, canonical[0]]


def _stable_id(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:16]}"


def _source_ids_for_ring(ring: LineString, curves: list[_TopologyCurve]) -> list[str]:
    return sorted(
        curve.curve_id
        for curve in curves
        if curve.geometry.intersection(ring).length > TOPOLOGY_NODE_TOLERANCE_MM
    )


def _planar_loop(ring: LineString, curves: list[_TopologyCurve], *, outer: bool) -> PlanarLoop:
    vertices = _canonical_vertices(ring.coords)
    analysis = analyze_closed_polygon(vertices)
    source_ids = _source_ids_for_ring(ring, curves)
    return PlanarLoop(
        loop_id=_stable_id("loop", {"vertices": vertices, "role": "outer" if outer else "hole"}),
        vertices=vertices,
        winding=analysis.winding,  # type: ignore[arg-type]
        area=analysis.area,
        source_curve_ids=source_ids,
    )


def _collection_source_ids(collection: object, curves: list[_TopologyCurve]) -> list[str]:
    ids: set[str] = set()
    for geometry in getattr(collection, "geoms", []):
        for curve in curves:
            if curve.geometry.intersection(geometry).length > TOPOLOGY_NODE_TOLERANCE_MM:
                ids.add(curve.curve_id)
    return sorted(ids)


def _dedupe_diagnostics(diagnostics: list[TopologyDiagnostic]) -> list[TopologyDiagnostic]:
    unique: dict[str, TopologyDiagnostic] = {}
    for diagnostic in diagnostics:
        key = json.dumps(diagnostic.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        unique[key] = diagnostic
    return sorted(
        unique.values(),
        key=lambda item: (item.severity, item.code, item.curve_ids, item.point or (0.0, 0.0)),
    )


def detect_planar_regions(state: SelectionContext, *, selection_point: Point2D | None = None) -> PlanarTopologyResult:
    curves, diagnostics = _topology_curves(state)
    diagnostics.extend(_pair_diagnostics(curves))
    components = _curve_components(curves)
    if len(components) > 1:
        diagnostics.append(
            TopologyDiagnostic(
                code="disconnected_components",
                severity="info",
                message="The sketch contains disconnected curve components; each component was analyzed.",
                curve_ids=sorted(curve.curve_id for curve in curves),
                detail={"component_count": len(components), "components": components},
            )
        )

    polygons: list[Polygon] = []
    if curves:
        noded = unary_union([curve.geometry for curve in curves])
        polygon_collection, cut_edges, dangles, invalid_rings = polygonize_full(noded)
        polygons = [orient(polygon, sign=1.0) for polygon in polygon_collection.geoms if polygon.area > TOPOLOGY_NODE_TOLERANCE_MM**2]
        for code, severity, message, collection in (
            ("open_branches", "warning", "Open or branched edges do not bound a region.", cut_edges),
            ("dangles", "warning", "Dangling edges were excluded from region boundaries.", dangles),
            ("invalid_rings", "error", "Invalid ring linework could not form a planar region.", invalid_rings),
        ):
            if not collection.is_empty:
                diagnostics.append(
                    TopologyDiagnostic(
                        code=code,
                        severity=severity,  # type: ignore[arg-type]
                        message=message,
                        curve_ids=_collection_source_ids(collection, curves),
                        detail={"geometry_count": len(collection.geoms)},
                    )
                )
    if curves and not polygons:
        diagnostics.append(
            TopologyDiagnostic(
                code="no_bounded_regions",
                severity="warning",
                message="No bounded planar regions were found.",
                curve_ids=[curve.curve_id for curve in curves],
            )
        )

    region_pairs: list[tuple[PlanarRegion, Polygon]] = []
    for polygon in polygons:
        outer_ring = LineString(polygon.exterior.coords)
        outer_loop = _planar_loop(outer_ring, curves, outer=True)
        holes = [
            _planar_loop(LineString(interior.coords), curves, outer=False)
            for interior in polygon.interiors
        ]
        holes.sort(key=lambda loop: loop.loop_id)
        source_ids = sorted(set(outer_loop.source_curve_ids).union(*(set(hole.source_curve_ids) for hole in holes)))
        region_id = _stable_id(
            "region",
            {"outer_loop_id": outer_loop.loop_id, "hole_loop_ids": [hole.loop_id for hole in holes]},
        )
        centroid = polygon.representative_point()
        region_pairs.append(
            (
                PlanarRegion(
                    region_id=region_id,
                    outer_loop=outer_loop,
                    holes=holes,
                    area=float(polygon.area),
                    centroid=(float(centroid.x), float(centroid.y)),
                    bounds=tuple(float(value) for value in polygon.bounds),  # type: ignore[arg-type]
                    source_curve_ids=source_ids,
                ),
                polygon,
            )
        )

    for index, (region, polygon) in enumerate(region_pairs):
        representative = polygon.representative_point()
        depth = sum(
            1
            for other_index, (_, other) in enumerate(region_pairs)
            if other_index != index and Polygon(other.exterior.coords).contains(representative)
        )
        region_pairs[index] = (region.model_copy(update={"nesting_depth": depth}), polygon)
    region_pairs.sort(key=lambda pair: pair[0].region_id)

    selection = RegionSelection()
    if selection_point is not None:
        selected_ids: list[str] = []
        boundary_ids: list[str] = []
        query = Point(selection_point)
        for region, polygon in region_pairs:
            if polygon.boundary.distance(query) <= TOPOLOGY_NODE_TOLERANCE_MM:
                boundary_ids.append(region.region_id)
            elif polygon.contains(query):
                selected_ids.append(region.region_id)
        status = "boundary" if boundary_ids else "none" if not selected_ids else "selected" if len(selected_ids) == 1 else "ambiguous"
        selection = RegionSelection(
            status=status,
            point=selection_point,
            region_ids=sorted(selected_ids),
            boundary_region_ids=sorted(boundary_ids),
        )

    return PlanarTopologyResult(
        regions=[region for region, _ in region_pairs],
        diagnostics=_dedupe_diagnostics(diagnostics),
        selection=selection,
        source_curve_ids=[curve.curve_id for curve in curves],
        approximation={
            "curve_mode": "piecewise_linear",
            "max_arc_step_deg": TOPOLOGY_ARC_STEP_DEG,
            "node_tolerance_mm": TOPOLOGY_NODE_TOLERANCE_MM,
            "near_vertex_warning_mm": TOPOLOGY_NEAR_VERTEX_MM,
        },
    )
