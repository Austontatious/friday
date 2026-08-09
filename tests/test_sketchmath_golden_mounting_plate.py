from __future__ import annotations

import pytest

from sketchmath.cad.feature_artifact import materialize_feature_artifact
from sketchmath.features.golden_mounting_plate import build_golden_mounting_plate, golden_mounting_plate_expectation
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import SketchMathDocument


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
    ]
    assert _body_bounds(document) == pytest.approx(expected.body_bounds_mm)
    assert sum(record.measurements.volume_delta_mm3 for record in first.records) == pytest.approx(expected.cumulative_volume_mm3)
    holes = [feature for feature in document.features if feature.feature_type == "hole"]
    assert len(holes) == expected.through_hole_count
    assert all(record.resolved_references[0].recovery_state == "exact" for record in first.records if record.feature_id in {hole.feature_id for hole in holes})
    boss = next(record for record in first.records if record.feature_id == "feature_boss")
    assert boss.measurements.bounds_mm[-2:] == pytest.approx((8, expected.maximum_z_mm))
    boss_hole = next(record for record in first.records if record.feature_id == "feature_boss_hole")
    assert boss_hole.measurements.bounds_mm[-2:] == pytest.approx((0, expected.maximum_z_mm))


def test_golden_mounting_plate_serializes_and_rehydrates_without_identity_drift() -> None:
    document = build_golden_mounting_plate()

    rehydrated = SketchMathDocument.model_validate_json(document.model_dump_json())
    report = rebuild_document(rehydrated)

    assert rehydrated == document
    assert report.content_hash == document.last_rebuild.content_hash
    assert [feature.feature_id for feature in rehydrated.features] == [feature.feature_id for feature in document.features]
    assert [record.output_signature for record in report.records] == [record.output_signature for record in document.last_rebuild.records]


def test_golden_mounting_plate_width_edit_recovers_downstream_references() -> None:
    document = build_golden_mounting_plate().model_copy(deep=True)
    sketch = document.sketches[0]
    profile = sketch.state.get_entity("profile_plate")
    widened = profile.model_copy(
        update={
            "vertices": [(0, 0), (120, 0), (120, 60), (0, 60), (0, 0)],
            "area": 7200,
        }
    )
    sketch.state.items[sketch.state.items.index(profile)] = widened
    document.revision += 1

    report = rebuild_document(document)

    assert report.ok is True
    assert report.records[0].measurements.bounds_mm[:2] == pytest.approx((0, 120))
    recovered_ids = {
        "feature_mount_hole_1",
        "feature_mount_hole_2",
        "feature_mount_hole_3",
        "feature_mount_hole_4",
        "feature_boss",
    }
    assert all(
        record.resolved_references[0].recovery_state == "recovered"
        for record in report.records
        if record.feature_id in recovered_ids
    )
    assert sum(record.measurements.volume_delta_mm3 for record in report.records) == pytest.approx(
        golden_mounting_plate_expectation().cumulative_volume_mm3 + 20 * 60 * 8
    )


def test_golden_mounting_plate_materializes_watertight_revisioned_stl(tmp_path) -> None:
    document = build_golden_mounting_plate()
    expected = golden_mounting_plate_expectation()

    first = materialize_feature_artifact(
        document,
        "feature_boss_hole",
        "stl",
        output_root=tmp_path / "artifacts",
    )
    second = materialize_feature_artifact(
        document.model_copy(deep=True),
        "feature_boss_hole",
        "stl",
        output_root=tmp_path / "artifacts",
    )

    measurements = first["measurements"]
    assert first["path"].endswith("golden_mounting_plate_v1_feature_boss_hole_r7.stl")
    assert first["content_hash"] == second["content_hash"]
    assert measurements["bbox"] == pytest.approx(
        {"xmin": 0, "xmax": 100, "ymin": 0, "ymax": 60, "zmin": 0, "zmax": 13}
    )
    assert measurements["analytic_volume_mm3"] == pytest.approx(expected.cumulative_volume_mm3)
    assert measurements["volume_mm3"] == pytest.approx(expected.cumulative_volume_mm3, abs=0.5)
    assert abs(measurements["volume_error_mm3"]) < 0.5
    assert measurements["is_closed_mesh"] is True
    assert measurements["nonmanifold_edge_count"] == 0
    assert measurements["layer_count"] == 2
    assert measurements["feature_ids"][-1] == "feature_boss_hole"
