from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from backend.sketchmath.artifact_jobs import SketchMathArtifactJobStore
from backend.sketchmath.service import SketchMathSessionStore
from sketchmath.models.artifact_job import ArtifactBuildRequest


def _selection() -> dict[str, object]:
    return {
        "selection_set_id": "artifact_job",
        "units": "mm",
        "frame": "canvas_2d",
        "items": [
            {
                "id": "plate_hole",
                "type": "profile_2d",
                "vertices": [[3, 3], [3, 7], [7, 7], [7, 3], [3, 3]],
                "area": 16,
                "winding": "clockwise",
            },
            {
                "id": "plate",
                "type": "profile_2d",
                "vertices": [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                "area": 100,
                "winding": "counterclockwise",
                "holes": ["plate_hole"],
            },
        ],
        "constraints": [],
        "named_references": {},
    }


def _feature_command(revision: int = 0) -> dict[str, object]:
    return {
        "version": "1.0",
        "operation_id": "add_artifact_feature",
        "mode": "commit",
        "base_revision": revision,
        "operation_type": "add_feature",
        "parameters": {
            "feature": {
                "feature_id": "feature_plate",
                "name": "Golden plate",
                "body_id": "body_main",
                "sketch_id": "sketch_main",
                "profile_id": "plate",
                "parameters": {"depth_mm": 10, "operation": "new_body"},
            }
        },
    }


def _configured_store(monkeypatch, tmp_path) -> tuple[SketchMathSessionStore, str]:  # noqa: ANN001
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    session_store = SketchMathSessionStore(session_dir=tmp_path / "sessions")
    session_id, _ = session_store.create_session({"selection_context": _selection()})
    response = session_store.run_feature_command(session_id, _feature_command(), mode="commit")
    assert response["document"]["revision"] == 1
    return session_store, session_id


def test_artifact_job_directory_state_machine_is_idempotent_and_registers_revision(monkeypatch, tmp_path) -> None:
    session_store, session_id = _configured_store(monkeypatch, tmp_path)
    jobs = SketchMathArtifactJobStore(tmp_path / "jobs", output_root=tmp_path / "cad")
    request = ArtifactBuildRequest(feature_id="feature_plate", format="stl", base_revision=1)

    submitted = jobs.submit(session_store, session_id, request, start=False)
    completed = jobs.run(submitted.job_id, session_store)
    duplicate = jobs.submit(session_store, session_id, request, start=False)

    assert submitted.state == "READY"
    assert completed.state == "DONE"
    assert completed.step == "complete"
    assert completed.attempt == 1
    assert duplicate.job_id == submitted.job_id
    assert duplicate.state == "DONE"
    job_dir = tmp_path / "jobs" / submitted.job_id
    assert {path.name for path in job_dir.iterdir()} >= {
        "manifest.json",
        "request.json",
        "materialized.json",
        "result.json",
        "validate.done",
        "materialize.done",
        "register.done",
    }
    manifest_payload = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_payload["state"] == "DONE"
    artifact_path = Path(completed.result.artifact.path)
    assert artifact_path.exists()
    assert artifact_path.suffix == ".stl"
    assert completed.result.artifact.revision == 1
    assert completed.result.measurements["volume_mm3"] == 840.0
    snapshot = session_store.snapshot(session_id, session_store.get_session(session_id))
    assert snapshot["document"]["artifacts"][0]["artifact_id"] == completed.result.artifact.artifact_id
    assert snapshot["document"]["artifacts"][0]["revision"] == 1


def test_stale_artifact_result_fails_without_registration_and_retains_resumable_materialization(monkeypatch, tmp_path) -> None:
    session_store, session_id = _configured_store(monkeypatch, tmp_path)
    jobs = SketchMathArtifactJobStore(tmp_path / "jobs", output_root=tmp_path / "cad")
    request = ArtifactBuildRequest(feature_id="feature_plate", format="stl", base_revision=1)
    submitted = jobs.submit(session_store, session_id, request, start=False)
    session_store.run_command(
        session_id,
        {
            "version": "0.1",
            "command_id": "advance_revision",
            "mode": "commit",
            "command_type": "define_point",
            "selection": [],
            "parameters": {"name": "point_after_request", "coords": [20, 20]},
        },
    )

    failed = jobs.run(submitted.job_id, session_store)

    assert failed.state == "FAILED"
    assert failed.error.code == "revision_conflict"
    assert failed.error.detail["input_revision"] == 1
    assert failed.error.detail["current_revision"] == 2
    job_dir = tmp_path / "jobs" / submitted.job_id
    assert (job_dir / "materialize.done").exists()
    assert not (job_dir / "register.done").exists()
    snapshot = session_store.snapshot(session_id, session_store.get_session(session_id))
    assert snapshot["document"]["revision"] == 2
    assert snapshot["document"]["artifacts"] == []


def test_fillet_step_runs_through_resumable_job_and_registers_kernel_measurements(monkeypatch, tmp_path) -> None:
    freecad_cmd = Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd")
    if not freecad_cmd.exists():
        pytest.skip("FreeCADCmd is unavailable")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_FREECAD_CMD", str(freecad_cmd))
    session_store = SketchMathSessionStore(session_dir=tmp_path / "sessions")
    selection = _selection()
    selection["items"] = [
        {
            "id": "box",
            "type": "profile_2d",
            "vertices": [[0, 0], [20, 0], [20, 10], [0, 10], [0, 0]],
            "area": 200,
            "winding": "counterclockwise",
        }
    ]
    session_id, _ = session_store.create_session({"selection_context": selection})
    base_command = _feature_command()
    base_command["parameters"]["feature"]["feature_id"] = "feature_box"
    base_command["parameters"]["feature"]["profile_id"] = "box"
    base_command["parameters"]["feature"]["parameters"] = {"depth_mm": 5, "operation": "new_body"}
    base_response = session_store.run_feature_command(session_id, base_command, mode="commit")
    edges = [
        item
        for item in base_response["document"]["last_rebuild"]["records"][0]["generated_topology"]
        if item["role"] == "vertical_outer_edge"
    ]
    fillet_command = {
        "version": "1.0",
        "operation_id": "add_fillet",
        "mode": "commit",
        "base_revision": 1,
        "operation_type": "add_feature",
        "parameters": {
            "feature": {
                "feature_id": "feature_fillet",
                "feature_type": "fillet",
                "name": "Outer fillet",
                "body_id": "body_main",
                "sketch_id": "sketch_main",
                "profile_id": None,
                "dependencies": ["feature_box"],
                "topology_references": [
                    {
                        "reference_id": edge["reference_id"],
                        "owner_feature_id": "feature_box",
                        "topology_type": "edge",
                        "role": edge["role"],
                        "source_entity_id": edge["source_entity_id"],
                        "expected_signature": edge["geometric_signature"],
                    }
                    for edge in edges
                ],
                "parameters": {"radius_mm": 2, "operation": "modify"},
            }
        },
    }
    fillet_response = session_store.run_feature_command(session_id, fillet_command, mode="commit")
    assert fillet_response["document"]["revision"] == 2
    jobs = SketchMathArtifactJobStore(tmp_path / "jobs", output_root=tmp_path / "cad")

    submitted = jobs.submit(
        session_store,
        session_id,
        ArtifactBuildRequest(feature_id="feature_fillet", format="step", base_revision=2),
        start=False,
    )
    completed = jobs.run(submitted.job_id, session_store)

    expected_volume = 20 * 10 * 5 - 4 * (1 - math.pi / 4) * 2**2 * 5
    assert completed.state == "DONE"
    assert completed.result.artifact.format == "step"
    assert Path(completed.result.artifact.path).exists()
    assert completed.result.measurements["volume_mm3"] == pytest.approx(expected_volume, abs=1e-5)
    assert completed.result.measurements["selected_edge_count"] == 4
    assert (tmp_path / "jobs" / submitted.job_id / "materialize.done").exists()
    assert (tmp_path / "jobs" / submitted.job_id / "register.done").exists()
