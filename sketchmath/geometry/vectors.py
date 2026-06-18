from __future__ import annotations

import math
from typing import Iterable


Point2D = tuple[float, float]


def add(a: Point2D, b: Point2D) -> Point2D:
    return (float(a[0] + b[0]), float(a[1] + b[1]))


def subtract(a: Point2D, b: Point2D) -> Point2D:
    return (float(a[0] - b[0]), float(a[1] - b[1]))


def scale(a: Point2D, factor: float) -> Point2D:
    return (float(a[0] * factor), float(a[1] * factor))


def distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def midpoint(a: Point2D, b: Point2D) -> Point2D:
    return (float((a[0] + b[0]) / 2.0), float((a[1] + b[1]) / 2.0))


def normalize(v: Point2D) -> Point2D:
    length = math.hypot(v[0], v[1])
    if length == 0:
        return (1.0, 0.0)
    return (float(v[0] / length), float(v[1] / length))


def rotate_point(point: Point2D, angle_radians: float, origin: Point2D = (0.0, 0.0)) -> Point2D:
    ox, oy = origin
    px, py = point[0] - ox, point[1] - oy
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return (
        float(ox + px * cos_a - py * sin_a),
        float(oy + px * sin_a + py * cos_a),
    )


def average(points: Iterable[Point2D]) -> Point2D:
    pts = list(points)
    if not pts:
        return (0.0, 0.0)
    return (
        float(sum(p[0] for p in pts) / len(pts)),
        float(sum(p[1] for p in pts) / len(pts)),
    )
