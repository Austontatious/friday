from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
from typing import Any

from core.config import SketchMathConfig
from sketchmath.executor.errors import CadAdapterUnavailableError, CadExportError, InvalidUnitsError, UnsupportedCadFormatError
from sketchmath.models.cad_export import CadExportResult
from sketchmath.models.entities import Profile2DEntity


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_mm_unit(unit: str) -> bool:
    normalized = unit.strip().lower()
    return normalized in {"mm", "millimeter", "millimeters"}


@dataclass(frozen=True)
class CadAdapter:
    freecad_cmd: str | None = None
    export_dir: str | Path | None = None
    timeout_seconds: float | None = None
    worker_script: str | Path | None = None
    feature_worker_script: str | Path | None = None

    @classmethod
    def from_env(cls) -> "CadAdapter":
        config = SketchMathConfig.from_env()
        return cls(
            freecad_cmd=config.freecad_cmd or None,
            export_dir=config.cad_export_dir,
            timeout_seconds=config.cad_timeout_seconds,
        )

    def _resolve_freecad_cmd(self) -> Path:
        if self.freecad_cmd:
            explicit = Path(self.freecad_cmd)
            if explicit.exists():
                return explicit
            resolved = shutil.which(self.freecad_cmd)
            if resolved:
                return Path(resolved)
            raise CadAdapterUnavailableError(
                "FreeCADCmd path from configuration is not available",
                detail={"freecad_cmd": self.freecad_cmd},
            )
        resolved = shutil.which("freecadcmd")
        if resolved:
            return Path(resolved)
        for path in (
            Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd"),
            Path("/mnt/data/freecad/FreeCADCmd"),
            Path("/usr/bin/freecadcmd"),
        ):
            if path.exists():
                return path
        raise CadAdapterUnavailableError(
            "FreeCADCmd is not available",
            detail={
                "candidates": [
                    "freecadcmd",
                    "/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd",
                    "/mnt/data/freecad/FreeCADCmd",
                    "/usr/bin/freecadcmd",
                ]
            },
        )

    def _resolve_export_dir(self, selection_set_id: str, command_id: str) -> Path:
        base = Path(self.export_dir or SketchMathConfig.from_env().cad_export_dir)
        if not base.is_absolute():
            base = _repo_root() / base
        return base / selection_set_id / command_id

    def _worker_script(self) -> Path:
        if self.worker_script is not None:
            path = Path(self.worker_script)
            if path.exists():
                return path
        path = _repo_root() / "sketchmath" / "cad" / "freecad_extrude_profile.py"
        if not path.exists():
            raise CadAdapterUnavailableError(
                "FreeCAD worker script is missing",
                detail={"worker_script": str(path)},
            )
        return path

    def _feature_worker_script(self) -> Path:
        if self.feature_worker_script is not None:
            path = Path(self.feature_worker_script)
            if path.exists():
                return path
        path = _repo_root() / "sketchmath" / "cad" / "freecad_feature_graph.py"
        if not path.exists():
            raise CadAdapterUnavailableError(
                "FreeCAD feature-graph worker script is missing",
                detail={"worker_script": str(path)},
            )
        return path

    def extrude_profile(
        self,
        profile: Profile2DEntity,
        *,
        holes: list[Profile2DEntity] | None = None,
        depth: float,
        depth_unit: str = "mm",
        direction: str = "positive_normal",
        output_format: str = "step",
        selection_set_id: str,
        command_id: str,
    ) -> CadExportResult:
        if output_format.strip().lower() != "step":
            raise UnsupportedCadFormatError(
                "Only STEP export is supported in this slice",
                detail={"output_format": output_format},
            )
        if not _is_mm_unit(depth_unit):
            raise InvalidUnitsError(
                "Extrusion depth unit must be mm in this slice",
                detail={"unit": depth_unit},
            )
        if not profile.closed:
            raise CadExportError(
                "Closed profile required for extrusion",
                detail={"profile_id": profile.id},
            )

        export_dir = self._resolve_export_dir(selection_set_id, command_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        input_path = export_dir / "input.json"
        payload = {
            "profile": profile.model_dump(mode="json"),
            "holes": [hole.model_dump(mode="json") for hole in holes or []],
            "depth_mm": float(depth),
            "depth_unit": depth_unit,
            "direction": direction,
            "output_format": output_format,
            "selection_set_id": selection_set_id,
            "command_id": command_id,
        }
        input_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        freecad_cmd = self._resolve_freecad_cmd()
        worker_script = self._worker_script()
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        bootstrap_code = (
            "import runpy, sys; "
            f"sys.path.insert(0, {str(_repo_root())!r}); "
            f"sys.argv = [{str(worker_script)!r}, '--input-json', {str(input_path)!r}, '--out-dir', {str(export_dir)!r}]; "
            f"runpy.run_path({str(worker_script)!r}, run_name='__main__')"
        )
        completed = subprocess.run(
            [str(freecad_cmd), "-c", bootstrap_code],
            cwd=str(_repo_root()),
            env=env,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds or SketchMathConfig.from_env().cad_timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            partial_step = export_dir / "export.step"
            if partial_step.exists() and partial_step.is_file():
                partial_step.unlink()
            raise CadExportError(
                "FreeCAD extrusion worker failed",
                detail={
                    "returncode": completed.returncode,
                    "stderr": completed.stderr.strip(),
                    "stdout": completed.stdout.strip(),
                    "freecad_cmd": str(freecad_cmd),
                    "worker_script": str(worker_script),
                },
            )

        validation_path = export_dir / "validation.json"
        if not validation_path.exists():
            raise CadExportError(
                "FreeCAD worker did not produce validation output",
                detail={"validation_json": str(validation_path)},
            )
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        result = CadExportResult.model_validate(payload)
        step_path = Path(result.artifacts.step_path) if result.artifacts else export_dir / "export.step"
        step_stat = step_path.stat() if step_path.exists() else None
        result.metadata.update(
            {
                "freecad_cmd": str(freecad_cmd),
                "worker_script": str(worker_script),
                "input_json": str(input_path),
                "out_dir": str(export_dir),
                "returncode": completed.returncode,
                "artifact_filename": step_path.name,
                "artifact_size_bytes": step_stat.st_size if step_stat else None,
                "artifact_created_at": datetime.fromtimestamp(step_stat.st_mtime, timezone.utc).isoformat() if step_stat else None,
                "profile_id": profile.id,
                "extrusion_depth": depth,
                "extrusion_depth_unit": depth_unit,
            }
        )
        return result

    def feature_graph(
        self,
        payload: dict[str, Any],
        *,
        selection_set_id: str,
        command_id: str,
    ) -> CadExportResult:
        export_dir = self._resolve_export_dir(selection_set_id, command_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        input_path = export_dir / "input.json"
        worker_payload = {
            **payload,
            "selection_set_id": selection_set_id,
            "command_id": command_id,
            "output_format": "step",
        }
        input_path.write_text(json.dumps(worker_payload, indent=2, sort_keys=True), encoding="utf-8")

        freecad_cmd = self._resolve_freecad_cmd()
        worker_script = self._feature_worker_script()
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        bootstrap_code = (
            "import runpy, sys; "
            f"sys.path.insert(0, {str(_repo_root())!r}); "
            f"sys.argv = [{str(worker_script)!r}, '--input-json', {str(input_path)!r}, '--out-dir', {str(export_dir)!r}]; "
            f"runpy.run_path({str(worker_script)!r}, run_name='__main__')"
        )
        completed = subprocess.run(
            [str(freecad_cmd), "-c", bootstrap_code],
            cwd=str(_repo_root()),
            env=env,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds or SketchMathConfig.from_env().cad_timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            partial_step = export_dir / "export.step"
            if partial_step.exists() and partial_step.is_file():
                partial_step.unlink()
            raise CadExportError(
                "FreeCAD feature-graph worker failed",
                detail={
                    "returncode": completed.returncode,
                    "stderr": completed.stderr.strip(),
                    "stdout": completed.stdout.strip(),
                    "freecad_cmd": str(freecad_cmd),
                    "worker_script": str(worker_script),
                },
            )

        validation_path = export_dir / "validation.json"
        if not validation_path.exists():
            raise CadExportError(
                "FreeCAD feature-graph worker did not produce validation output",
                detail={"validation_json": str(validation_path)},
            )
        result = CadExportResult.model_validate_json(validation_path.read_text(encoding="utf-8"))
        step_path = Path(result.artifacts.step_path) if result.artifacts else export_dir / "export.step"
        step_stat = step_path.stat() if step_path.exists() else None
        result.metadata.update(
            {
                "freecad_cmd": str(freecad_cmd),
                "worker_script": str(worker_script),
                "input_json": str(input_path),
                "out_dir": str(export_dir),
                "returncode": completed.returncode,
                "artifact_filename": step_path.name,
                "artifact_size_bytes": step_stat.st_size if step_stat else None,
                "artifact_created_at": datetime.fromtimestamp(step_stat.st_mtime, timezone.utc).isoformat() if step_stat else None,
            }
        )
        return result

    def edge_finish_feature_graph(
        self,
        payload: dict[str, Any],
        *,
        selection_set_id: str,
        command_id: str,
    ) -> CadExportResult:
        return self.feature_graph(
            payload,
            selection_set_id=selection_set_id,
            command_id=command_id,
        )
