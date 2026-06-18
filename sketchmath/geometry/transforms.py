from __future__ import annotations

from .units import normalize_angle, normalize_length
from .vectors import Point2D, add, average, midpoint, normalize, rotate_point, scale, subtract


def set_distance_between_points(
    a: Point2D,
    b: Point2D,
    distance_value: float,
    *,
    anchor: str = "midpoint",
    unit: str = "mm",
) -> tuple[Point2D, Point2D]:
    target_distance = normalize_length(distance_value, unit)
    direction = normalize(subtract(b, a))
    if anchor == "midpoint":
        center = midpoint(a, b)
        half = target_distance / 2.0
        offset = scale(direction, half)
        return subtract(center, offset), add(center, offset)
    if anchor == "point_a":
        return a, add(a, scale(direction, target_distance))
    if anchor == "point_b":
        return subtract(b, scale(direction, target_distance)), b
    raise ValueError(f"Unsupported anchor for set_distance: {anchor}")


def set_line_polar(
    start: Point2D,
    length_value: float,
    angle_value: float,
    *,
    length_unit: str = "mm",
    angle_unit: str = "deg",
) -> Point2D:
    length = normalize_length(length_value, length_unit)
    angle = normalize_angle(angle_value, angle_unit)
    delta = (length, 0.0)
    return add(start, rotate_point(delta, angle))


def translate_point(point: Point2D, delta: Point2D) -> Point2D:
    return add(point, delta)


def rotate_point_around(point: Point2D, angle_value: float, *, origin: Point2D = (0.0, 0.0), angle_unit: str = "deg") -> Point2D:
    return rotate_point(point, normalize_angle(angle_value, angle_unit), origin)


def mirror_point_across_vertical_axis(point: Point2D, axis_x: float) -> Point2D:
    return (float(2.0 * axis_x - point[0]), float(point[1]))
