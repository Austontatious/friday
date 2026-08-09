from __future__ import annotations

import pytest

from sketchmath.cad.feature_artifact import materialize_feature_artifact
from sketchmath.executor.errors import CadExportError
from sketchmath.models.document import FeatureRecord, wrap_legacy_selection_context
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


def test_layered_stl_rejects_revolve_until_a_supported_mesher_exists(tmp_path) -> None:
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
            "name": "Revolve",
            "body_id": "body_main",
            "sketch_id": "sketch_main",
            "profile_id": profile.id,
            "parameters": {"axis_entity_id": "axis_y", "angle_deg": 360, "operation": "new_body"},
        }
    )
    document = document.model_copy(update={"revision": 1, "features": [revolve]})

    with pytest.raises(CadExportError) as exc_info:
        materialize_feature_artifact(
            document,
            revolve.feature_id,
            "stl",
            output_root=tmp_path / "artifacts",
        )

    assert exc_info.value.detail["error_code"] == "unsupported_stl_feature_type"
