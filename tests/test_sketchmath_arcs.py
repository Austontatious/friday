from __future__ import annotations

import pytest

from sketchmath.geometry.arcs import arc_endpoints, center_arc_geometry, three_point_arc_geometry


def test_center_arc_direction_controls_signed_sweep() -> None:
    radius, start, sweep = center_arc_geometry((0, 0), (2, 0), (0, 2), direction="counterclockwise")
    assert radius == pytest.approx(2.0)
    assert start == pytest.approx(0.0)
    assert sweep == pytest.approx(-270.0)
    arc_start, arc_end = arc_endpoints((0, 0), radius, start, sweep)
    assert arc_start == pytest.approx((2.0, 0.0))
    assert arc_end == pytest.approx((0.0, 2.0))


def test_three_point_arc_rejects_near_collinear_input() -> None:
    with pytest.raises(ValueError, match="non-collinear"):
        three_point_arc_geometry((0, 0), (1, 1e-12), (2, 0))
