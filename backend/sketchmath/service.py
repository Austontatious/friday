from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from core.config import SketchMathConfig
from sketchmath.executor.command_router import GeometrySession
from sketchmath.executor.errors import (
    CadAdapterUnavailableError,
    CadExportError,
    ClarificationRequiredError,
    InvalidUnitsError,
    LockedEntityMutationError,
    MissingEntityError,
    MissingParameterError,
    SelectionResolutionError,
    SolverError,
    SketchMathError,
    UnsupportedCommandError,
    UnsupportedCadFormatError,
    WrongEntityTypeError,
)
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.operation_result import OperationResult
from sketchmath.models.selection_context import SelectionContext


def default_selection_context(selection_set_id: str | None = None) -> SelectionContext:
    return SelectionContext.model_validate(
        {
            "selection_set_id": selection_set_id or f"sketchmath_{uuid4().hex[:10]}",
            "units": "mm",
            "frame": "canvas_2d",
            "items": [],
            "constraints": [],
            "named_references": {},
        }
    )


def _selection_context_from_payload(payload: dict[str, Any] | None) -> SelectionContext:
    if not payload:
        return default_selection_context()
    if "selection_context" in payload and isinstance(payload["selection_context"], dict):
        return SelectionContext.model_validate(payload["selection_context"])
    return SelectionContext.model_validate(payload)


def _command_from_entity(entity: dict[str, Any], *, command_id: str, mode: str) -> GeometryCommand:
    entity_type = str(entity.get("type") or "").strip()
    if entity_type == "point_2d":
        payload = {
            "version": "0.1",
            "command_id": command_id,
            "mode": mode,
            "command_type": "define_point",
            "selection": [],
            "parameters": {
                "name": entity["id"],
                "coords": entity["coords"],
                "locked": entity.get("locked", False),
                "label": entity.get("label"),
            },
        }
    elif entity_type in {"line_2d", "construction_line_2d"}:
        payload = {
            "version": "0.1",
            "command_id": command_id,
            "mode": mode,
            "command_type": "define_line",
            "selection": [],
            "parameters": {
                "name": entity["id"],
                "start": entity["start"],
                "end": entity["end"],
                "locked": entity.get("locked", False),
                "label": entity.get("label"),
            },
        }
    elif entity_type == "profile_2d":
        payload = {
            "version": "0.1",
            "command_id": command_id,
            "mode": mode,
            "command_type": "define_profile",
            "selection": [],
            "parameters": {
                "name": entity["id"],
                "vertices": entity["vertices"],
                "area": entity["area"],
                "winding": entity["winding"],
                "warnings": entity.get("warnings", []),
                "closed": entity.get("closed", True),
                "locked": entity.get("locked", False),
                "label": entity.get("label"),
            },
        }
    else:
        raise UnsupportedCommandError(
            "Unsupported entity type",
            detail={"entity_type": entity_type, "entity_id": entity.get("id")},
        )
    return GeometryCommand.model_validate(payload)


def _error_status(exc: SketchMathError) -> int:
    if isinstance(exc, MissingEntityError):
        return 404
    if isinstance(exc, (MissingParameterError, WrongEntityTypeError, UnsupportedCommandError, InvalidUnitsError, SelectionResolutionError)):
        return 422
    if isinstance(exc, UnsupportedCadFormatError):
        return 422
    if isinstance(exc, CadAdapterUnavailableError):
        return 503
    if isinstance(exc, CadExportError):
        return 502
    if isinstance(exc, (LockedEntityMutationError, SolverError, ClarificationRequiredError)):
        return 409
    return 400


def _serialize_history_record(record) -> dict[str, Any]:  # noqa: ANN001
    return {
        "command": record.command.model_dump(mode="json"),
        "committed": record.committed,
        "before": record.before.model_dump(mode="json"),
        "after": record.after.model_dump(mode="json"),
    }


