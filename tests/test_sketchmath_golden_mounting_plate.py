from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.sketchmath.artifact_jobs import SketchMathArtifactJobStore
from backend.sketchmath.service import SketchMathSessionStore
from sketchmath.cad.adapter import CadAdapter
from sketchmath.cad.feature_artifact import materialize_feature_artifact
from sketchmath.executor.errors import CadExportError, CommandValidationError, SelectionResolutionError
from sketchmath.executor.command_router import GeometrySession
from sketchmath.features.executor import apply_feature_command
from sketchmath.features.golden_mounting_plate import build_golden_mounting_plate, edit_golden_mounting_plate_parameters, golden_mounting_plate_expectation
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import SketchMathDocument
from sketchmath.models.artifact_job import ArtifactBuildRequest
from sketchmath.models.feature_command import FeatureCommand
from sketchmath.models.geometry_command import GeometryCommand


def _body_bounds(document: SketchMathDocument) -> tuple[float, float, float, float, float, float]:
    measurements = [
        record.measurements.bounds_mm
        for record in document.last_rebuild.records
        if record.measurements is not None and record.measurements.volume_delta_mm3 > 0
    ]
    return (
        min(item[0] for item in measurements),
        max(item[1] for item in measurements),
        min(item[2] for item in measurements),
        max(item[3] for item in measurements),
        min(item[4] for item in measurements),
        max(item[5] for item in measurements),
    )


def test_golden_mounting_plate_rebuild_is_deterministic_and_matches_geometric_ledger() -> None:
    document = build_golden_mounting_plate()
    expected = golden_mounting_plate_expectation()
    first = rebuild_document(document)
    second = rebuild_document(document.model_copy(deep=True))

    assert first == second == document.last_rebuild
    assert first.ok is True
    assert len(document.features) == expected.feature_count
    assert first.rebuild_order == [
        "feature_plate",
        "feature_mount_hole_1",
        "feature_mount_hole_2",
        "feature_mount_hole_3",
        "feature_mount_hole_4",
        "feature_boss",
        "feature_boss_hole",
        "feature_outer_fillet",
    ]
    assert _body_bounds(document) == pytest.approx(expected.body_bounds_mm)
    assert sum(record.measurements.volume_delta_mm3 for record in first.records if record.measurements) == pytest.approx(
        expected.pre_fillet_volume_mm3
    )
    holes = [feature for feature in document.features if feature.feature_type == "hole"]
    assert len(holes) == expected.through_hole_count
    assert [feature.parameters.position_mm for feature in holes] == [
        (7, 7),
        (73, 7),
        (73, 43),
        (7, 43),
        (40, 25),
    ]
    assert [feature.parameters.diameter_mm for feature in holes] == [5, 5, 5, 5, 10]
    assert all(record.resolved_references[0].recovery_state == "exact" for record in first.records if record.feature_id in {hole.feature_id for hole in holes})
    boss = next(record for record in first.records if record.feature_id == "feature_boss")
    assert boss.measurements.bounds_mm[-2:] == pytest.approx((5, expected.maximum_z_mm))
    boss_hole = next(record for record in first.records if record.feature_id == "feature_boss_hole")
    assert boss_hole.measurements.bounds_mm[-2:] == pytest.approx((0, expected.maximum_z_mm))
    fillet = next(record for record in first.records if record.feature_id == "feature_outer_fillet")
    assert fillet.measurement_coverage == "kernel_required"
    assert len(fillet.resolved_references) == 4
    assert all(item.recovery_state == "exact" for item in fillet.resolved_references)


def test_golden_mounting_plate_serializes_and_rehydrates_without_identity_drift() -> None:
    document = build_golden_mounting_plate()

    rehydrated = SketchMathDocument.model_validate_json(document.model_dump_json())
    report = rebuild_document(rehydrated)

    assert rehydrated == document
    assert report.content_hash == document.last_rebuild.content_hash
    assert [feature.feature_id for feature in rehydrated.features] == [feature.feature_id for feature in document.features]
    assert [record.output_signature for record in report.records] == [record.output_signature for record in document.last_rebuild.records]


