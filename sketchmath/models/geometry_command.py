from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GeometryCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "0.1"
    command_id: str
    mode: Literal["preview", "commit"] = "preview"
    command_type: str
    selection: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
