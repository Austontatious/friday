from __future__ import annotations

import math
from pathlib import Path

import pytest

from sketchmath.cad.adapter import CadAdapter
from sketchmath.cad.feature_artifact import materialize_feature_artifact
from sketchmath.executor.errors import CadExportError
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import FeatureRecord, SketchMathDocument, wrap_legacy_selection_context
from sketchmath.models.entities import Profile2DEntity
from sketchmath.models.selection_context import SelectionContext


def _profile(profile_id: str, vertices: list[tuple[float, float]], area: float, winding: str) -> Profile2DEntity:
    return Profile2DEntity.model_validate(
        {
            "id": profile_id,
            "type": "profile_2d",
            "vertices": vertices,
            "area": area,
            "winding": winding,
            "closed": True,
        }
    )


def _semantic_cut_document() -> tuple[SketchMathDocument, FeatureRecord, FeatureRecord]:
    outer = _profile("base", [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], 100, "counterclockwise")
    cutter = _profile("pocket", [(3, 3), (7, 3), (7, 7), (3, 7), (3, 3)], 16, "counterclockwise")
    document = wrap_legacy_selection_context(
        SelectionContext(selection_set_id="cut_artifact", units="mm", items=[outer, cutter]),
        document_id="doc_cut_artifact",
    )
    base = FeatureRecord.model_validate(
        {
            "feature_id": "feature_base",
            "name": "Base",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": outer.id,
            "parameters": {"depth_mm": 10, "operation": "new_body"},
        }
    )
    base_report = rebuild_document(document.model_copy(update={"features": [base]}))
    top = next(item for item in base_report.records[0].generated_topology if item.role == "top")
    cut = FeatureRecord.model_validate(
        {
            "feature_id": "feature_cut",
            "name": "Pocket",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": cutter.id,
            "dependencies": [base.feature_id],
            "topology_references": [
                {
                    "reference_id": top.reference_id,
                    "owner_feature_id": base.feature_id,
                    "topology_type": "face",
                    "role": top.role,
                    "source_entity_id": top.source_entity_id,
                    "expected_signature": top.geometric_signature,
                }
            ],
            "parameters": {"depth_mm": 4, "direction": "negative", "operation": "cut"},
        }
    )
    return document.model_copy(update={"revision": 2, "features": [base, cut]}), base, cut


def _revolve_document() -> tuple[SketchMathDocument, FeatureRecord]:
    profile = _profile("revolve_profile", [(2, 0), (4, 0), (4, 5), (2, 5), (2, 0)], 10, "counterclockwise")
    selection = SelectionContext.model_validate(
        {
            "selection_set_id": "revolve_artifact",
            "units": "mm",
            "items": [
                profile.model_dump(mode="json"),
                {"id": "axis_y", "type": "axis_2d", "origin": [0, 0], "direction": [0, 1]},
            ],
        }
    )
    document = wrap_legacy_selection_context(selection, document_id="doc_revolve_artifact")
    revolve = FeatureRecord.model_validate(
        {
            "feature_id": "feature_revolve",
            "feature_type": "revolve",
            "name": "Turned body",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": profile.id,
            "parameters": {"axis_entity_id": "axis_y", "angle_deg": 360, "operation": "new_body"},
        }
    )
    return document.model_copy(update={"revision": 1, "features": [revolve]}), revolve


def test_canonical_stl_materialization_uses_revisioned_safe_path_and_validates_geometry(tmp_path) -> None:
    outer = _profile("plate", [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], 100, "counterclockwise")
    hole = _profile("hole", [(3, 3), (3, 7), (7, 7), (7, 3), (3, 3)], 16, "clockwise")
    outer = outer.model_copy(update={"holes": [hole.id]})
    selection = SelectionContext(selection_set_id="artifact", units="mm", items=[outer, hole])
    document = wrap_legacy_selection_context(selection, document_id="doc/golden plate")
    feature = FeatureRecord.model_validate(
        {
            "feature_id": "feature/plate",
            "name": "Golden plate",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": "plate",
            "parameters": {"depth_mm": 10, "operation": "new_body"},
        }
    )
    document = document.model_copy(update={"revision": 7, "features": [feature]})

    artifact = materialize_feature_artifact(
        document,
        feature.feature_id,
        "stl",
        output_root=tmp_path / "artifacts",
    )

    path = tmp_path / "artifacts" / "doc_golden_plate" / "revision_7" / "feature_plate" / "doc_golden_plate_feature_plate_r7.stl"
    assert artifact["path"] == str(path.resolve())
    assert artifact["format"] == "stl"
    assert artifact["revision"] == 7
    assert artifact["measurements"]["volume_mm3"] == pytest.approx(840.0)
    assert artifact["measurements"]["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 10}
    )
    assert path.exists()


def test_canonical_stl_materializes_a_terminal_semantic_cut_graph(tmp_path) -> None:
    document, base, cut = _semantic_cut_document()

    artifact = materialize_feature_artifact(
        document,
        cut.feature_id,
        "stl",
        output_root=tmp_path / "artifacts",
    )

    assert Path(artifact["path"]).exists()
    assert artifact["measurements"]["is_closed_mesh"] is True
    assert artifact["measurements"]["volume_mm3"] == pytest.approx(936.0)
    assert artifact["measurements"]["analytic_volume_mm3"] == pytest.approx(936.0)
    assert artifact["measurements"]["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 10}
    )
    assert artifact["measurements"]["feature_ids"] == [base.feature_id, cut.feature_id]
    assert artifact["measurements"]["layer_count"] == 2