def test_golden_mounting_plate_sketch_supports_normal_mode_analysis_without_stale_topology_refs() -> None:
    session = GeometrySession(build_golden_mounting_plate().sketches[0].state)

    analysis = session.execute(GeometryCommand(
        version="0.3",
        command_id="golden_analysis",
        mode="preview",
        command_type="analyze_constraints",
        selection=[],
        parameters={},
    ))
    topology = session.execute(GeometryCommand(
        version="0.9",
        command_id="golden_topology",
        mode="preview",
        command_type="detect_regions",
        selection=[],
        parameters={},
    ))

    assert analysis.status == "preview"
    assert analysis.metadata["solver_analysis"]["coverage"] == "partial"
    assert topology.status == "preview"
    assert len(topology.metadata["topology"]["regions"]) == 1
    assert topology.metadata["topology"]["regions"][0]["source_curve_ids"] == ["circle_boss"]


def _set_parameter(document: SketchMathDocument, parameter_id: str, value: float, *, mode: str = "commit"):
    return apply_feature_command(
        document,
        FeatureCommand(
            operation_id=f"set_{parameter_id}_{document.revision}",
            mode=mode,
            base_revision=document.revision,
            operation_type="set_design_parameter",
            target_id=parameter_id,
            parameters={"value": value},
        ),
    )


def test_golden_mounting_plate_design_parameter_preview_is_atomic_and_rebuilds_intent() -> None:
    original = build_golden_mounting_plate()

    result = _set_parameter(original, "plate_width_mm", 100, mode="preview")
    widened = result.after

    assert original.revision == 8
    assert original.sketches[0].state.get_entity("profile_plate").area == pytest.approx(4000)
    assert original.design_parameters[0].value == 80
    assert widened.revision == 9
    assert widened.design_parameters[0].value == 100
    assert widened.sketches[0].state.get_entity("profile_plate").area == pytest.approx(5000)
    assert widened.sketches[0].state.get_entity("circle_boss").center == pytest.approx((50, 25))
    holes = {feature.feature_id: feature for feature in widened.features if feature.feature_type == "hole"}
    assert holes["feature_mount_hole_2"].parameters.position_mm == pytest.approx((93, 7))
    assert holes["feature_mount_hole_3"].parameters.position_mm == pytest.approx((93, 43))
    assert holes["feature_boss_hole"].parameters.position_mm == pytest.approx((50, 25))
    assert result.rebuild.ok is True
    assert set(result.changed_feature_ids) == {
        "feature_plate",
        "feature_mount_hole_2",
        "feature_mount_hole_3",
        "feature_boss",
        "feature_boss_hole",
    }


def test_golden_mounting_plate_design_parameter_rejects_out_of_range_without_mutation() -> None:
    original = build_golden_mounting_plate()
    before = original.model_dump(mode="json")

    with pytest.raises(CommandValidationError) as exc_info:
        _set_parameter(original, "corner_hole_diameter_mm", 14)

    assert exc_info.value.detail["maximum"] == pytest.approx(13.99)
    assert original.model_dump(mode="json") == before


