from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Literal
from uuid import uuid4

from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.selection_context import SelectionContext

from .repair import repair_geometry_command
from .translator_client import load_prompt


@dataclass(frozen=True)
class TranslationOutcome:
    status: Literal["command", "clarification_required", "unsupported"]
    command: GeometryCommand | None = None
    reason: str | None = None
    options: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _reference_map(context: SelectionContext) -> dict[str, str]:
    mapping = dict(context.named_references)
    for item in context.items:
        label = getattr(item, "label", None)
        if label:
            mapping.setdefault(str(label), item.id)
            mapping.setdefault(str(label).strip(), item.id)
        mapping.setdefault(item.id, item.id)
    return mapping


def _resolve_reference(name: str, context: SelectionContext) -> str | None:
    reference_map = _reference_map(context)
    return reference_map.get(name) or reference_map.get(name.strip())


def _build_command(payload: dict[str, Any]) -> GeometryCommand:
    repaired = repair_geometry_command(json.dumps(payload, sort_keys=True))
    return GeometryCommand.model_validate(json.loads(repaired))


def _named_line_polar_match(utterance: str, context: SelectionContext) -> TranslationOutcome | None:
    match = re.match(
        r"^\s*make\s+([A-Za-z0-9_]+)\s*-\s*([A-Za-z0-9_]+)\s+([0-9]+(?:\.[0-9]+)?)\s*(mm|cm|m)?\s+at\s+([0-9]+(?:\.[0-9]+)?)\s*(deg|degrees|°)?\s*$",
        utterance,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    start_name, end_name, length_text, length_unit, angle_text, angle_unit = match.groups()
    start_id = _resolve_reference(start_name, context)
    end_id = _resolve_reference(end_name, context)
    if start_id is None or end_id is None:
        missing = [name for name, resolved in ((start_name, start_id), (end_name, end_id)) if resolved is None]
        return TranslationOutcome(
            status="clarification_required",
            reason="Resolve the named endpoints before building the command.",
            options=[f"Name not found: {name}" for name in missing],
            metadata={"resolved_references": _reference_map(context)},
        )
    command = _build_command(
        {
            "version": "0.1",
            "command_id": f"cmd_translate_{uuid4().hex[:12]}",
            "mode": "preview",
            "command_type": "set_line_polar",
            "selection": [start_id, end_id],
            "parameters": {
                "start": start_id,
                "end": end_id,
                "length": float(length_text),
                "length_unit": length_unit or context.units,
                "angle": float(angle_text),
                "angle_unit": "deg" if not angle_unit or angle_unit.lower() in {"deg", "degrees", "°"} else angle_unit,
            },
        }
    )
    return TranslationOutcome(
        status="command",
        command=command,
        metadata={
            "resolved_references": {start_name: start_id, end_name: end_id},
            "prompt_names": ["sketchmath_system", "geometry_command_contract"],
        },
    )


def _keyword_clarification(utterance: str, context: SelectionContext) -> TranslationOutcome | None:
    lowered = utterance.lower()
    if "longer" in lowered or "shorter" in lowered or "bigger" in lowered or "smaller" in lowered:
        return TranslationOutcome(
            status="clarification_required",
            reason="Specify the target length and which two points or segment should move.",
            options=[
                "Use 'make A-B 17.5 mm at 45 degrees'",
                "Choose the segment anchors explicitly",
            ],
            metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]},
        )
    if any(token in lowered for token in {"parallel", "perpendicular", "equal length", "equal angle"}):
        selected = [item.id for item in context.items if getattr(item, "type", "") in {"point_2d", "line_2d", "construction_line_2d", "axis_2d"}]
        if len(selected) < 2:
            return TranslationOutcome(
                status="clarification_required",
                reason="Select the minimum geometry needed before translating this command.",
                options=["Select the referenced points or lines", "Name the anchors explicitly"],
                metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]},
            )
    return None


