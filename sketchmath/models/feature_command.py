from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .document import FeatureRebuildReport, SketchMathDocument


class FeatureCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    operation_id: str
    mode: Literal["preview", "commit"] = "preview"
    base_revision: int = Field(ge=0)
    operation_type: Literal["add_feature", "replace_feature", "delete_feature", "set_feature_suppressed", "rebuild"]
    target_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class FeatureOperationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: FeatureCommand
    status: Literal["preview", "committed"]
    before: SketchMathDocument
    after: SketchMathDocument
    changed_feature_ids: list[str] = Field(default_factory=list)
    rebuild: FeatureRebuildReport
