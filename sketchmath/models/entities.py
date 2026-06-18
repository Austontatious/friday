from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class Axis2DEntity(_EntityBase):
    type: Literal["axis_2d"] = "axis_2d"
    origin: tuple[float, float]
    direction: tuple[float, float]


class ConstructionLine2DEntity(_EntityBase):
    type: Literal["construction_line_2d"] = "construction_line_2d"
    start: tuple[float, float]
    end: tuple[float, float]


class Profile2DEntity(_EntityBase):
    type: Literal["profile_2d"] = "profile_2d"
    vertices: list[tuple[float, float]]
    area: float
    winding: Literal["clockwise", "counterclockwise", "degenerate"]
    warnings: list[str] = Field(default_factory=list)
    closed: bool = True


SelectionEntity = Annotated[
    Point2DEntity | Line2DEntity | Axis2DEntity | ConstructionLine2DEntity | Profile2DEntity,
    Field(discriminator="type"),
]