def _history_record_from_payload(payload: dict[str, Any]):  # noqa: ANN001
    from sketchmath.executor.history import OperationRecord

    return OperationRecord(
        command=GeometryCommand.model_validate(payload["command"]),
        before=SelectionContext.model_validate(payload["before"]),
        after=SelectionContext.model_validate(payload["after"]),
        committed=bool(payload.get("committed", False)),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _StoredSession:
    session: GeometrySession
    initial_state: SelectionContext
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SketchMathSessionStore:
    session_dir: Path | None = None
    _sessions: dict[str, _StoredSession] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def _root(self) -> Path:
        if self.session_dir is not None:
            root = self.session_dir
        else:
            root = Path(SketchMathConfig.from_env().session_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _session_path(self, session_id: str) -> Path:
        return self._root() / f"{session_id}.json"

    def _build_snapshot(self, session_id: str, stored: _StoredSession) -> dict[str, Any]:
        session = stored.session
        return {
            "session_id": session_id,
            "selection_context": session.state.model_dump(mode="json"),
            "session_metadata": {
                **stored.metadata,
                "persisted": True,
                "storage_path": str(self._session_path(session_id)),
            },
            "history_length": len(session.history.records),
            "history": [_serialize_history_record(record) for record in session.history.records],
        }

    def _save(self, session_id: str, stored: _StoredSession) -> None:
        payload = {
            "session_id": session_id,
            "initial_selection_context": stored.initial_state.model_dump(mode="json"),
            "selection_context": stored.session.state.model_dump(mode="json"),
            "session_metadata": {
                **stored.metadata,
                "persisted": True,
                "updated_at": _now_iso(),
            },
            "history": [_serialize_history_record(record) for record in stored.session.history.records],
        }
        path = self._session_path(session_id)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def _load(self, session_id: str) -> _StoredSession:
        path = self._session_path(session_id)
        if not path.exists():
            raise MissingEntityError("SketchMath session not found", detail={"session_id": session_id})
        payload = json.loads(path.read_text(encoding="utf-8"))
        initial_state = SelectionContext.model_validate(payload["initial_selection_context"])
        current_state = SelectionContext.model_validate(payload["selection_context"])
        session = GeometrySession(initial_state)
        history_records = [_history_record_from_payload(record) for record in payload.get("history", [])]
        session.history.records = history_records
        session.state = current_state
        metadata = dict(payload.get("session_metadata") or {})
        metadata.setdefault("persisted", True)
        metadata.setdefault("storage_path", str(path))
        return _StoredSession(session=session, initial_state=initial_state, metadata=metadata)

    def _get_stored(self, session_id: str) -> _StoredSession:
        with self._lock:
            stored = self._sessions.get(session_id)
        if stored is not None:
            return stored
        stored = self._load(session_id)
        with self._lock:
            self._sessions[session_id] = stored
        return stored

    def create_session(self, payload: dict[str, Any] | None = None) -> tuple[str, GeometrySession]:
        context = _selection_context_from_payload(payload)
        session_id = f"sm_{uuid4().hex[:12]}"
        session = GeometrySession(context)
        metadata = {
            "persisted": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        stored = _StoredSession(session=session, initial_state=context.model_copy(deep=True), metadata=metadata)
        with self._lock:
            self._sessions[session_id] = stored
        self._save(session_id, stored)
        return session_id, session

    def get_session(self, session_id: str) -> GeometrySession:
        return self._get_stored(session_id).session

    def snapshot(self, session_id: str, session: GeometrySession) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        stored.session = session
        return self._build_snapshot(session_id, stored)

    def run_command(self, session_id: str, command_payload: dict[str, Any], *, mode: str | None = None) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        session = stored.session
        payload = dict(command_payload)
        if mode is not None:
            payload["mode"] = mode
        command = GeometryCommand.model_validate(payload)
        result = session.execute(command)
        if command.mode == "commit":
            stored.metadata["updated_at"] = _now_iso()
            self._save(session_id, stored)
        return {
            "session_id": session_id,
            "selection_context": session.state.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
            "history_length": len(session.history.records),
            "session_metadata": {
                **stored.metadata,
                "persisted": True,
                "storage_path": str(self._session_path(session_id)),
            },
        }

    def run_entity(self, session_id: str, entity_payload: dict[str, Any], *, mode: str = "commit") -> dict[str, Any]:
        command = _command_from_entity(entity_payload, command_id=f"{session_id}_{entity_payload.get('id', 'entity')}", mode=mode)
        return self.run_command(session_id, command.model_dump(mode="json"))

    def translate(self, session_id: str, utterance: str, selection_context: SelectionContext | None = None) -> dict[str, Any]:
        from sketchmath.translator.translator_service import translate_utterance

        stored = self._get_stored(session_id)
        context = selection_context or stored.session.state
        outcome = translate_utterance(utterance, context)
        payload: dict[str, Any] = {
            "session_id": session_id,
            "utterance": utterance,
            "selection_context": context.model_dump(mode="json"),
            "status": outcome.status,
            "reason": outcome.reason,
            "options": outcome.options,
            "metadata": outcome.metadata,
        }
        if outcome.command is not None:
            payload["command"] = outcome.command.model_dump(mode="json")
        return payload

    def revert(self, session_id: str) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        session = stored.session
        session.revert()
        stored.metadata["updated_at"] = _now_iso()
        self._save(session_id, stored)
        return self._build_snapshot(session_id, stored)


SESSION_STORE = SketchMathSessionStore()
