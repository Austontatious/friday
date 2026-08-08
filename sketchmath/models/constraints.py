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


class HorizontalDistanceConstraint(_ConstraintBase):
    type: Literal["horizontal_distance_constraint"] = "horizontal_distance_constraint"
    points: tuple[str, str]
    distance: float = Field(gt=0)
    unit: str = "mm"
    direction: Literal[-1, 1] = 1
    anchor: Literal["point_a", "point_b", "midpoint"] = "midpoint"


class VerticalDistanceConstraint(_ConstraintBase):
    type: Literal["vertical_distance_constraint"] = "vertical_distance_constraint"
    points: tuple[str, str]
    distance: float = Field(gt=0)
    unit: str = "mm"
    direction: Literal[-1, 1] = 1
    anchor: Literal["point_a", "point_b", "midpoint"] = "midpoint"


class RadiusConstraint(_ConstraintBase):
    type: Literal["radius_constraint"] = "radius_constraint"
    circle_id: str
    radius: float = Field(gt=0)
    unit: str = "mm"


class DiameterConstraint(_ConstraintBase):
    type: Literal["diameter_constraint"] = "diameter_constraint"
    circle_id: str
    diameter: float = Field(gt=0)
    unit: str = "mm"


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


class HorizontalConstraint(_ConstraintBase):
    type: Literal["horizontal_constraint"] = "horizontal_constraint"
    points: tuple[str, str]


class VerticalConstraint(_ConstraintBase):
    type: Literal["vertical_constraint"] = "vertical_constraint"
    points: tuple[str, str]


class CoincidentConstraint(_ConstraintBase):
    type: Literal["coincident_constraint"] = "coincident_constraint"
    points: tuple[str, str]


class MidpointConstraint(_ConstraintBase):
    type: Literal["midpoint_constraint"] = "midpoint_constraint"
    point_id: str
    line_points: tuple[str, str]


class CollinearConstraint(_ConstraintBase):
    type: Literal["collinear_constraint"] = "collinear_constraint"
    points: tuple[str, str, str]


class SymmetricConstraint(_ConstraintBase):
    type: Literal["symmetric_constraint"] = "symmetric_constraint"
    points: tuple[str, str, str, str]


class ConcentricConstraint(_ConstraintBase):
    type: Literal["concentric_constraint"] = "concentric_constraint"
    entities: tuple[str, str]


class TangentConstraint(_ConstraintBase):
    type: Literal["tangent_constraint"] = "tangent_constraint"
    entities: tuple[str, str]
    tangency: Literal["external", "internal"] = "external"


ConstraintEntity = Annotated[
    FixedPointConstraint
    | DistanceConstraint
    | HorizontalDistanceConstraint
    | VerticalDistanceConstraint
    | RadiusConstraint
    | DiameterConstraint
    | AngleConstraint
    | ParallelConstraint
    | PerpendicularConstraint
    | EqualLengthConstraint
    | EqualAngleConstraint
    | HorizontalConstraint
    | VerticalConstraint
    | CoincidentConstraint
    | MidpointConstraint
    | CollinearConstraint
    | SymmetricConstraint
    | ConcentricConstraint
    | TangentConstraint,
    Field(discriminator="type"),
]
