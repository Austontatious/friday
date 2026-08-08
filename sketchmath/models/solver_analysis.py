from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SolverAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    coverage: Literal["exact", "partial", "unknown"]
    freedom_state: Literal["under_constrained", "fully_constrained", "unknown"]
    consistency_state: Literal["consistent", "inconsistent", "unknown"]
    redundancy_state: Literal["none", "redundant", "unknown"]
    tracked_variable_count: int = Field(ge=0)
    independent_equation_count: int = Field(ge=0)
    remaining_dof: int | None = Field(default=None, ge=0)
    remaining_tracked_dof_upper_bound: int = Field(ge=0)
    fixed_entity_ids: list[str] = Field(default_factory=list)
    supported_constraint_ids: list[str] = Field(default_factory=list)
    unsupported_constraint_ids: list[str] = Field(default_factory=list)
    invalid_constraint_ids: list[str] = Field(default_factory=list)
    redundant_constraint_ids: list[str] = Field(default_factory=list)
    conflicting_constraint_ids: list[str] = Field(default_factory=list)
    unmodeled_entity_ids: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    tolerance_policy: dict[str, float | str]
