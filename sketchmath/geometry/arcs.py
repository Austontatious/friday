from __future__ import annotations

import math
from typing import Literal

from sketchmath.geometry.tolerances import DEFAULT_TOLERANCE_POLICY
from sketchmath.geometry.vectors import Point2D, distance


ArcDirection = Literal["clockwise", "counterclockwise"]


def normalize_angle_degrees(value: float) -> float:
    normalized = value % 360.0
    return 0.0 if math.isclose(normalized, 360.0, abs_tol=1e-12) else normalized


def point_angle_degrees(center: Point2D, point: Point2D) -> float:
    return normalize_angle_degrees(math.degrees(math.atan2(point[1] - center[1], point[0] - center[0])))


def arc_endpoints(center: Point2D, radius: float, start_angle_deg: float, sweep_angle_deg: float) -> tuple[Point2D, Point2D]:
    start_radians = math.radians(start_angle_deg)
    end_radians = math.radians(start_angle_deg + sweep_angle_deg)
    return (
        (center[0] + radius * math.cos(start_radians), center[1] + radius * math.sin(start_radians)),
        (center[0] + radius * math.cos(end_radians), center[1] + radius * math.sin(end_radians)),
    )


def center_arc_geometry(
    center: Point2D,
    start: Point2D,
    end: Point2D,
    *,
    direction: ArcDirection,
) -> tuple[float, float, float]:
    radius = distance(center, start)
    if radius <= DEFAULT_TOLERANCE_POLICY.coordinate_abs_mm:
        raise ValueError("arc center and start point must be distinct")
    if distance(center, end) <= DEFAULT_TOLERANCE_POLICY.coordinate_abs_mm:
        raise ValueError("arc center and end point must be distinct")
    start_angle = point_angle_degrees(center, start)
    end_angle = point_angle_degrees(center, end)
    if direction == "clockwise":
        sweep = (end_angle - start_angle) % 360.0
    else:
        sweep = -((start_angle - end_angle) % 360.0)
    if abs(sweep) <= 1e-9:
        raise ValueError("arc start and end directions must be distinct")
    return radius, start_angle, sweep


def three_point_arc_geometry(start: Point2D, through: Point2D, end: Point2D) -> tuple[Point2D, float, float, float]:
    ax, ay = start
    bx, by = through
    cx, cy = end
    determinant = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    scale = max(distance(start, through), distance(through, end), distance(start, end), 1.0)
    if abs(determinant) <= DEFAULT_TOLERANCE_POLICY.linear_rank_abs * scale * scale:
        raise ValueError("three-point arc requires non-collinear points")
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    center = (
        (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / determinant,
        (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / determinant,
    )
    radius = distance(center, start)
    start_angle = point_angle_degrees(center, start)
    through_angle = point_angle_degrees(center, through)
    end_angle = point_angle_degrees(center, end)
    increasing_sweep = (end_angle - start_angle) % 360.0
    through_increasing = (through_angle - start_angle) % 360.0
    if 0.0 < through_increasing < increasing_sweep:
        sweep = increasing_sweep
    else:
        sweep = -((start_angle - end_angle) % 360.0)
    if abs(sweep) <= 1e-9:
        raise ValueError("three-point arc start and end must be distinct")
    return center, radius, start_angle, sweep
