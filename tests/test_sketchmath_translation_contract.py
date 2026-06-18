from __future__ import annotations


def test_sketchmath_system_prompt_mentions_geometry_command() -> None:
    from sketchmath.translator.translator_client import load_prompt

    text = load_prompt("sketchmath_system")

    assert "GeometryCommand" in text
    assert "typed geometry command" in text.lower()


def test_geometry_command_repair_trims_whitespace() -> None:
    from sketchmath.translator.repair import repair_geometry_command

    assert repair_geometry_command("\n  {\"ok\": true}  \n") == '{"ok": true}'
