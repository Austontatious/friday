from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _EntityBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    locked: bool = False
    label: str | None = None


class Point2DEntity(_EntityBase):
    type: Literal["point_2d"] = "point_2d"
    coords: tuple[float, float]


class Line2DEntity(_EntityBase):
    type: Literal["line_2d"] = "line_2d"
    start: tuple[float, float]
    end: tuple[float, float]
    start_point_id: str | None = None
    end_point_id: str | None = None


class Axis2DEntity(_EntityBase):
    type: Literal["axis_2d"] = "axis_2d"
    origin: tuple[float, float]
    direction: tuple[float, float]


class ConstructionLine2DEntity(_EntityBase):
    type: Literal["construction_line_2d"] = "construction_line_2d"
    start: tuple[float, float]
    end: tuple[float, float]
    start_point_id: str | None = None
    end_point_id: str | None = None


class Circle2DEntity(_EntityBase):
    type: Literal["circle_2d"] = "circle_2d"
    center: tuple[float, float]
    radius: float = Field(gt=0)
    center_point_id: str | None = None


class Arc2DEntity(_EntityBase):
    type: Literal["arc_2d"] = "arc_2d"
    center: tuple[float, float]
    radius: float = Field(gt=0)
    start_angle_deg: float
    sweep_angle_deg: float
    construction: Literal["center", "three_point"]
    center_point_id: str | None = None
    start_point_id: str | None = None
    through_point_id: str | None = None
    end_point_id: str | None = None

    @field_validator("center")
    @classmethod
    def validate_center(cls, value: tuple[float, float]) -> tuple[float, float]:
        if not all(math.isfinite(coordinate) for coordinate in value):
            raise ValueError("arc center coordinates must be finite")
        return value

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("arc radius must be finite")
        return value

    @field_validator("start_angle_deg")
    @classmethod
    def normalize_start_angle(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("arc start angle must be finite")
        normalized = value % 360.0
        return 0.0 if math.isclose(normalized, 360.0, abs_tol=1e-12) else normalized

    @field_validator("sweep_angle_deg")
    @classmethod
    def validate_sweep(cls, value: float) -> float:
        if not -360.0 < value < 360.0 or abs(value) <= 1e-9:
            raise ValueError("arc sweep must be non-zero and less than 360 degrees")
        return value


class Profile2DEntity(_EntityBase):
    type: Literal["profile_2d"] = "profile_2d"
    vertices: list[tuple[float, float]]
    area: float
    winding: Literal["clockwise", "counterclockwise", "degenerate"]
    warnings: list[str] = Field(default_factory=list)
    closed: bool = True
    holes: list[str] = Field(default_factory=list)
    source_line_ids: list[str] = Field(default_factory=list)
    source_circle_id: str | None = None


SelectionEntity = Annotated[
    Point2DEntity | Line2DEntity | Axis2DEntity | ConstructionLine2DEntity | Circle2DEntity | Arc2DEntity | Profile2DEntity,
    Field(discriminator="type"),
]
