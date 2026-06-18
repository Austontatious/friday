from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sketchmath.models.geometry_command import GeometryCommand
    from sketchmath.models.selection_context import SelectionContext


@dataclass
class OperationRecord:
    command: "GeometryCommand"
    before: "SelectionContext"
    after: "SelectionContext"
    committed: bool


@dataclass
class GeometryHistory:
    records: list[OperationRecord] = field(default_factory=list)

    def append(self, record: OperationRecord) -> None:
        if not record.committed:
            raise ValueError("Only committed operation records can be stored in history")
        self.records.append(record)

    def pop_last(self) -> OperationRecord | None:
        if not self.records:
            return None
        return self.records.pop()

    def replay(self, base_state: "SelectionContext") -> "SelectionContext":
        from sketchmath.executor.command_router import apply_geometry_command

        state = base_state.model_copy(deep=True)
        for record in self.records:
            state, _, _, _, _ = apply_geometry_command(record.command, state)
        return state
