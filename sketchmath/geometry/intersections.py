from __future__ import annotations

from .vectors import Point2D


def intersect_lines(a_start: Point2D, a_end: Point2D, b_start: Point2D, b_end: Point2D) -> Point2D:
    x1, y1 = a_start
    x2, y2 = a_end
    x3, y3 = b_start
    x4, y4 = b_end

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if denom == 0:
        raise ValueError("Lines are parallel and do not intersect")

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return (float(px), float(py))