def _keyword_command(utterance: str, context: SelectionContext) -> TranslationOutcome | None:
    lowered = utterance.lower().strip()
    selected = [item.id for item in context.items if getattr(item, "type", "") in {"point_2d", "line_2d", "construction_line_2d", "axis_2d", "profile_2d"}]
    if lowered.startswith("set angle") or "make angle" in lowered:
        angle_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", lowered)
        angle = float(angle_match.group(1)) if angle_match else 45.0
        if len(selected) < 3:
            return TranslationOutcome(
                status="clarification_required",
                reason="Set angle needs anchor, pivot, and moving point.",
                options=["Select three named points", "Name the three points explicitly"],
                metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]},
            )
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "set_angle",
                "selection": selected[:3],
                "parameters": {"angle": angle, "angle_unit": "deg"},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "translate" in lowered:
        numbers = [float(match) for match in re.findall(r"([0-9]+(?:\.[0-9]+)?)", lowered)]
        vector = [numbers[0] if numbers else 10.0, numbers[1] if len(numbers) > 1 else 0.0]
        if len(selected) < 1:
            return TranslationOutcome(status="clarification_required", reason="Translate needs at least one selected entity.", options=["Select one or more entities"], metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "translate",
                "selection": selected,
                "parameters": {"vector": vector},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "rotate" in lowered:
        numbers = [float(match) for match in re.findall(r"([0-9]+(?:\.[0-9]+)?)", lowered)]
        angle = numbers[0] if numbers else 90.0
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "rotate",
                "selection": selected,
                "parameters": {"angle": angle, "angle_unit": "deg", "origin": [0.0, 0.0]},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "mirror" in lowered:
        numbers = [float(match) for match in re.findall(r"([0-9]+(?:\.[0-9]+)?)", lowered)]
        axis_x = numbers[0] if numbers else 0.0
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "mirror",
                "selection": selected,
                "parameters": {"axis_x": axis_x},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "equal length" in lowered:
        if len(selected) < 4:
            return TranslationOutcome(status="clarification_required", reason="Equal length needs two point pairs.", options=["Select four points"], metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "make_equal_length",
                "selection": selected[:4],
                "parameters": {},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "equal angle" in lowered:
        if len(selected) < 6:
            return TranslationOutcome(status="clarification_required", reason="Equal angle needs two point triples.", options=["Select six points"], metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "make_equal_angle",
                "selection": selected[:6],
                "parameters": {},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "profile" in lowered:
        if len(selected) < 3:
            return TranslationOutcome(status="clarification_required", reason="Profile needs an ordered closed selection.", options=["Select an ordered chain of points or lines"], metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "make_profile",
                "selection": selected,
                "parameters": {"name": f"profile_{uuid4().hex[:8]}"},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "parallel" in lowered:
        if len(selected) < 4:
            return TranslationOutcome(status="clarification_required", reason="Parallel needs two line segments.", options=["Select four point endpoints"], metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "make_parallel",
                "selection": selected[:4],
                "parameters": {},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    if "perpendicular" in lowered:
        if len(selected) < 4:
            return TranslationOutcome(status="clarification_required", reason="Perpendicular needs two line segments.", options=["Select four point endpoints"], metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
        command = _build_command(
            {
                "version": "0.1",
                "command_id": f"cmd_translate_{uuid4().hex[:12]}",
                "mode": "preview",
                "command_type": "make_perpendicular",
                "selection": selected[:4],
                "parameters": {},
            }
        )
        return TranslationOutcome(status="command", command=command, metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]})
    return None


def translate_utterance(utterance: str, context: SelectionContext) -> TranslationOutcome:
    _ = load_prompt("sketchmath_system")
    _ = load_prompt("geometry_command_contract")

    if not utterance.strip():
        return TranslationOutcome(
            status="unsupported",
            reason="Empty utterance.",
            metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]},
        )

    line_polar = _named_line_polar_match(utterance, context)
    if line_polar is not None:
        return line_polar

    clarification = _keyword_clarification(utterance, context)
    if clarification is not None:
        return clarification

    keyword_command = _keyword_command(utterance, context)
    if keyword_command is not None:
        return keyword_command

    lowered = utterance.lower()
    if any(token in lowered for token in {"translate", "rotate", "mirror", "profile", "set angle", "set length"}):
        return TranslationOutcome(
            status="clarification_required",
            reason="The utterance is too vague to map to a deterministic SketchMath command.",
            options=["Name the target points or lines", "Specify the length, angle, or reference anchors"],
            metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]},
        )

    return TranslationOutcome(
        status="unsupported",
        reason="No deterministic translator rule matched the utterance.",
        metadata={"prompt_names": ["sketchmath_system", "geometry_command_contract"]},
    )
