from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CadExportArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_path: str
    validation_json: str
    preview_path: str | None = None


class CadExportMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bbox: dict[str, float | None] = Field(default_factory=dict)
    volume_mm3: float | None = None
    area_mm2: float | None = None
    is_valid_solid: bool | None = None


class CadExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["export_ready", "validation_failed", "adapter_unavailable", "export_failed"]
    profile_id: str
    command_id: str
    command_type: Literal["extrude_profile", "fillet_feature_graph"] = "extrude_profile"
    artifacts: CadExportArtifacts | None = None
    measurements: CadExportMeasurements | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