def test_design_parameter_contract_requires_v11_and_protects_bound_features() -> None:
    with pytest.raises(ValueError, match="version 1.1"):
        FeatureCommand(
            version="1.0",
            operation_id="legacy_parameter_edit",
            mode="commit",
            base_revision=8,
            operation_type="set_design_parameter",
            target_id="plate_width_mm",
            parameters={"value": 100},
        )

    document = build_golden_mounting_plate()
    with pytest.raises(SelectionResolutionError) as exc_info:
        apply_feature_command(
            document,
            FeatureCommand(
                operation_id="delete_bound_hole",
                mode="commit",
                base_revision=8,
                operation_type="delete_feature",
                target_id="feature_mount_hole_1",
            ),
        )

    assert exc_info.value.detail["error_code"] == "feature_still_parameter_bound"
    assert exc_info.value.detail["design_parameter_ids"] == ["corner_hole_diameter_mm"]
    assert len(document.features) == 8

    bound_hole = document.features[1]
    changed_hole = bound_hole.model_copy(
        update={"parameters": bound_hole.parameters.model_copy(update={"diameter_mm": 6})}
    )
    with pytest.raises(SelectionResolutionError) as replace_exc:
        apply_feature_command(
            document,
            FeatureCommand(
                operation_id="replace_bound_hole",
                mode="commit",
                base_revision=8,
                operation_type="replace_feature",
                target_id=bound_hole.feature_id,
                parameters={"feature": changed_hole.model_dump(mode="json")},
            ),
        )
    assert replace_exc.value.detail["error_code"] == "feature_parameter_bound"


def test_golden_mounting_plate_typed_parameter_history_survives_undo_redo_and_reload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    original = build_golden_mounting_plate()
    sessions = SketchMathSessionStore(session_dir=tmp_path / "sessions")
    session_id, _ = sessions.create_session({"document": original.model_dump(mode="json")})

    widened = sessions.run_feature_command(
        session_id,
        FeatureCommand(
            operation_id="set_plate_width",
            mode="commit",
            base_revision=8,
            operation_type="set_design_parameter",
            target_id="plate_width_mm",
            parameters={"value": 100},
        ).model_dump(mode="json"),
    )
    resized = sessions.run_feature_command(
        session_id,
        FeatureCommand(
            operation_id="set_corner_holes",
            mode="commit",
            base_revision=9,
            operation_type="set_design_parameter",
            target_id="corner_hole_diameter_mm",
            parameters={"value": 6},
        ).model_dump(mode="json"),
    )

    assert widened["document"]["design_parameters"][0]["value"] == 100
    widened_entities = {entity["id"]: entity for entity in widened["selection_context"]["items"]}
    assert widened_entities["profile_plate"]["area"] == pytest.approx(5000)
    assert widened_entities["circle_boss"]["center"] == [50, 25]
    assert resized["document"]["design_parameters"][1]["value"] == 6
    undone = sessions.revert_feature(session_id)
    assert undone["document"]["design_parameters"][0]["value"] == 100
    assert undone["document"]["design_parameters"][1]["value"] == 5
    assert undone["document"]["features"][1]["parameters"]["diameter_mm"] == 5
    redone = sessions.redo_feature(session_id)
    assert redone["document"]["design_parameters"][1]["value"] == 6
    assert redone["document"]["features"][1]["parameters"]["diameter_mm"] == 6

    reloaded = SketchMathSessionStore(session_dir=tmp_path / "sessions")
    snapshot = reloaded.snapshot(session_id, reloaded.get_session(session_id))
    assert [parameter["value"] for parameter in snapshot["document"]["design_parameters"]] == [100, 6]
    assert snapshot["document"]["features"][2]["parameters"]["position_mm"] == [93, 7]
    assert next(entity for entity in snapshot["selection_context"]["items"] if entity["id"] == "profile_plate")["area"] == pytest.approx(5000)


