from __future__ import annotations

from .vectors import Point2D, subtract


def project_point_to_line(point: Point2D, line_start: Point2D, line_end: Point2D) -> Point2D:
    lx, ly = subtract(line_end, line_start)
    denom = lx * lx + ly * ly
    if denom == 0:
        raise ValueError("Cannot project onto a zero-length line")
    px, py = subtract(point, line_start)
    t = (px * lx + py * ly) / denom
    return (float(line_start[0] + t * lx), float(line_start[1] + t * ly))
