from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from core.config import SketchMathConfig
from sketchmath.executor.command_router import GeometrySession
from sketchmath.executor.errors import (
    CadAdapterUnavailableError,
    CadExportError,
    ClarificationRequiredError,
    CommandValidationError,
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
    FeatureRebuildError,
    RevisionConflictError,
)
from sketchmath.features.executor import apply_feature_command
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import ArtifactRecord, SketchMathDocument, SketchRecord, wrap_legacy_selection_context
from sketchmath.models.feature_command import FeatureCommand
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
    elif entity_type == "circle_2d":
        payload = {
            "version": "0.2",
            "command_id": command_id,
            "mode": mode,
            "command_type": "define_circle",
            "selection": [],
            "parameters": {
                "name": entity["id"],
                "center": entity["center"],
                "radius": entity["radius"],
                "center_point_id": entity.get("center_point_id"),
                "locked": entity.get("locked", False),
                "label": entity.get("label"),
            },
        }
    elif entity_type == "arc_2d":
        payload = {
            "version": "0.5",
            "command_id": command_id,
            "mode": mode,
            "command_type": "define_arc",
            "selection": [],
            "parameters": {
                "name": entity["id"],
                "construction": entity["construction"],
                "center": entity["center"],
                "radius": entity["radius"],
                "start_angle_deg": entity["start_angle_deg"],
                "sweep_angle_deg": entity["sweep_angle_deg"],
                "center_point_id": entity.get("center_point_id"),
                "start_point_id": entity.get("start_point_id"),
                "through_point_id": entity.get("through_point_id"),
                "end_point_id": entity.get("end_point_id"),
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
                "start_point_id": entity.get("start_point_id"),
                "end_point_id": entity.get("end_point_id"),
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
                "source_line_ids": entity.get("source_line_ids", []),
                "source_circle_id": entity.get("source_circle_id"),
            },
        }
    else:
        raise UnsupportedCommandError(
            "Unsupported entity type",
            detail={"entity_type": entity_type, "entity_id": entity.get("id")},
        )
    return _validate_command_payload(payload)


def _validate_command_payload(payload: dict[str, Any]) -> GeometryCommand:
    try:
        return GeometryCommand.model_validate(payload)
    except ValidationError as exc:
        errors = [
            {
                "type": error["type"],
                "location": [str(part) for part in error["loc"]],
                "message": error["msg"],
            }
            for error in exc.errors(include_url=False)
        ]
        raise CommandValidationError(
            "Geometry command failed contract validation",
            detail={"errors": errors},
        ) from exc


def _error_status(exc: SketchMathError) -> int:
    if isinstance(exc, MissingEntityError):
        return 404
    if isinstance(exc, (CommandValidationError, MissingParameterError, WrongEntityTypeError, UnsupportedCommandError, InvalidUnitsError, SelectionResolutionError)):
        return 422
    if isinstance(exc, UnsupportedCadFormatError):
        return 422
    if isinstance(exc, CadAdapterUnavailableError):
        return 503
    if isinstance(exc, CadExportError):
        return 502
    if isinstance(exc, (LockedEntityMutationError, SolverError, ClarificationRequiredError, FeatureRebuildError, RevisionConflictError)):
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
        command=_validate_command_payload(payload["command"]),
        before=SelectionContext.model_validate(payload["before"]),
        after=SelectionContext.model_validate(payload["after"]),
        committed=bool(payload.get("committed", False)),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _FeatureOperationRecord:
    command: FeatureCommand
    before: SketchMathDocument
    after: SketchMathDocument


def _serialize_feature_record(record: _FeatureOperationRecord) -> dict[str, Any]:
    return {
        "command": record.command.model_dump(mode="json"),
        "before": record.before.model_dump(mode="json"),
        "after": record.after.model_dump(mode="json"),
    }


def _feature_record_from_payload(payload: dict[str, Any]) -> _FeatureOperationRecord:
    return _FeatureOperationRecord(
        command=FeatureCommand.model_validate(payload["command"]),
        before=SketchMathDocument.model_validate(payload["before"]),
        after=SketchMathDocument.model_validate(payload["after"]),
    )


@dataclass
class _StoredSession:
    session: GeometrySession
    initial_state: SelectionContext
    metadata: dict[str, Any] = field(default_factory=dict)
    document: SketchMathDocument | None = None
    feature_history: list[_FeatureOperationRecord] = field(default_factory=list)
    feature_redo_history: list[_FeatureOperationRecord] = field(default_factory=list)


