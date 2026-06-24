from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core.config import SketchMathConfig
from backend.sketchmath.service import SESSION_STORE, SketchMathSessionStore, _error_status
from sketchmath.executor.errors import SketchMathError
from sketchmath.models.selection_context import SelectionContext

router = APIRouter(tags=["sketchmath"])


def _error_payload(code: str, message: str, detail: Any = None, retryable: bool = False) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "retryable": retryable,
        }
    }


def _raise_http(exc: SketchMathError) -> None:
    raise HTTPException(
        status_code=_error_status(exc),
        detail=_error_payload(exc.code, str(exc), exc.detail, exc.retryable),
    ) from exc


def _store() -> SketchMathSessionStore:
    return SESSION_STORE


def _enabled() -> bool:
    return SketchMathConfig.from_env().enabled


def _require_enabled() -> None:
    if not _enabled():
        raise HTTPException(
            status_code=503,
            detail=_error_payload(
                "sketchmath_disabled",
                "SketchMath is disabled",
                "Set FRIDAY_SKETCHMATH_ENABLED=1",
                False,
            ),
        )


def _cad_export_root() -> Path:
    root = Path(SketchMathConfig.from_env().cad_export_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _resolve_step_artifact(path: str) -> Path:
    requested = Path(path)
    if not requested.is_absolute():
        requested = _cad_export_root() / requested
    resolved = requested.resolve()
    root = _cad_export_root()
    if resolved.suffix.lower() not in {".step", ".stp"}:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("artifact_not_step", "Only STEP artifacts can be downloaded", {"path": path}, False),
        )
    if root != resolved and root not in resolved.parents:
        raise HTTPException(
            status_code=403,
            detail=_error_payload("artifact_outside_export_root", "Artifact path is outside the SketchMath export root", {"path": path}, False),
        )
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(
            status_code=404,
            detail=_error_payload("artifact_not_found", "STEP artifact was not found", {"path": path}, False),
        )
    return resolved


@router.post("/sketchmath/sessions", summary="Create a SketchMath session")
def create_session(payload: Dict[str, Any] | None = None):
    _require_enabled()
    session_id, session = _store().create_session(payload)
    return _store().snapshot(session_id, session)


@router.get("/sketchmath/artifacts/step", summary="Download a SketchMath STEP artifact")
def download_step_artifact(path: str = Query(..., min_length=1)):
    _require_enabled()
    artifact = _resolve_step_artifact(path)
    return FileResponse(
        artifact,
        media_type="model/step",
        filename=artifact.name,
    )


@router.get("/sketchmath/sessions/{session_id}", summary="Get a SketchMath session")
def get_session(session_id: str):
    _require_enabled()
    try:
        session = _store().get_session(session_id)
    except SketchMathError as exc:
        _raise_http(exc)
    return _store().snapshot(session_id, session)


@router.get("/sketchmath/sessions/{session_id}/history", summary="Get session history")
def get_session_history(session_id: str):
    _require_enabled()
    try:
        session = _store().get_session(session_id)
    except SketchMathError as exc:
        _raise_http(exc)
    snapshot = _store().snapshot(session_id, session)
    return {"session_id": session_id, "history": snapshot["history"], "history_length": snapshot["history_length"]}


@router.post("/sketchmath/sessions/{session_id}/commands/preview", summary="Preview a SketchMath command")
def preview_command(session_id: str, payload: Dict[str, Any]):
    _require_enabled()
    command = payload.get("command") if isinstance(payload, dict) else None
    if not isinstance(command, dict):
        raise HTTPException(
            status_code=400,
            detail=_error_payload("bad_request", "Missing command", "Provide a 'command' object", False),
        )
    try:
        return _store().run_command(session_id, command, mode="preview")
    except SketchMathError as exc:
        _raise_http(exc)


@router.post("/sketchmath/sessions/{session_id}/commands/commit", summary="Commit a SketchMath command")
def commit_command(session_id: str, payload: Dict[str, Any]):
    _require_enabled()
    command = payload.get("command") if isinstance(payload, dict) else None
    if not isinstance(command, dict):
        raise HTTPException(
            status_code=400,
            detail=_error_payload("bad_request", "Missing command", "Provide a 'command' object", False),
        )
    try:
        return _store().run_command(session_id, command, mode="commit")
    except SketchMathError as exc:
        _raise_http(exc)


@router.post("/sketchmath/sessions/{session_id}/entities", summary="Create or replace a SketchMath entity")
def upsert_entity(session_id: str, payload: Dict[str, Any]):
    _require_enabled()
    entity = payload.get("entity") if isinstance(payload, dict) else None
    if not isinstance(entity, dict):
        raise HTTPException(
            status_code=400,
            detail=_error_payload("bad_request", "Missing entity", "Provide an 'entity' object", False),
        )
    try:
        mode = str(payload.get("mode") or "commit").strip().lower()
        if mode not in {"preview", "commit"}:
            mode = "commit"
        return _store().run_entity(session_id, entity, mode=mode)
    except SketchMathError as exc:
        _raise_http(exc)


@router.post("/sketchmath/sessions/{session_id}/revert", summary="Revert the last committed SketchMath operation")
def revert(session_id: str):
    _require_enabled()
    try:
        return _store().revert(session_id)
    except SketchMathError as exc:
        _raise_http(exc)


@router.post("/sketchmath/sessions/{session_id}/translate", summary="Translate a SketchMath utterance into a typed command")
def translate_utterance(session_id: str, payload: Dict[str, Any]):
    _require_enabled()
    utterance = str(payload.get("utterance") or "").strip()
    if not utterance:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("bad_request", "Missing utterance", "Provide an 'utterance' string", False),
        )
    selection_context = None
    if isinstance(payload.get("selection_context"), dict):
        selection_context = SelectionContext.model_validate(payload["selection_context"])
    try:
        stored = _store().get_session(session_id)
    except SketchMathError as exc:
        _raise_http(exc)
    try:
        return _store().translate(session_id, utterance, selection_context=selection_context or stored.state)
    except SketchMathError as exc:
        _raise_http(exc)