def test_canonical_step_materializes_a_terminal_semantic_cut_with_kernel_validation(tmp_path) -> None:
    freecad_cmd = Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd")
    if not freecad_cmd.exists():
        pytest.skip("FreeCADCmd is unavailable")
    document, base, cut = _semantic_cut_document()

    artifact = materialize_feature_artifact(
        document,
        cut.feature_id,
        "step",
        output_root=tmp_path / "artifacts",
        cad_adapter=CadAdapter(freecad_cmd=freecad_cmd, export_dir=tmp_path / "kernel"),
    )

    assert Path(artifact["path"]).exists()
    assert artifact["measurements"]["is_valid_solid"] is True
    assert artifact["measurements"]["volume_mm3"] == pytest.approx(936.0, abs=1e-6)
    assert artifact["measurements"]["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 10}
    )
    assert artifact["measurements"]["canonical_volume_mm3"] == pytest.approx(936.0, abs=1e-6)
    assert [item["operation"] for item in artifact["measurements"]["operation_execution"]] == ["new_body", "cut"]
    assert artifact["measurements"]["operation_execution"][1]["feature_id"] == cut.feature_id
    assert artifact["measurements"]["operation_execution"][0]["feature_id"] == base.feature_id


def test_canonical_step_materializes_a_full_revolve_with_kernel_validation(tmp_path) -> None:
    freecad_cmd = Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd")
    if not freecad_cmd.exists():
        pytest.skip("FreeCADCmd is unavailable")
    document, revolve = _revolve_document()

    artifact = materialize_feature_artifact(
        document,
        revolve.feature_id,
        "step",
        output_root=tmp_path / "artifacts",
        cad_adapter=CadAdapter(freecad_cmd=freecad_cmd, export_dir=tmp_path / "kernel"),
    )

    assert Path(artifact["path"]).exists()
    assert artifact["measurements"]["is_valid_solid"] is True
    assert artifact["measurements"]["volume_mm3"] == pytest.approx(60 * math.pi, abs=1e-6)
    assert artifact["measurements"]["bbox"] == pytest.approx(
        {"xmin": -4, "xmax": 4, "ymin": 0, "ymax": 5, "zmin": -4, "zmax": 4}
    )
    assert artifact["measurements"]["operation_execution"] == [
        {
            "feature_id": revolve.feature_id,
            "feature_type": "revolve",
            "operation": "new_body",
            "angle_deg": 360,
            "strategy": "face_with_holes",
        }
    ]


def test_layered_stl_rejects_revolve_until_a_supported_mesher_exists(tmp_path) -> None:
    document, revolve = _revolve_document()

    with pytest.raises(CadExportError) as exc_info:
        materialize_feature_artifact(
            document,
            revolve.feature_id,
            "stl",
            output_root=tmp_path / "artifacts",
        )

    assert exc_info.value.detail["error_code"] == "unsupported_stl_feature_type"


@pytest.mark.parametrize(
    ("feature_type", "size_name", "expected_volume"),
    [
        ("fillet", "radius", 20 * 10 * 5 - 4 * (1 - math.pi / 4) * 2**2 * 5),
        ("chamfer", "distance", 20 * 10 * 5 - 4 * (2**2 / 2) * 5),
    ],
)
def test_canonical_edge_finish_step_resolves_semantic_edges_and_validates_kernel_solid(
    tmp_path,
    feature_type: str,
    size_name: str,
    expected_volume: float,
) -> None:
    profile = _profile("fillet_box", [(0, 0), (20, 0), (20, 10), (0, 10), (0, 0)], 200, "counterclockwise")
    document = wrap_legacy_selection_context(
        SelectionContext(selection_set_id="fillet_artifact", units="mm", items=[profile]),
        document_id="doc_fillet_artifact",
    )
    base = FeatureRecord.model_validate(
        {
            "feature_id": "feature_base",
            "feature_type": "extrude",
            "name": "Base",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": profile.id,
            "parameters": {"depth_mm": 5, "operation": "new_body"},
        }
    )
    base_report = rebuild_document(document.model_copy(update={"features": [base]}))
    vertical_edges = [
        item for item in base_report.records[0].generated_topology if item.role == "vertical_outer_edge"
    ]
    edge_finish = FeatureRecord.model_validate(
        {
            "feature_id": f"feature_{feature_type}",
            "feature_type": feature_type,
            "name": f"Outer edge {feature_type}",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": None,
            "dependencies": [base.feature_id],
            "topology_references": [
                {
                    "reference_id": edge.reference_id,
                    "owner_feature_id": base.feature_id,
                    "topology_type": "edge",
                    "role": edge.role,
                    "source_entity_id": edge.source_entity_id,
                    "expected_signature": edge.geometric_signature,
                }
                for edge in vertical_edges
            ],
            "parameters": {f"{size_name}_mm": 2, "operation": "modify"},
        }
    )
    document = document.model_copy(update={"revision": 2, "features": [base, edge_finish]})
    freecad_cmd = Path("/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd")
    if not freecad_cmd.exists():
        pytest.skip("FreeCADCmd is unavailable")

    artifact = materialize_feature_artifact(
        document,
        edge_finish.feature_id,
        "step",
        output_root=tmp_path / "artifacts",
        cad_adapter=CadAdapter(freecad_cmd=freecad_cmd, export_dir=tmp_path / "kernel"),
    )

    assert Path(artifact["path"]).exists()
    assert artifact["measurements"]["is_valid_solid"] is True
    assert artifact["measurements"]["volume_mm3"] == pytest.approx(expected_volume, abs=1e-5)
    assert artifact["measurements"]["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 20, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 5}
    )
    assert artifact["measurements"]["selected_edge_count"] == 4
    assert artifact["measurements"][f"{size_name}_mm"] == 2
    assert artifact["measurements"]["reference_policy"] == "semantic_endpoints_unique_match"
    assert all(
        item["match_basis"] == "unordered_endpoints_mm"
        for item in artifact["measurements"]["semantic_edge_resolution"]
    )
