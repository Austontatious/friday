from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .solver_analysis import SolverAnalysis


class SolverCoordinatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    entity_type: str
    before: dict[str, object]
    after: dict[str, object]


class SolverRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.1"] = "1.1"
    backend: str
    mode: Literal["analyze", "solve"]
    outcome: Literal["analyzed", "solved", "under_constrained", "inconsistent", "redundant", "failed"]
    termination_reason: str
    requested_constraint_ids: list[str] = Field(default_factory=list)
    changed_entity_ids: list[str] = Field(default_factory=list)
    proposed_patch: list[SolverCoordinatePatch] = Field(default_factory=list)
    feasible: bool | None = None
    residual_norm: float | None = Field(default=None, ge=0)
    max_abs_residual: float | None = Field(default=None, ge=0)
    residual_count: int | None = Field(default=None, ge=0)
    variable_order: list[str] = Field(default_factory=list)
    jacobian_strategy: str | None = None
    jacobian_rank: int | None = Field(default=None, ge=0)
    function_evaluations: int | None = Field(default=None, ge=0)
    jacobian_evaluations: int | None = Field(default=None, ge=0)
    seed_count: int | None = Field(default=None, ge=1)
    characteristic_length_mm: float | None = Field(default=None, gt=0)
    optimizer_terminated_successfully: bool | None = None
    analysis_before: SolverAnalysis
    analysis_after: SolverAnalysis
    diagnostics: list[str] = Field(default_factory=list)
