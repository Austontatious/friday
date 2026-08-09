from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_geometry_command_defaults_to_preview() -> None:
    from sketchmath.models.geometry_command import GeometryCommand

    command = GeometryCommand.model_validate(
        {
            "version": "0.1",
            "command_id": "cmd_example",
            "command_type": "set_distance",
            "selection": ["point_A", "point_B"],
            "parameters": {"distance": 17.5, "unit": "mm", "anchor": "point_A"},
        }
    )

    assert command.mode == "preview"
    assert command.version == "0.1"
    assert command.command_type == "set_distance"


def test_geometry_command_accepts_extrude_profile() -> None:
    from sketchmath.models.geometry_command import GeometryCommand

    command = GeometryCommand.model_validate(
        {
            "version": "0.1",
            "command_id": "cmd_extrude",
            "mode": "commit",
            "command_type": "extrude_profile",
            "selection": ["profile_box"],
            "parameters": {"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step"},
        }
    )

    assert command.command_type == "extrude_profile"


def test_geometry_command_accepts_extrude_profile_holes() -> None:
    from sketchmath.models.geometry_command import GeometryCommand

    command = GeometryCommand.model_validate(
        {
            "version": "0.1",
            "command_id": "cmd_extrude_holes",
            "mode": "commit",
            "command_type": "extrude_profile",
            "selection": ["profile_outer"],
            "parameters": {
                "depth": 7.5,
                "depth_unit": "mm",
                "direction": "positive_normal",
                "output_format": "step",
                "holes": ["profile_inner"],
            },
        }
    )

    assert command.parameters["holes"] == ["profile_inner"]


def test_geometry_command_schema_matches_runtime_command_contract() -> None:
    from sketchmath.models.geometry_command import SUPPORTED_GEOMETRY_COMMAND_TYPES, SUPPORTED_GEOMETRY_COMMAND_VERSIONS

    schema = json.loads(Path("sketchmath/schemas/geometry_command.schema.json").read_text(encoding="utf-8"))
    command_types = set(schema["properties"]["command_type"]["enum"])

    assert command_types == set(SUPPORTED_GEOMETRY_COMMAND_TYPES)
    assert set(schema["properties"]["version"]["enum"]) == set(SUPPORTED_GEOMETRY_COMMAND_VERSIONS)
    assert "define_circle" in command_types
    assert "detect_profiles" in command_types
    assert "make_horizontal" in command_types
    assert "set_horizontal_distance" in command_types
    assert "set_vertical_distance" in command_types
    assert "set_radius" in command_types
    assert "set_diameter" in command_types
    assert "define_arc" in command_types
    assert "update_arc" in command_types
    assert "0.5" in schema["properties"]["version"]["enum"]
    for command_type in ("make_fixed", "make_midpoint", "make_collinear", "make_symmetric", "make_concentric", "make_tangent"):
        assert command_type in command_types
    assert "0.6" in schema["properties"]["version"]["enum"]
    assert "set_construction" in command_types
    assert "0.7" in schema["properties"]["version"]["enum"]
    assert {"define_regular_polygon", "define_slot", "split_line", "trim_line", "extend_line", "offset_curve"} <= command_types
    assert "0.8" in schema["properties"]["version"]["enum"]


def test_checked_in_sketchmath_schemas_match_canonical_models() -> None:
    from sketchmath.schemas.generate import schema_drift

    assert schema_drift() == []


def test_solver_run_result_schema_declares_neutral_patch_and_feasibility_contract() -> None:
    schema_text = Path("sketchmath/schemas/solver_run_result.schema.json").read_text(encoding="utf-8")

    for field in ("backend", "outcome", "proposed_patch", "feasible", "residual_norm", "analysis_before", "analysis_after"):
        assert f'"{field}"' in schema_text


@pytest.mark.parametrize(
    ("field", "value"),
    [("version", "9.9"), ("command_type", "unsupported")],
)
def test_geometry_command_rejects_undeclared_contract_values(field: str, value: str) -> None:
    from sketchmath.models.geometry_command import GeometryCommand

    payload = {
        "version": "0.2",
        "command_id": "cmd_contract_reject",
        "mode": "preview",
        "command_type": "define_circle",
        "selection": [],
        "parameters": {"name": "circle_1", "center": [0, 0], "radius": 5},
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        GeometryCommand.model_validate(payload)


def test_selection_context_schema_declares_current_entities_and_constraints() -> None:
    schema_text = Path("sketchmath/schemas/selection_context.schema.json").read_text(encoding="utf-8")

    for declared_type in (
        "circle_2d",
        "arc_2d",
        "horizontal_constraint",
        "vertical_constraint",
        "coincident_constraint",
        "horizontal_distance_constraint",
        "vertical_distance_constraint",
        "radius_constraint",
        "diameter_constraint",
        "midpoint_constraint",
        "collinear_constraint",
        "symmetric_constraint",
        "concentric_constraint",
        "tangent_constraint",
        "start_point_id",
        "source_circle_id",
    ):
        assert declared_type in schema_text


def test_selection_context_recognizes_2d_point_and_line_entities() -> None:
    from sketchmath.models.selection_context import SelectionContext

    selection = SelectionContext.model_validate(
        {
            "selection_set_id": "sel_001",
            "units": "mm",
            "frame": "canvas_2d",
            "items": [
                {
                    "id": "point_A",
                    "type": "point_2d",
                    "coords": [0, 0],
                    "locked": True,
                    "label": "first clicked point",
                },
                {
                    "id": "line_B",
                    "type": "line_2d",
                    "start": [0, 0],
                    "end": [3, 4],
                    "locked": False,
                },
            ],
            "named_references": {"centerline": "line_center"},
        }
    )

    assert selection.items[0].type == "point_2d"
    assert selection.items[1].type == "line_2d"
    assert selection.named_references["centerline"] == "line_center"


def test_operation_result_carries_measurement_fields() -> None:
    from sketchmath.models.geometry_command import GeometryCommand
    from sketchmath.models.operation_result import OperationResult
    from sketchmath.models.selection_context import SelectionContext

    command = GeometryCommand.model_validate(
        {
            "version": "0.1",
            "command_id": "cmd_result",
            "command_type": "measure_distance",
            "selection": ["point_A", "point_B"],
            "parameters": {"unit": "mm"},
        }
    )
    context = SelectionContext.model_validate(
        {
            "selection_set_id": "sel_002",
            "units": "mm",
            "frame": "canvas_2d",
            "items": [
                {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
                {"id": "point_B", "type": "point_2d", "coords": [1, 0], "locked": False},
            ],
            "named_references": {},
        }
    )

    result = OperationResult.model_validate(
        {
            "command": command.model_dump(),
            "status": "preview",
            "before": context.model_dump(),
            "after": context.model_dump(),
            "changed_entity_ids": [],
            "replay_index": 0,
            "value": 1.0,
            "unit": "mm",
            "metadata": {},
        }
    )

    assert result.value == 1.0
    assert result.unit == "mm"
