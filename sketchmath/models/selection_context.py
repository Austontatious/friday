from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .constraints import ConstraintEntity
from .entities import SelectionEntity


class SelectionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_set_id: str
    units: str
    frame: Literal["canvas_2d"] = "canvas_2d"
    items: list[SelectionEntity] = Field(default_factory=list)
    constraints: list[ConstraintEntity] = Field(default_factory=list)
    named_references: dict[str, str] = Field(default_factory=dict)

    def entity_map(self) -> dict[str, SelectionEntity]:
        return {item.id: item for item in self.items}

    def get_entity(self, entity_id: str) -> SelectionEntity:
        entity = self.entity_map().get(entity_id)
        if entity is None:
            from sketchmath.executor.errors import MissingEntityError

            raise MissingEntityError(
                f"Unknown entity id: {entity_id}",
                detail={"entity_id": entity_id},
            )
        return entity

    def replace_entity(self, replacement: SelectionEntity) -> None:
        for index, item in enumerate(self.items):
            if item.id == replacement.id:
                self.items[index] = replacement
                return
        self.items.append(replacement)

    def constraint_map(self) -> dict[str, ConstraintEntity]:
        return {item.id: item for item in self.constraints}

    def get_constraint(self, constraint_id: str) -> ConstraintEntity:
        constraint = self.constraint_map().get(constraint_id)
        if constraint is None:
            from sketchmath.executor.errors import MissingEntityError

            raise MissingEntityError(
                f"Unknown constraint id: {constraint_id}",
                detail={"constraint_id": constraint_id},
            )
        return constraint

    def replace_constraint(self, replacement: ConstraintEntity) -> None:
        for index, item in enumerate(self.constraints):
            if item.id == replacement.id:
                self.constraints[index] = replacement
                return
        self.constraints.append(replacement)