def test_golden_mounting_plate_width_edit_recovers_downstream_references() -> None:
    original = build_golden_mounting_plate()
    document = edit_golden_mounting_plate_parameters(original, plate_width_mm=100)
    report = document.last_rebuild

    assert report.ok is True
    assert report.records[0].measurements.bounds_mm[:2] == pytest.approx((0, 100))
    recovered_ids = {
        "feature_mount_hole_1",
        "feature_mount_hole_2",
        "feature_mount_hole_3",
        "feature_mount_hole_4",
        "feature_boss",
        "feature_boss_hole",
        "feature_outer_fillet",
    }
    resolved = [
        reference.recovery_state
        for record in report.records
        if record.feature_id in recovered_ids
        for reference in record.resolved_references
    ]
    assert "recovered" in resolved
    assert set(resolved) <= {"exact", "recovered"}
    assert sum(record.measurements.volume_delta_mm3 for record in report.records if record.measurements) == pytest.approx(
        golden_mounting_plate_expectation().pre_fillet_volume_mm3 + 20 * 50 * 5
    )
    holes = {feature.feature_id: feature for feature in document.features if feature.feature_type == "hole"}
    assert holes["feature_mount_hole_2"].parameters.position_mm == pytest.approx((93, 7))
    assert holes["feature_mount_hole_3"].parameters.position_mm == pytest.approx((93, 43))
    assert holes["feature_boss_hole"].parameters.position_mm == pytest.approx((50, 25))
    assert document.sketches[0].state.get_entity("circle_boss").center == pytest.approx((50, 25))
    assert [feature.feature_id for feature in document.features] == [feature.feature_id for feature in original.features]


def test_golden_mounting_plate_corner_hole_diameter_edit_preserves_edge_offset_intent() -> None:
    widened = edit_golden_mounting_plate_parameters(build_golden_mounting_plate(), plate_width_mm=100)
    edited = edit_golden_mounting_plate_parameters(widened, corner_hole_diameter_mm=6)

    holes = [feature for feature in edited.features if feature.feature_id.startswith("feature_mount_hole_")]
    assert [feature.parameters.diameter_mm for feature in holes] == [6, 6, 6, 6]
    assert [feature.parameters.position_mm for feature in holes] == [(7, 7), (93, 7), (93, 43), (7, 43)]
    assert sum(record.measurements.volume_delta_mm3 for record in edited.last_rebuild.records if record.measurements) == pytest.approx(
        golden_mounting_plate_expectation().pre_fillet_volume_mm3 + 20 * 50 * 5 - 55 * math.pi
    )


def test_golden_mounting_plate_terminal_fillet_refuses_layered_stl(tmp_path) -> None:
    document = build_golden_mounting_plate()

    with pytest.raises(CadExportError) as exc_info:
        materialize_feature_artifact(
            document,
            "feature_outer_fillet",
            "stl",
            output_root=tmp_path / "artifacts",
        )

    assert exc_info.value.detail["error_code"] == "unsupported_stl_feature_type"


def test_golden_mounting_plate_materializes_valid_revisioned_kernel_step(tmp_path) -> None:
    freecad_cmd = Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd")
    if not freecad_cmd.exists():
        pytest.skip("FreeCADCmd is unavailable")
    document = build_golden_mounting_plate()
    expected = golden_mounting_plate_expectation()

    artifact = materialize_feature_artifact(
        document,
        "feature_outer_fillet",
        "step",
        output_root=tmp_path / "artifacts",
        cad_adapter=CadAdapter(freecad_cmd=freecad_cmd, export_dir=tmp_path / "kernel"),
    )

    measurements = artifact["measurements"]
    assert Path(artifact["path"]).exists()
    assert artifact["revision"] == 8
    assert measurements["is_valid_solid"] is True
    assert measurements["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 80, "ymin": 0, "ymax": 50, "zmin": 0, "zmax": 13}
    )
    assert measurements["pre_finish_volume_mm3"] == pytest.approx(expected.pre_fillet_volume_mm3, abs=1e-6)
    assert measurements["volume_mm3"] == pytest.approx(expected.final_volume_mm3, abs=1e-5)
    assert measurements["selected_edge_count"] == 4
    assert measurements["radius_mm"] == expected.fillet_radius_mm
    assert measurements["canonical_hole_count"] == expected.through_hole_count
    assert [item["feature_type"] for item in measurements["operation_execution"]] == [
        "extrude",
        "hole",
        "hole",
        "hole",
        "hole",
        "extrude",
        "hole",
    ]
    radii = measurements["cylindrical_face_radii_mm"]
    assert sum(math.isclose(radius, 2.5, abs_tol=1e-6) for radius in radii) == 4
    assert any(math.isclose(radius, 5, abs_tol=1e-6) for radius in radii)
    assert any(math.isclose(radius, 15, abs_tol=1e-6) for radius in radii)


