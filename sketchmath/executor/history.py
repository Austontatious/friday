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
    redo_records: list[OperationRecord] = field(default_factory=list)

    @property
    def cursor(self) -> int:
        return len(self.records)

    def append(self, record: OperationRecord) -> None:
        if not record.committed:
            raise ValueError("Only committed operation records can be stored in history")
        self.redo_records.clear()
        self.records.append(record)

    def pop_last(self) -> OperationRecord | None:
        if not self.records:
            return None
        record = self.records.pop()
        self.redo_records.append(record)
        return record

    def redo_next(self) -> OperationRecord | None:
        if not self.redo_records:
            return None
        record = self.redo_records.pop()
        self.records.append(record)
        return record

    def replay(self, base_state: "SelectionContext") -> "SelectionContext":
        from sketchmath.executor.command_router import apply_geometry_command

        state = base_state.model_copy(deep=True)
        for record in self.records:
            state, _, _, _, _ = apply_geometry_command(record.command, state)
        return state
