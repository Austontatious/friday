from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sketchmath.geometry.profiles import analyze_closed_polygon
from sketchmath.geometry.vectors import Point2D
from sketchmath.models.constraints import CoincidentConstraint
from sketchmath.models.entities import Line2DEntity, Point2DEntity
from sketchmath.models.selection_context import SelectionContext


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