@dataclass
class SketchMathSessionStore:
    session_dir: Path | None = None
    _sessions: dict[str, _StoredSession] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _session_locks: dict[str, Lock] = field(default_factory=dict)

    def _session_lock(self, session_id: str) -> Lock:
        with self._lock:
            return self._session_locks.setdefault(session_id, Lock())

    def _root(self) -> Path:
        if self.session_dir is not None:
            root = self.session_dir
        else:
            root = Path(SketchMathConfig.from_env().session_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _session_path(self, session_id: str) -> Path:
        return self._root() / f"{session_id}.json"

    @staticmethod
    def _primary_sketch(document: SketchMathDocument) -> SketchRecord:
        if len(document.sketches) != 1:
            raise CommandValidationError(
                "The compatibility session adapter requires exactly one sketch",
                detail={"document_id": document.document_id, "sketch_count": len(document.sketches)},
            )
        return document.sketches[0]

    def _sync_document_sketch(self, stored: _StoredSession, state: SelectionContext, *, increment_revision: bool) -> None:
        if stored.document is None:
            return
        document = stored.document.model_copy(deep=True)
        primary = self._primary_sketch(document)
        document.sketches[0] = primary.model_copy(update={"state": state.model_copy(deep=True)})
        if increment_revision:
            document.revision += 1
        report = rebuild_document(document)
        if not report.ok:
            raise FeatureRebuildError(
                "Sketch edit would invalidate canonical feature references",
                detail={
                    "document_id": document.document_id,
                    "revision": document.revision,
                    "error_code": "feature_reference_invalidated",
                    "rebuild": report.model_dump(mode="json"),
                },
            )
        document.last_rebuild = report
        stored.document = document

    @staticmethod
    def _restore_feature_state(current: SketchMathDocument, source: SketchMathDocument) -> SketchMathDocument:
        candidate = current.model_copy(deep=True)
        candidate.features = [feature.model_copy(deep=True) for feature in source.features]
        source_feature_ids = {body.body_id: list(body.feature_ids) for body in source.bodies}
        candidate.bodies = [
            body.model_copy(update={"feature_ids": source_feature_ids.get(body.body_id, [])})
            for body in candidate.bodies
        ]
        candidate.revision = current.revision + 1
        report = rebuild_document(candidate)
        if not report.ok:
            raise FeatureRebuildError(
                "Feature history operation is invalid against the current sketch",
                detail={
                    "document_id": current.document_id,
                    "revision": current.revision,
                    "error_code": "feature_history_reference_invalid",
                    "rebuild": report.model_dump(mode="json"),
                },
            )
        candidate.last_rebuild = report
        return candidate

    def _build_snapshot(self, session_id: str, stored: _StoredSession) -> dict[str, Any]:
        session = stored.session
        snapshot = {
            "session_id": session_id,
            "selection_context": session.state.model_dump(mode="json"),
            "session_metadata": {
                **stored.metadata,
                "persisted": True,
                "storage_path": str(self._session_path(session_id)),
            },
            "history_length": session.history.cursor,
            "history": [_serialize_history_record(record) for record in session.history.records],
            "history_cursor": session.history.cursor,
            "can_undo": session.history.cursor > 0,
            "can_redo": bool(session.history.redo_records),
        }
        if stored.document is not None:
            snapshot.update(
                {
                    "document": stored.document.model_dump(mode="json"),
                    "feature_history_length": len(stored.feature_history),
                    "feature_history": [_serialize_feature_record(record) for record in stored.feature_history],
                    "can_feature_undo": bool(stored.feature_history),
                    "can_feature_redo": bool(stored.feature_redo_history),
                }
            )
        return snapshot

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
            "redo_history": [_serialize_history_record(record) for record in stored.session.history.redo_records],
        }
        if stored.document is not None:
            payload.update(
                {
                    "document": stored.document.model_dump(mode="json"),
                    "feature_history": [_serialize_feature_record(record) for record in stored.feature_history],
                    "feature_redo_history": [_serialize_feature_record(record) for record in stored.feature_redo_history],
                }
            )
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
        session.history.redo_records = [_history_record_from_payload(record) for record in payload.get("redo_history", [])]
        session.state = current_state
        metadata = dict(payload.get("session_metadata") or {})
        metadata.setdefault("persisted", True)
        metadata.setdefault("storage_path", str(path))
        document_payload = payload.get("document")
        document = SketchMathDocument.model_validate(document_payload) if isinstance(document_payload, dict) else None
        if document is None and SketchMathConfig.from_env().document_v1_enabled:
            document = wrap_legacy_selection_context(current_state, document_id=f"doc_{session_id}")
            document.last_rebuild = rebuild_document(document)
        return _StoredSession(
            session=session,
            initial_state=initial_state,
            metadata=metadata,
            document=document,
            feature_history=[_feature_record_from_payload(record) for record in payload.get("feature_history", [])],
            feature_redo_history=[_feature_record_from_payload(record) for record in payload.get("feature_redo_history", [])],
        )

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
        session_id = f"sm_{uuid4().hex[:12]}"
        document_payload = payload.get("document") if isinstance(payload, dict) else None
        document: SketchMathDocument | None = None
        if SketchMathConfig.from_env().document_v1_enabled and isinstance(document_payload, dict):
            document = SketchMathDocument.model_validate(document_payload)
            context = self._primary_sketch(document).state.model_copy(deep=True)
        else:
            context = _selection_context_from_payload(payload)
            if SketchMathConfig.from_env().document_v1_enabled:
                document = wrap_legacy_selection_context(context, document_id=f"doc_{session_id}")
                document.last_rebuild = rebuild_document(document)
        session = GeometrySession(context)
        metadata = {
            "persisted": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        stored = _StoredSession(
            session=session,
            initial_state=context.model_copy(deep=True),
            metadata=metadata,
            document=document,
        )
        with self._lock:
            self._sessions[session_id] = stored
        self._save(session_id, stored)
        return session_id, session

    def get_session(self, session_id: str) -> GeometrySession:
        return self._get_stored(session_id).session

    def snapshot(self, session_id: str, session: GeometrySession) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            stored.session = session
            return self._build_snapshot(session_id, stored)

    def run_command(self, session_id: str, command_payload: dict[str, Any], *, mode: str | None = None) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            session = stored.session
            payload = dict(command_payload)
            if mode is not None:
                payload["mode"] = mode
            command = _validate_command_payload(payload)
            state_before = session.state.model_copy(deep=True)
            history_before = list(session.history.records)
            redo_before = list(session.history.redo_records)
            document_before = stored.document.model_copy(deep=True) if stored.document is not None else None
            try:
                result = session.execute(command)
                if command.mode == "commit":
                    self._sync_document_sketch(stored, session.state, increment_revision=True)
                    stored.metadata["updated_at"] = _now_iso()
                    self._save(session_id, stored)
            except Exception:
                session.state = state_before
                session.history.records = history_before
                session.history.redo_records = redo_before
                stored.document = document_before
                raise
            return {**self._build_snapshot(session_id, stored), "result": result.model_dump(mode="json")}

    def run_feature_command(self, session_id: str, command_payload: dict[str, Any], *, mode: str | None = None) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            if stored.document is None:
                raise CommandValidationError(
                    "SketchMath document v1 is not enabled for this session",
                    detail={"session_id": session_id, "error_code": "document_v1_disabled"},
                )
            payload = dict(command_payload)
            if mode is not None:
                payload["mode"] = mode
            try:
                command = FeatureCommand.model_validate(payload)
            except ValidationError as exc:
                raise CommandValidationError(
                    "Feature command failed schema validation",
                    detail={"errors": exc.errors(include_url=False)},
                ) from exc
            result = apply_feature_command(stored.document, command)
            if command.mode == "commit":
                stored.document = result.after.model_copy(deep=True)
                stored.feature_history.append(
                    _FeatureOperationRecord(
                        command=command,
                        before=result.before.model_copy(deep=True),
                        after=result.after.model_copy(deep=True),
                    )
                )
                stored.feature_redo_history.clear()
                stored.metadata["updated_at"] = _now_iso()
                self._save(session_id, stored)
            return {
                **self._build_snapshot(session_id, stored),
                "result": result.model_dump(mode="json"),
            }

    def artifact_build_snapshot(self, session_id: str, *, feature_id: str, base_revision: int) -> SketchMathDocument:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            document = stored.document
            if document is None:
                raise CommandValidationError("SketchMath document v1 is not enabled for this session")
            if document.revision != base_revision:
                raise RevisionConflictError(
                    "Artifact request targets a stale document revision",
                    detail={
                        "document_id": document.document_id,
                        "feature_id": feature_id,
                        "base_revision": base_revision,
                        "current_revision": document.revision,
                    },
                )
            if not any(feature.feature_id == feature_id for feature in document.features):
                raise MissingEntityError("Feature does not exist", detail={"feature_id": feature_id})
            return document.model_copy(deep=True)

    def register_artifact(self, session_id: str, artifact: ArtifactRecord, *, input_revision: int) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            document = stored.document
            if document is None:
                raise CommandValidationError("SketchMath document v1 is not enabled for this session")
            if document.revision != input_revision:
                raise RevisionConflictError(
                    "Artifact result is stale and cannot be registered",
                    detail={
                        "document_id": document.document_id,
                        "artifact_id": artifact.artifact_id,
                        "input_revision": input_revision,
                        "current_revision": document.revision,
                    },
                )
            candidate = document.model_copy(deep=True)
            candidate.artifacts = [item for item in candidate.artifacts if item.artifact_id != artifact.artifact_id]
            candidate.artifacts.append(artifact.model_copy(deep=True))
            stored.document = candidate
            stored.metadata["updated_at"] = _now_iso()
            self._save(session_id, stored)
            return self._build_snapshot(session_id, stored)

    def run_entity(self, session_id: str, entity_payload: dict[str, Any], *, mode: str = "commit") -> dict[str, Any]:
        command = _command_from_entity(entity_payload, command_id=f"{session_id}_{entity_payload.get('id', 'entity')}", mode=mode)
        return self.run_command(session_id, command.model_dump(mode="json"))

    def translate(self, session_id: str, utterance: str, selection_context: SelectionContext | None = None) -> dict[str, Any]:
        from sketchmath.translator.translator_service import translate_utterance

        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            context = selection_context or stored.session.state.model_copy(deep=True)
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
        with self._session_lock(session_id):
            session = stored.session
            state_before = session.state.model_copy(deep=True)
            history_before = list(session.history.records)
            redo_before = list(session.history.redo_records)
            document_before = stored.document.model_copy(deep=True) if stored.document is not None else None
            try:
                session.revert()
                self._sync_document_sketch(stored, session.state, increment_revision=True)
            except Exception:
                session.state = state_before
                session.history.records = history_before
                session.history.redo_records = redo_before
                stored.document = document_before
                raise
            stored.metadata["updated_at"] = _now_iso()
            self._save(session_id, stored)
            return self._build_snapshot(session_id, stored)

    def redo(self, session_id: str) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            session = stored.session
            state_before = session.state.model_copy(deep=True)
            history_before = list(session.history.records)
            redo_before = list(session.history.redo_records)
            document_before = stored.document.model_copy(deep=True) if stored.document is not None else None
            try:
                session.redo()
                self._sync_document_sketch(stored, session.state, increment_revision=True)
            except Exception:
                session.state = state_before
                session.history.records = history_before
                session.history.redo_records = redo_before
                stored.document = document_before
                raise
            stored.metadata["updated_at"] = _now_iso()
            self._save(session_id, stored)
            return self._build_snapshot(session_id, stored)

    def revert_feature(self, session_id: str) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            if stored.document is None:
                raise CommandValidationError("SketchMath document v1 is not enabled for this session")
            if not stored.feature_history:
                return self._build_snapshot(session_id, stored)
            record = stored.feature_history[-1]
            restored = self._restore_feature_state(stored.document, record.before)
            stored.feature_history.pop()
            stored.feature_redo_history.append(record)
            stored.document = restored
            stored.metadata["updated_at"] = _now_iso()
            self._save(session_id, stored)
            return self._build_snapshot(session_id, stored)

    def redo_feature(self, session_id: str) -> dict[str, Any]:
        stored = self._get_stored(session_id)
        with self._session_lock(session_id):
            if stored.document is None:
                raise CommandValidationError("SketchMath document v1 is not enabled for this session")
            if not stored.feature_redo_history:
                return self._build_snapshot(session_id, stored)
            record = stored.feature_redo_history[-1]
            restored = self._restore_feature_state(stored.document, record.after)
            stored.feature_redo_history.pop()
            stored.document = restored
            stored.feature_history.append(record)
            stored.metadata["updated_at"] = _now_iso()
            self._save(session_id, stored)
            return self._build_snapshot(session_id, stored)


SESSION_STORE = SketchMathSessionStore()
