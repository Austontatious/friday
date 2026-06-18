from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class SolidValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    measurements: dict[str, Any] = field(default_factory=dict)


def expected_bbox_from_outer(vertices: list[tuple[float, float]], depth_mm: float, direction: str) -> dict[str, float]:
    xs = [float(point[0]) for point in vertices[:-1]]
    ys = [float(point[1]) for point in vertices[:-1]]
    zmin = 0.0 if direction == "positive_normal" else -float(depth_mm)
    zmax = float(depth_mm) if direction == "positive_normal" else 0.0
    return {
        "xmin": min(xs),
        "ymin": min(ys),
        "zmin": zmin,
        "xmax": max(xs),
        "ymax": max(ys),
        "zmax": zmax,
    }


def expected_volume_mm3(outer_area_mm2: float, hole_areas_mm2: list[float], depth_mm: float) -> float:
    return max(0.0, (float(outer_area_mm2) - sum(float(area) for area in hole_areas_mm2)) * abs(float(depth_mm)))


def _bbox_value(bbox: dict[str, float | None], key: str) -> float | None:
    value = bbox.get(key)
    return None if value is None else float(value)


def validate_solid_measurements(
    *,
    actual_bbox: dict[str, float | None],
    actual_volume_mm3: float | None,
    actual_is_valid_solid: bool | None,
    expected_bbox: dict[str, float],
    expected_volume_mm3: float,
    bbox_tolerance_mm: float = 1e-6,
    volume_tolerance_mm3: float = 1e-4,
) -> SolidValidationResult:
    if actual_is_valid_solid is False:
        return SolidValidationResult(
            ok=False,
            error_code="solid_validation_failed",
            message="FreeCAD reported the solid as invalid",
            details={"reason": "is_valid_solid_false"},
            measurements={
                "actual_bbox": actual_bbox,
                "actual_volume_mm3": actual_volume_mm3,
                "actual_is_valid_solid": actual_is_valid_solid,
                "expected_bbox": expected_bbox,
                "expected_volume_mm3": expected_volume_mm3,
            },
        )

    for key, expected_value in expected_bbox.items():
        actual_value = _bbox_value(actual_bbox, key)
        if actual_value is None:
            return SolidValidationResult(
                ok=False,
                error_code="solid_validation_failed",
                message=f"Missing bbox component: {key}",
                details={"component": key},
                measurements={
                    "actual_bbox": actual_bbox,
                    "actual_volume_mm3": actual_volume_mm3,
                    "actual_is_valid_solid": actual_is_valid_solid,
                    "expected_bbox": expected_bbox,
                    "expected_volume_mm3": expected_volume_mm3,
                },
            )
        if abs(actual_value - expected_value) > bbox_tolerance_mm:
            return SolidValidationResult(
                ok=False,
                error_code="solid_validation_failed",
                message=f"BBox mismatch on {key}",
                details={"component": key, "actual": actual_value, "expected": expected_value, "tolerance": bbox_tolerance_mm},
                measurements={
                    "actual_bbox": actual_bbox,
                    "actual_volume_mm3": actual_volume_mm3,
                    "actual_is_valid_solid": actual_is_valid_solid,
                    "expected_bbox": expected_bbox,
                    "expected_volume_mm3": expected_volume_mm3,
                },
            )

    if actual_volume_mm3 is None:
        return SolidValidationResult(
            ok=False,
            error_code="solid_validation_failed",
            message="Missing solid volume",
            details={"reason": "volume_missing"},
            measurements={
                "actual_bbox": actual_bbox,
                "actual_volume_mm3": actual_volume_mm3,
                "actual_is_valid_solid": actual_is_valid_solid,
                "expected_bbox": expected_bbox,
                "expected_volume_mm3": expected_volume_mm3,
            },
        )

    if abs(float(actual_volume_mm3) - float(expected_volume_mm3)) > volume_tolerance_mm3:
        return SolidValidationResult(
            ok=False,
            error_code="solid_validation_failed",
            message="Solid volume mismatch",
            details={"actual": float(actual_volume_mm3), "expected": float(expected_volume_mm3), "tolerance": volume_tolerance_mm3},
            measurements={
                "actual_bbox": actual_bbox,
                "actual_volume_mm3": actual_volume_mm3,
                "actual_is_valid_solid": actual_is_valid_solid,
                "expected_bbox": expected_bbox,
                "expected_volume_mm3": expected_volume_mm3,
            },
        )

    return SolidValidationResult(
        ok=True,
        measurements={
            "actual_bbox": actual_bbox,
            "actual_volume_mm3": actual_volume_mm3,
            "actual_is_valid_solid": actual_is_valid_solid,
            "expected_bbox": expected_bbox,
            "expected_volume_mm3": expected_volume_mm3,
        },
    )
