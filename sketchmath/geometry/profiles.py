from __future__ import annotations

from dataclasses import dataclass

from .vectors import Point2D


@dataclass(frozen=True)
class ProfileAnalysis:
    vertices: list[Point2D]
    area: float
    winding: str
    warnings: list[str]
    closed: bool


def _shoelace_area(vertices: list[Point2D]) -> float:
    if len(vertices) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(vertices):
        next_point = vertices[(index + 1) % len(vertices)]
        total += point[0] * next_point[1] - next_point[0] * point[1]
    return abs(total) / 2.0


def analyze_closed_polygon(vertices: list[Point2D]) -> ProfileAnalysis:
    warnings: list[str] = []
    if len(vertices) < 3:
        raise ValueError("Profile requires at least three vertices")
    if vertices[0] != vertices[-1]:
        raise ValueError("Profile is not closed")
    unique_vertices = vertices[:-1]
    area = _shoelace_area(unique_vertices)
    if area == 0.0:
        winding = "degenerate"
        warnings.append("profile area is zero")
    else:
        signed = 0.0
        for index, point in enumerate(unique_vertices):
            next_point = unique_vertices[(index + 1) % len(unique_vertices)]
            signed += point[0] * next_point[1] - next_point[0] * point[1]
        winding = "counterclockwise" if signed > 0 else "clockwise"
    return ProfileAnalysis(vertices=vertices, area=area, winding=winding, warnings=warnings, closed=True)


def vertices_from_line_chain(points: list[Point2D]) -> list[Point2D]:
    if len(points) < 3:
        raise ValueError("Profile requires at least three points")
    return points
