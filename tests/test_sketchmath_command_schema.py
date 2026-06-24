from __future__ import annotations


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


def test_geometry_command_schema_lists_supported_mvp_commands() -> None:
    import json
    from pathlib import Path

    schema = json.loads(Path("sketchmath/schemas/geometry_command.schema.json").read_text(encoding="utf-8"))
    command_types = set(schema["properties"]["command_type"]["enum"])

    assert "delete_entity" in command_types
    assert "set_rectangle_dimension" in command_types
    assert "add_profile_hole" in command_types
    assert "update_profile_hole" in command_types
    assert "extrude_profile" in command_types
    assert "define_circle" not in command_types
    assert "define_arc" not in command_types


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
