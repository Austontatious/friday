from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .document import ArtifactRecord


class ArtifactBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    format: Literal["step", "stl"]
    base_revision: int = Field(ge=0)


class ArtifactJobError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False


class ArtifactJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: ArtifactRecord
    measurements: dict[str, Any] = Field(default_factory=dict)
    input_revision: int = Field(ge=0)
    registered: bool = True


class ArtifactJobManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    job_id: str
    document_id: str
    session_id: str
    feature_id: str
    format: Literal["step", "stl"]
    input_revision: int = Field(ge=0)
    input_content_hash: str
    state: Literal["READY", "RUNNING", "DONE", "FAILED"] = "READY"
    attempt: int = Field(default=0, ge=0)
    created_at: str
    updated_at: str
    step: str = "ready"
    error: ArtifactJobError | None = None
    result: ArtifactJobResult | None = None
