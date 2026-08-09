from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.config import SketchMathConfig
from sketchmath.cad.feature_artifact import materialize_feature_artifact
from sketchmath.executor.errors import SketchMathError
from sketchmath.models.artifact_job import (
    ArtifactBuildRequest,
    ArtifactJobError,
    ArtifactJobManifest,
    ArtifactJobResult,
)
from sketchmath.models.document import ArtifactRecord, SketchMathDocument

if TYPE_CHECKING:
    from backend.sketchmath.service import SketchMathSessionStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SketchMathArtifactJobStore:
    def __init__(self, root: str | Path | None = None, *, output_root: str | Path | None = None) -> None:
        self._explicit_root = Path(root) if root is not None else None
        self._explicit_output_root = Path(output_root) if output_root is not None else None
        self._lock = threading.RLock()
        self._active: set[str] = set()

    def _root(self) -> Path:
        root = self._explicit_root or Path(SketchMathConfig.from_env().artifact_job_dir)
        if not root.is_absolute():
            root = Path.cwd() / root
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    def _output_root(self) -> Path:
        root = self._explicit_output_root or Path(SketchMathConfig.from_env().cad_export_dir)
        if not root.is_absolute():
            root = Path.cwd() / root
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    def _job_dir(self, job_id: str) -> Path:
        return self._root() / job_id

    def _manifest_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "manifest.json"

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f"{path.suffix}.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def _write_manifest(self, manifest: ArtifactJobManifest) -> None:
        self._write_json(self._manifest_path(manifest.job_id), manifest.model_dump(mode="json"))

    def _load_manifest(self, job_id: str) -> ArtifactJobManifest | None:
        path = self._manifest_path(job_id)
        if not path.exists():
            return None
        return ArtifactJobManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def submit(
        self,
        session_store: "SketchMathSessionStore",
        session_id: str,
        request: ArtifactBuildRequest,
        *,
        start: bool = True,
    ) -> ArtifactJobManifest:
        document = session_store.artifact_build_snapshot(
            session_id,
            feature_id=request.feature_id,
            base_revision=request.base_revision,
        )
        input_hash = document.last_rebuild.content_hash if document.last_rebuild is not None else _hash_payload(document.model_dump(mode="json"))
        identity = {
            "document_id": document.document_id,
            "feature_id": request.feature_id,
            "format": request.format,
            "input_revision": request.base_revision,
            "input_content_hash": input_hash,
        }
        job_id = f"smjob_{_hash_payload(identity)[:20]}"
        with self._lock:
            existing = self._load_manifest(job_id)
            if existing is not None:
                if start and existing.state in {"READY", "FAILED"}:
                    self.start_background(job_id, session_store)
                return existing
            now = _now_iso()
            manifest = ArtifactJobManifest(
                job_id=job_id,
                document_id=document.document_id,
                session_id=session_id,
                feature_id=request.feature_id,
                format=request.format,
                input_revision=request.base_revision,
                input_content_hash=input_hash,
                created_at=now,
                updated_at=now,
            )
            job_dir = self._job_dir(job_id)
            job_dir.mkdir(parents=True, exist_ok=True)
            self._write_json(
                job_dir / "request.json",
                {
                    "session_id": session_id,
                    "request": request.model_dump(mode="json"),
                    "document": document.model_dump(mode="json"),
                },
            )
            self._write_manifest(manifest)
        if start:
            self.start_background(job_id, session_store)
        return manifest

    def get(self, session_id: str, job_id: str) -> ArtifactJobManifest | None:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest is None or manifest.session_id != session_id:
                return None
            return manifest

    def retry(self, session_id: str, job_id: str, session_store: "SketchMathSessionStore") -> ArtifactJobManifest | None:
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest is None or manifest.session_id != session_id:
                return None
            if manifest.state == "DONE":
                return manifest
            manifest.state = "READY"
            manifest.step = "retry_ready"
            manifest.error = None
            manifest.updated_at = _now_iso()
            self._write_manifest(manifest)
        self.start_background(job_id, session_store)
        return manifest

    def start_background(self, job_id: str, session_store: "SketchMathSessionStore") -> None:
        with self._lock:
            if job_id in self._active:
                return
            self._active.add(job_id)

        def _target() -> None:
            try:
                self.run(job_id, session_store)
            finally:
                with self._lock:
                    self._active.discard(job_id)

        threading.Thread(target=_target, name=f"sketchmath-artifact-{job_id}", daemon=True).start()

    def run(self, job_id: str, session_store: "SketchMathSessionStore") -> ArtifactJobManifest:
        job_dir = self._job_dir(job_id)
        with self._lock:
            manifest = self._load_manifest(job_id)
            if manifest is None:
                raise FileNotFoundError(f"Artifact job does not exist: {job_id}")
            if manifest.state == "DONE":
                return manifest
            manifest.state = "RUNNING"
            manifest.step = "validate"
            manifest.attempt += 1
            manifest.updated_at = _now_iso()
            manifest.error = None
            self._write_manifest(manifest)
        try:
            request_payload = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
            document = SketchMathDocument.model_validate(request_payload["document"])
            request = ArtifactBuildRequest.model_validate(request_payload["request"])
            (job_dir / "validate.done").touch()

            manifest.step = "materialize"
            manifest.updated_at = _now_iso()
            self._write_manifest(manifest)
            materialized_path = job_dir / "materialized.json"
            if (job_dir / "materialize.done").exists() and materialized_path.exists():
                materialized = json.loads(materialized_path.read_text(encoding="utf-8"))
                artifact_path = Path(materialized["path"])
                if not artifact_path.exists() or not artifact_path.is_file():
                    (job_dir / "materialize.done").unlink(missing_ok=True)
                    materialized = materialize_feature_artifact(
                        document,
                        request.feature_id,
                        request.format,
                        output_root=self._output_root(),
                    )
            else:
                materialized = materialize_feature_artifact(
                    document,
                    request.feature_id,
                    request.format,
                    output_root=self._output_root(),
                )
            self._write_json(materialized_path, materialized)
            (job_dir / "materialize.done").touch()

            manifest.step = "register"
            manifest.updated_at = _now_iso()
            self._write_manifest(manifest)
            artifact = ArtifactRecord(
                artifact_id=f"artifact_{_hash_payload({'job_id': job_id, 'content_hash': materialized['content_hash']})[:20]}",
                feature_id=request.feature_id,
                revision=request.base_revision,
                format=request.format,
                path=materialized["path"],
                content_hash=materialized["content_hash"],
                metadata={
                    "job_id": job_id,
                    "size_bytes": materialized["size_bytes"],
                    "input_content_hash": manifest.input_content_hash,
                    "measurements": materialized["measurements"],
                },
            )
            session_store.register_artifact(manifest.session_id, artifact, input_revision=manifest.input_revision)
            (job_dir / "register.done").touch()
            result = ArtifactJobResult(
                artifact=artifact,
                measurements=materialized["measurements"],
                input_revision=manifest.input_revision,
            )
            self._write_json(job_dir / "result.json", result.model_dump(mode="json"))
            manifest.result = result
            manifest.state = "DONE"
            manifest.step = "complete"
            manifest.updated_at = _now_iso()
            self._write_manifest(manifest)
            return manifest
        except Exception as exc:
            if isinstance(exc, SketchMathError):
                error = ArtifactJobError(
                    code=exc.code,
                    message=str(exc),
                    detail=exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail},
                    retryable=exc.retryable,
                )
            else:
                error = ArtifactJobError(
                    code="artifact_job_failed",
                    message=str(exc),
                    detail={"exception_type": type(exc).__name__},
                    retryable=True,
                )
            self._write_json(job_dir / "error.json", error.model_dump(mode="json"))
            manifest.error = error
            manifest.state = "FAILED"
            manifest.step = "failed"
            manifest.updated_at = _now_iso()
            self._write_manifest(manifest)
            return manifest


ARTIFACT_JOB_STORE = SketchMathArtifactJobStore()
