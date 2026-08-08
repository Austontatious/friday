from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field


GeometryCommandVersion = Literal["0.1", "0.2", "0.3"]
GeometryCommandType = Literal[
    "measure_distance",
    "measure_angle",
    "define_point",
    "define_line",
    "define_profile",
    "delete_entity",
    "set_distance",
    "set_rectangle_dimension",
    "set_line_polar",
    "set_angle",
    "make_parallel",
    "make_perpendicular",
    "make_equal_length",
    "make_equal_angle",
    "make_horizontal",
    "make_vertical",
    "make_coincident",
    "solve_constraints",
    "analyze_constraints",
    "move_point",
    "detect_profiles",
    "make_profile",
    "define_circle",
    "update_circle",
    "make_circle_profile",
    "add_profile_hole",
    "update_profile_hole",
    "extrude_profile",
    "translate",
    "rotate",
    "mirror",
    "copy_linear",
    "intersect_lines",
    "project_point_to_line",
    "batch",
]

SUPPORTED_GEOMETRY_COMMAND_VERSIONS = tuple(get_args(GeometryCommandVersion))
SUPPORTED_GEOMETRY_COMMAND_TYPES = tuple(get_args(GeometryCommandType))


class GeometryCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: GeometryCommandVersion = "0.1"
    command_id: str
    mode: Literal["preview", "commit"] = "preview"
    command_type: GeometryCommandType
    selection: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
