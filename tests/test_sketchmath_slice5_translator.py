from __future__ import annotations


def test_translation_helper_parses_named_line_instruction() -> None:
    from sketchmath.translator.translator_service import translate_utterance
    from sketchmath.models.selection_context import SelectionContext

    context = SelectionContext.model_validate(
        {
            "selection_set_id": "sel_translate",
            "units": "mm",
            "frame": "canvas_2d",
            "items": [
                {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True, "label": "A"},
                {"id": "point_B", "type": "point_2d", "coords": [10, 0], "locked": False, "label": "B"},
            ],
            "constraints": [],
            "named_references": {"A": "point_A", "B": "point_B"},
        }
    )

    result = translate_utterance("make A-B 17.5 mm at 45 degrees", context)

    assert result.status == "command"
    assert result.command is not None
    assert result.command.command_type == "set_line_polar"
    assert result.command.selection == ["point_A", "point_B"]
    assert result.command.parameters["length"] == 17.5
    assert result.command.parameters["angle"] == 45.0


def test_translation_helper_requests_clarification_for_ambiguous_instruction() -> None:
    from sketchmath.translator.translator_service import translate_utterance
    from sketchmath.models.selection_context import SelectionContext

    context = SelectionContext.model_validate(
        {
            "selection_set_id": "sel_translate",
            "units": "mm",
            "frame": "canvas_2d",
            "items": [
                {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": True, "label": "A"},
            ],
            "constraints": [],
            "named_references": {"A": "point_A"},
        }
    )

    result = translate_utterance("make the selected line longer", context)

    assert result.status == "clarification_required"
    assert result.reason
    assert result.options
