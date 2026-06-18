from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _ConstraintBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    locked: bool = False
    label: str | None = None


class FixedPointConstraint(_ConstraintBase):
    type: Literal["fixed_point_constraint"] = "fixed_point_constraint"
    point_id: str
    coords: tuple[float, float]


class DistanceConstraint(_ConstraintBase):
    type: Literal["distance_constraint"] = "distance_constraint"
    points: tuple[str, str]
    distance: float
    unit: str = "mm"
    anchor: Literal["point_a", "point_b", "midpoint"] = "midpoint"


class AngleConstraint(_ConstraintBase):
    type: Literal["angle_constraint"] = "angle_constraint"
    points: tuple[str, str, str]
    angle: float
    unit: str = "deg"


class ParallelConstraint(_ConstraintBase):
    type: Literal["parallel_constraint"] = "parallel_constraint"
    points: tuple[str, str, str, str]


class PerpendicularConstraint(_ConstraintBase):
    type: Literal["perpendicular_constraint"] = "perpendicular_constraint"
    points: tuple[str, str, str, str]


class EqualLengthConstraint(_ConstraintBase):
    type: Literal["equal_length_constraint"] = "equal_length_constraint"
    points: tuple[str, str, str, str]


class EqualAngleConstraint(_ConstraintBase):
    type: Literal["equal_angle_constraint"] = "equal_angle_constraint"
    points: tuple[str, str, str, str, str, str]


ConstraintEntity = Annotated[
    FixedPointConstraint
    | DistanceConstraint
    | AngleConstraint
    | ParallelConstraint
    | PerpendicularConstraint
    | EqualLengthConstraint
    | EqualAngleConstraint,
    Field(discriminator="type"),
]
