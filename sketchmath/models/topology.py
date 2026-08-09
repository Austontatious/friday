from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TopologyDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    curve_ids: list[str] = Field(default_factory=list)
    point: tuple[float, float] | None = None
    detail: dict[str, object] = Field(default_factory=dict)


class PlanarLoop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loop_id: str
    vertices: list[tuple[float, float]]
    winding: Literal["clockwise", "counterclockwise"]
    area: float
    source_curve_ids: list[str] = Field(default_factory=list)


class PlanarRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_id: str
    outer_loop: PlanarLoop
    holes: list[PlanarLoop] = Field(default_factory=list)
    area: float
    centroid: tuple[float, float]
    bounds: tuple[float, float, float, float]
    source_curve_ids: list[str] = Field(default_factory=list)
    nesting_depth: int = 0


class RegionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_requested", "selected", "none", "boundary", "ambiguous"] = "not_requested"
    point: tuple[float, float] | None = None
    region_ids: list[str] = Field(default_factory=list)
    boundary_region_ids: list[str] = Field(default_factory=list)


class PlanarTopologyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    regions: list[PlanarRegion] = Field(default_factory=list)
    diagnostics: list[TopologyDiagnostic] = Field(default_factory=list)
    selection: RegionSelection = Field(default_factory=RegionSelection)
    source_curve_ids: list[str] = Field(default_factory=list)
    approximation: dict[str, object] = Field(default_factory=dict)
