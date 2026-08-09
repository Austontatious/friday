from __future__ import annotations

import pytest

from sketchmath.cad.preview_mesh import build_preview_mesh
from sketchmath.cad.stl_export import mesh_measurements, render_ascii_stl, write_ascii_stl
from sketchmath.models.entities import Profile2DEntity


def _profile(profile_id: str, vertices: list[tuple[float, float]], area: float, winding: str) -> Profile2DEntity:
    return Profile2DEntity.model_validate(
        {
            "id": profile_id,
            "type": "profile_2d",
            "vertices": vertices,
            "area": area,
            "winding": winding,
            "closed": True,
        }
    )


def test_ascii_stl_is_deterministic_and_preserves_holed_extrusion_measurements(tmp_path) -> None:
    outer = _profile("plate", [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], 100, "counterclockwise")
    hole = _profile("hole", [(3, 3), (3, 7), (7, 7), (7, 3), (3, 3)], 16, "clockwise")
    mesh = build_preview_mesh(outer, holes=[hole], depth=10)

    first = render_ascii_stl(mesh, solid_name="golden_plate")
    second = render_ascii_stl(mesh, solid_name="golden_plate")
    measurements = mesh_measurements(mesh)
    path = tmp_path / "golden_plate.stl"
    artifact = write_ascii_stl(mesh, path, solid_name="golden_plate")

    assert first == second == path.read_text(encoding="ascii")
    assert first.startswith("solid golden_plate\n")
    assert first.endswith("endsolid golden_plate\n")
    assert measurements["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 10}
    )
    assert measurements["volume_mm3"] == pytest.approx(840.0)
    assert measurements["triangle_count"] == mesh["metadata"]["triangle_count"]
    assert artifact["content_hash"]
    assert artifact["size_bytes"] > 0