def test_edited_golden_mounting_plate_materializes_valid_widened_kernel_step(tmp_path) -> None:
    freecad_cmd = Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd")
    if not freecad_cmd.exists():
        pytest.skip("FreeCADCmd is unavailable")
    document = edit_golden_mounting_plate_parameters(
        build_golden_mounting_plate(),
        plate_width_mm=100,
        corner_hole_diameter_mm=6,
    )

    artifact = materialize_feature_artifact(
        document,
        "feature_outer_fillet",
        "step",
        output_root=tmp_path / "artifacts",
        cad_adapter=CadAdapter(freecad_cmd=freecad_cmd, export_dir=tmp_path / "kernel"),
    )

    measurements = artifact["measurements"]
    assert artifact["revision"] == 10
    assert measurements["is_valid_solid"] is True
    assert measurements["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 100, "ymin": 0, "ymax": 50, "zmin": 0, "zmax": 13}
    )
    assert measurements["volume_mm3"] == pytest.approx(24_920 + 1_315 * math.pi, abs=1e-5)
    assert measurements["canonical_hole_count"] == 5
    radii = measurements["cylindrical_face_radii_mm"]
    assert sum(math.isclose(radius, 3, abs_tol=1e-6) for radius in radii) == 4
    assert any(math.isclose(radius, 5, abs_tol=1e-6) for radius in radii)
    assert any(math.isclose(radius, 15, abs_tol=1e-6) for radius in radii)


def test_golden_mounting_plate_step_runs_through_resumable_job_and_persists_registration(monkeypatch, tmp_path) -> None:
    freecad_cmd = Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd")
    if not freecad_cmd.exists():
        pytest.skip("FreeCADCmd is unavailable")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", "1")
    monkeypatch.setenv("FRIDAY_SKETCHMATH_FREECAD_CMD", str(freecad_cmd))
    document = build_golden_mounting_plate()
    sessions = SketchMathSessionStore(session_dir=tmp_path / "sessions")
    session_id, _ = sessions.create_session({"document": document.model_dump(mode="json")})
    jobs = SketchMathArtifactJobStore(tmp_path / "jobs", output_root=tmp_path / "cad")

    submitted = jobs.submit(
        sessions,
        session_id,
        ArtifactBuildRequest(feature_id="feature_outer_fillet", format="step", base_revision=8),
        start=False,
    )
    completed = jobs.run(submitted.job_id, sessions)
    duplicate = jobs.submit(
        sessions,
        session_id,
        ArtifactBuildRequest(feature_id="feature_outer_fillet", format="step", base_revision=8),
        start=False,
    )

    assert completed.state == "DONE"
    assert duplicate.job_id == submitted.job_id
    assert duplicate.state == "DONE"
    assert completed.result.artifact.revision == 8
    assert completed.result.artifact.format == "step"
    assert completed.result.measurements["volume_mm3"] == pytest.approx(
        golden_mounting_plate_expectation().final_volume_mm3,
        abs=1e-5,
    )
    job_dir = tmp_path / "jobs" / submitted.job_id
    assert (job_dir / "materialize.done").exists()
    assert (job_dir / "register.done").exists()

    reloaded_sessions = SketchMathSessionStore(session_dir=tmp_path / "sessions")
    snapshot = reloaded_sessions.snapshot(session_id, reloaded_sessions.get_session(session_id))
    assert snapshot["document"]["features"][-1]["feature_id"] == "feature_outer_fillet"
    assert snapshot["document"]["artifacts"][0]["revision"] == 8
    assert snapshot["document"]["artifacts"][0]["metadata"]["measurements"]["canonical_hole_count"] == 5
