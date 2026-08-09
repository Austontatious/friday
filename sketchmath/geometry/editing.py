from __future__ import annotations

from dataclasses import dataclass
import math

from sketchmath.geometry.tolerances import DEFAULT_TOLERANCE_POLICY
from sketchmath.geometry.vectors import Point2D, add, distance, scale, subtract


@dataclass(frozen=True)
class LineIntersection:
    point: Point2D
    first_parameter: float
    second_parameter: float


@dataclass(frozen=True)
class SlotBoundary:
    center_start: Point2D
    center_end: Point2D
    start_positive: Point2D
    end_positive: Point2D
    end_negative: Point2D
    start_negative: Point2D
    radius: float
    end_arc_start_angle_deg: float
    start_arc_start_angle_deg: float


def regular_polygon_vertices(
    center: Point2D,
    radius: float,
    sides: int,
    rotation_deg: float = -90.0,
) -> list[Point2D]:
    if sides < 3 or sides > 128:
        raise ValueError("regular polygon sides must be between 3 and 128")
    if not math.isfinite(radius) or radius <= DEFAULT_TOLERANCE_POLICY.coordinate_abs_mm:
        raise ValueError("regular polygon radius must be positive")
    if not all(math.isfinite(value) for value in center) or not math.isfinite(rotation_deg):
        raise ValueError("regular polygon geometry must be finite")
    start = math.radians(rotation_deg)
    vertices = [
        (
            center[0] + radius * math.cos(start + 2.0 * math.pi * index / sides),
            center[1] + radius * math.sin(start + 2.0 * math.pi * index / sides),
        )
        for index in range(sides)
    ]
    return [*vertices, vertices[0]]


def slot_boundary(center_start: Point2D, center_end: Point2D, width: float) -> SlotBoundary:
    length = distance(center_start, center_end)
    if length <= DEFAULT_TOLERANCE_POLICY.coordinate_abs_mm:
        raise ValueError("slot centers must be distinct")
    if not math.isfinite(width) or width <= 2.0 * DEFAULT_TOLERANCE_POLICY.coordinate_abs_mm:
        raise ValueError("slot width must be positive")
    direction = scale(subtract(center_end, center_start), 1.0 / length)
    normal = (-direction[1], direction[0])
    radius = width / 2.0
    start_positive = add(center_start, scale(normal, radius))
    end_positive = add(center_end, scale(normal, radius))
    end_negative = add(center_end, scale(normal, -radius))
    start_negative = add(center_start, scale(normal, -radius))
    return SlotBoundary(
        center_start=center_start,
        center_end=center_end,
        start_positive=start_positive,
        end_positive=end_positive,
        end_negative=end_negative,
        start_negative=start_negative,
        radius=radius,
        end_arc_start_angle_deg=math.degrees(math.atan2(normal[1], normal[0])) % 360.0,
        start_arc_start_angle_deg=math.degrees(math.atan2(-normal[1], -normal[0])) % 360.0,
    )


def line_intersection_parameters(
    first_start: Point2D,
    first_end: Point2D,
    second_start: Point2D,
    second_end: Point2D,
) -> LineIntersection:
    first = subtract(first_end, first_start)
    second = subtract(second_end, second_start)
    denominator = first[0] * second[1] - first[1] * second[0]
    scale_value = max(distance(first_start, first_end), distance(second_start, second_end), 1.0)
    if abs(denominator) <= DEFAULT_TOLERANCE_POLICY.linear_rank_abs * scale_value * scale_value:
        raise ValueError("lines are parallel or coincident")
    offset = subtract(second_start, first_start)
    first_parameter = (offset[0] * second[1] - offset[1] * second[0]) / denominator
    second_parameter = (offset[0] * first[1] - offset[1] * first[0]) / denominator
    return LineIntersection(
        point=add(first_start, scale(first, first_parameter)),
        first_parameter=first_parameter,
        second_parameter=second_parameter,
    )


def offset_segment(start: Point2D, end: Point2D, offset: float) -> tuple[Point2D, Point2D]:
    segment_length = distance(start, end)
    if segment_length <= DEFAULT_TOLERANCE_POLICY.coordinate_abs_mm:
        raise ValueError("cannot offset a zero-length line")
    direction = scale(subtract(end, start), 1.0 / segment_length)
    normal = (-direction[1], direction[0])
    delta = scale(normal, offset)
    return add(start, delta), add(end, delta)
