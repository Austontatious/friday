from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .geometry_command import GeometryCommand
from .selection_context import SelectionContext


class OperationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: GeometryCommand
    status: Literal["preview", "committed"]
    before: SelectionContext
    after: SelectionContext
    changed_entity_ids: list[str] = Field(default_factory=list)
    replay_index: int = 0
    value: float | None = None
    unit: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
