from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from sketchmath.geometry.intersections import intersect_lines
from sketchmath.geometry.profiles import analyze_closed_polygon
from sketchmath.geometry.projections import project_point_to_line
from sketchmath.geometry.transforms import (
    mirror_point_across_vertical_axis,
    rotate_point_around,
    set_distance_between_points,
    set_line_polar,
    translate_point,
)
from sketchmath.geometry.units import denormalize_angle, denormalize_length, normalize_angle, normalize_length
from sketchmath.geometry.vectors import Point2D, add, distance, normalize, rotate_point, scale, subtract
from sketchmath.models.constraints import (
    AngleConstraint,
    ConstraintEntity,
    DistanceConstraint,
    EqualAngleConstraint,
    EqualLengthConstraint,
    FixedPointConstraint,
    HorizontalConstraint,
    VerticalConstraint,
    CoincidentConstraint,
    ParallelConstraint,
    PerpendicularConstraint,
)
from sketchmath.cad.adapter import CadAdapter
from sketchmath.cad.profile_holes import validate_profile_holes
from sketchmath.cad.preview_mesh import build_preview_mesh
from sketchmath.models.entities import (
    Axis2DEntity,
    ConstructionLine2DEntity,
    Circle2DEntity,
    Line2DEntity,
    Point2DEntity,
    Profile2DEntity,
    SelectionEntity,
)
from sketchmath.geometry.topology import detect_line_profiles
from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.operation_result import OperationResult
from sketchmath.models.selection_context import SelectionContext

from .errors import (
    CadExportError,
    ClarificationRequiredError,
    InvalidUnitsError,
    LockedEntityMutationError,
    MissingParameterError,
    SelectionResolutionError,
    SolverError,
    SketchMathError,
    UnsupportedCommandError,
    WrongEntityTypeError,
)
from .history import GeometryHistory, OperationRecord


@dataclass
class GeometrySession:
    initial_state: SelectionContext

    def __post_init__(self) -> None:
        self.initial_state = self.initial_state.model_copy(deep=True)
        self.state = self.initial_state.model_copy(deep=True)
        self.history = GeometryHistory()

    def execute(self, command: GeometryCommand) -> OperationResult:
        before = self.state.model_copy(deep=True)
        after, changed, value, unit, metadata = apply_geometry_command(command, before)
        result_metadata = dict(metadata)
        result_metadata.setdefault("history_length", self.history.cursor + (1 if command.mode == "commit" else 0))
        result = OperationResult(
            command=command,
            status="committed" if command.mode == "commit" else "preview",
            before=before,
            after=after.model_copy(deep=True),
            changed_entity_ids=changed,
            replay_index=self.history.cursor,
            value=value,
            unit=unit,
            metadata=result_metadata,
        )
        if command.mode == "commit":
            self.history.append(
                OperationRecord(
                    command=command,
                    before=before,
                    after=after.model_copy(deep=True),
                    committed=True,
                )
            )
            self.state = after
        return result

    def revert(self) -> SelectionContext:
        if self.history.cursor == 0:
            self.state = self.initial_state.model_copy(deep=True)
            return self.state
        self.history.pop_last()
        self.state = self.history.replay(self.initial_state)
        return self.state

    def redo(self) -> SelectionContext:
        self.history.redo_next()
        self.state = self.history.replay(self.initial_state)
        return self.state


def apply_geometry_command(
    command: GeometryCommand,
    state: SelectionContext,
) -> tuple[SelectionContext, list[str], float | None, str | None, dict[str, Any]]:
    state = state.model_copy(deep=True)
    handlers = {
        "measure_distance": _handle_measure_distance,
        "measure_angle": _handle_measure_angle,
        "define_point": _handle_define_point,
        "define_line": _handle_define_line,
        "define_profile": _handle_define_profile,
        "delete_entity": _handle_delete_entity,
        "set_distance": _handle_set_distance,
        "set_rectangle_dimension": _handle_set_rectangle_dimension,
        "set_line_polar": _handle_set_line_polar,
        "set_angle": _handle_set_angle,
        "make_parallel": _handle_make_parallel,
        "make_perpendicular": _handle_make_perpendicular,
        "make_equal_length": _handle_make_equal_length,
        "make_equal_angle": _handle_make_equal_angle,
        "solve_constraints": _handle_solve_constraints,
        "make_profile": _handle_make_profile,
        "add_profile_hole": _handle_add_profile_hole,
        "update_profile_hole": _handle_update_profile_hole,
        "extrude_profile": _handle_extrude_profile,
        "translate": _handle_translate,
        "rotate": _handle_rotate,
        "mirror": _handle_mirror,
        "copy_linear": _handle_copy_linear,
        "intersect_lines": _handle_intersect_lines,
        "project_point_to_line": _handle_project_point_to_line,
        "batch": _handle_batch,
    }
    handlers.update({
        "make_horizontal": _handle_make_horizontal,
        "make_vertical": _handle_make_vertical,
        "make_coincident": _handle_make_coincident,
        "detect_profiles": _handle_detect_profiles,
        "define_circle": _handle_define_circle,
        "update_circle": _handle_update_circle,
        "make_circle_profile": _handle_make_circle_profile,
    })
    handler = handlers.get(command.command_type)
    if handler is None:
        raise UnsupportedCommandError(
            f"Unsupported SketchMath command: {command.command_type}",
            detail={"command_type": command.command_type},
        )
    result = handler(command, state)
    _sync_linked_geometry(result[0])
    return result


def _handle_measure_distance(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    a, b = _resolve_points(state, command.selection)
    unit = str(_parameter(command, "unit", default=state.units))
    try:
        value = denormalize_length(distance(a.coords, b.coords), unit)
    except ValueError as exc:
        raise InvalidUnitsError(str(exc), detail={"command_type": command.command_type, "unit": unit}) from exc
    return state, [], value, unit, {}


def _handle_measure_angle(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    if len(command.selection) < 2:
        raise SelectionResolutionError(
            "Expected two selected line-like entities",
            detail={"command_type": command.command_type, "selection": command.selection},
        )
    a = _resolve_line_like(state, command.selection[0], "first")
    b = _resolve_line_like(state, command.selection[1], "second")
    a_start, a_end = _line_points(a)
    b_start, b_end = _line_points(b)
    a_vec = subtract(a_end, a_start)
    b_vec = subtract(b_end, b_start)
    dot = a_vec[0] * b_vec[0] + a_vec[1] * b_vec[1]
    cross = a_vec[0] * b_vec[1] - a_vec[1] * b_vec[0]
    angle_radians = abs(math.atan2(cross, dot))
    unit = str(_parameter(command, "unit", default="deg"))
    try:
        value = denormalize_angle(angle_radians, unit)
    except ValueError as exc:
        raise InvalidUnitsError(str(exc), detail={"command_type": command.command_type, "unit": unit}) from exc
    return state, [], value, unit, {}


def _handle_define_point(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    name = str(_parameter(command, "name"))
    coords = _point_tuple(_parameter(command, "coords"))
    label = command.parameters.get("label")
    point = Point2DEntity(id=name, coords=coords, locked=bool(command.parameters.get("locked", False)), label=label)
    state.replace_entity(point)
    _sync_named_reference(state, point.id, label)
    return state, [point.id], None, None, {}


def _handle_define_line(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    name = str(_parameter(command, "name"))
    start = _point_tuple(_parameter(command, "start"))
    end = _point_tuple(_parameter(command, "end"))
    label = command.parameters.get("label")
    line = Line2DEntity(
        id=name,
        start=start,
        end=end,
        start_point_id=command.parameters.get("start_point_id"),
        end_point_id=command.parameters.get("end_point_id"),
        locked=bool(command.parameters.get("locked", False)),
        label=label,
    )
    state.replace_entity(line)
    _sync_named_reference(state, line.id, label)
    return state, [line.id], None, None, {}


def _handle_define_profile(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    name = str(_parameter(command, "name"))
    vertices = [_point_tuple(vertex) for vertex in _parameter(command, "vertices")]
    area = float(_parameter(command, "area"))
    winding = str(_parameter(command, "winding", default="counterclockwise"))
    warnings = command.parameters.get("warnings") or []
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    label = command.parameters.get("label")
    profile = Profile2DEntity(
        id=name,
        vertices=vertices,
        area=area,
        winding=winding,  # type: ignore[arg-type]
        warnings=[str(warning) for warning in warnings],
        closed=bool(command.parameters.get("closed", True)),
        locked=bool(command.parameters.get("locked", False)),
        label=label,
    )
    state.replace_entity(profile)
    _sync_named_reference(state, profile.id, label)
    return state, [profile.id], profile.area, "square_mm", {"area": profile.area, "winding": profile.winding, "warnings": profile.warnings}


def _handle_delete_entity(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    if not command.selection:
        raise MissingParameterError("delete_entity requires a selection list", detail={"command_type": command.command_type, "parameter": "selection"})
    cascade = bool(command.parameters.get("cascade", False))
    referenced_entities = {
        constraint_point
        for constraint in state.constraints
        for constraint_point in getattr(constraint, "points", [])
    }
    named_entities = set(state.named_references.values())
    deleted: list[str] = []
    for entity_id in command.selection:
        entity = state.get_entity(entity_id)
        if entity.locked:
            raise LockedEntityMutationError(
                f"Cannot delete locked entity: {entity_id}",
                detail={"command_type": command.command_type, "entity_id": entity_id},
            )
        if not cascade and (entity_id in referenced_entities or entity_id in named_entities):
            raise SelectionResolutionError(
                "Cannot delete an entity that is still referenced",
                detail={"command_type": command.command_type, "entity_id": entity_id, "dependencies": _entity_dependencies(state, entity_id)},
            )
    remaining = [entity for entity in state.items if entity.id not in command.selection]
    state.items = remaining
    if cascade:
        state.constraints = [
            constraint
            for constraint in state.constraints
            if not any(point_id in command.selection for point_id in getattr(constraint, "points", []))
        ]
    for name, entity_id in list(state.named_references.items()):
        if entity_id in command.selection:
            state.named_references.pop(name, None)
    deleted.extend(command.selection)
    return state, deleted, None, None, {"deleted_entity_ids": deleted}


def _entity_dependencies(state: SelectionContext, entity_id: str) -> list[dict[str, str]]:
    dependencies: list[dict[str, str]] = []
    for constraint in state.constraints:
        if entity_id in getattr(constraint, "points", []):
            dependencies.append({"kind": "constraint", "id": constraint.id})
    for name, mapped_id in state.named_references.items():
        if mapped_id == entity_id:
            dependencies.append({"kind": "named_reference", "id": name})
    return dependencies


def _handle_set_distance(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    start, end = _resolve_points(state, command.selection)
    anchor = str(command.parameters.get("anchor", "midpoint")).strip().lower()
    target_distance = float(_parameter(command, "distance"))
    unit = str(_parameter(command, "unit", default=state.units))
    try:
        new_a, new_b = set_distance_between_points(start.coords, end.coords, target_distance, anchor=anchor, unit=unit)
    except ValueError as exc:
        if "unit" in str(exc).lower():
            raise InvalidUnitsError(str(exc), detail={"command_type": command.command_type, "unit": unit}) from exc
        raise SelectionResolutionError(str(exc), detail={"command_type": command.command_type, "anchor": anchor}) from exc
    if anchor == "midpoint":
        _ensure_mutable(state, [start.id, end.id], command.command_type)
        state.replace_entity(_replace_point(start, new_a))
        state.replace_entity(_replace_point(end, new_b))
        constraint = DistanceConstraint(id=f"constraint_{command.command_id}", points=(start.id, end.id), distance=target_distance, unit=unit, anchor="midpoint")
        state.replace_constraint(constraint)
        return state, [start.id, end.id], None, None, {"constraint_id": constraint.id}
    if anchor == "point_a":
        _ensure_mutable(state, [end.id], command.command_type)
        state.replace_entity(_replace_point(end, new_b))
        constraint = DistanceConstraint(id=f"constraint_{command.command_id}", points=(start.id, end.id), distance=target_distance, unit=unit, anchor="point_a")
        state.replace_constraint(constraint)
        return state, [end.id], None, None, {"constraint_id": constraint.id}
    if anchor == "point_b":
        _ensure_mutable(state, [start.id], command.command_type)
        state.replace_entity(_replace_point(start, new_a))
        constraint = DistanceConstraint(id=f"constraint_{command.command_id}", points=(start.id, end.id), distance=target_distance, unit=unit, anchor="point_b")
        state.replace_constraint(constraint)
        return state, [start.id], None, None, {"constraint_id": constraint.id}
    raise SelectionResolutionError(f"Unsupported anchor for set_distance: {anchor}", detail={"command_type": command.command_type, "anchor": anchor})


def _handle_set_rectangle_dimension(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    base_id = str(command.parameters.get("base_id") or _rectangle_base_id_from_selection(command.selection))
    dimension = str(_parameter(command, "dimension")).strip().lower()
    if dimension not in {"width", "height"}:
        raise SelectionResolutionError(
            "Rectangle dimension must be width or height",
            detail={"command_type": command.command_type, "dimension": dimension},
        )
    unit = str(_parameter(command, "unit", default=state.units))
    try:
        value_mm = normalize_length(float(_parameter(command, "value")), unit)
    except ValueError as exc:
        raise InvalidUnitsError(str(exc), detail={"command_type": command.command_type, "unit": unit}) from exc
    if value_mm <= 0:
        raise SelectionResolutionError(
            "Rectangle dimension must be positive",
            detail={"command_type": command.command_type, "dimension": dimension, "value": value_mm},
        )

    bundle = _resolve_rectangle_bundle(state, base_id)
    sign_x = 1.0 if bundle["ab"].end[0] >= bundle["ab"].start[0] else -1.0
    sign_y = 1.0 if bundle["da"].start[1] >= bundle["da"].end[1] else -1.0
    current_width = abs(bundle["ab"].end[0] - bundle["ab"].start[0])
    current_height = abs(bundle["da"].start[1] - bundle["da"].end[1])
    width = value_mm if dimension == "width" else current_width
    height = value_mm if dimension == "height" else current_height
    if width <= 0 or height <= 0:
        raise SelectionResolutionError(
            "Rectangle width and height must be positive",
            detail={"command_type": command.command_type, "width": width, "height": height},
        )

    top_left = bundle["a"].coords
    top_right = (round(top_left[0] + sign_x * width, 10), top_left[1])
    bottom_left = (top_left[0], round(top_left[1] + sign_y * height, 10))
    bottom_right = (top_right[0], bottom_left[1])

    point_updates = {
        bundle["a"].id: top_left,
        bundle["b"].id: top_right,
        bundle["c"].id: bottom_right,
        bundle["d"].id: bottom_left,
    }
    line_updates = {
        bundle["ab"].id: (top_left, top_right),
        bundle["bc"].id: (top_right, bottom_right),
        bundle["cd"].id: (bottom_right, bottom_left),
        bundle["da"].id: (bottom_left, top_left),
    }
    vertices = [top_left, top_right, bottom_right, bottom_left, top_left]
    analysis = analyze_closed_polygon(vertices)

    moving_ids = [entity_id for entity_id, coords in point_updates.items() if bundle[_rectangle_suffix(entity_id)].coords != coords]
    moving_ids.extend(
        entity_id
        for entity_id, (start, end) in line_updates.items()
        if bundle[_rectangle_suffix(entity_id)].start != start or bundle[_rectangle_suffix(entity_id)].end != end
    )
    moving_ids.append(bundle["profile"].id)
    _ensure_mutable(state, _dedupe(moving_ids), command.command_type)

    for key in ("a", "b", "c", "d"):
        point = bundle[key]
        state.replace_entity(_replace_point(point, point_updates[point.id]))
    for key in ("ab", "bc", "cd", "da"):
        line = bundle[key]
        start, end = line_updates[line.id]
        state.replace_entity(Line2DEntity(**{**line.model_dump(), "start": start, "end": end}))
    state.replace_entity(
        Profile2DEntity(
            **{
                **bundle["profile"].model_dump(),
                "vertices": analysis.vertices,
                "area": analysis.area,
                "winding": analysis.winding,
                "warnings": analysis.warnings,
                "closed": analysis.closed,
            }
        )
    )
    changed = [bundle[key].id for key in ("a", "b", "c", "d", "ab", "bc", "cd", "da")] + [bundle["profile"].id]
    solver_status = "solved" if bundle["a"].locked else "underconstrained"
    return (
        state,
        changed,
        denormalize_length(value_mm, unit),
        unit,
        {
            "base_id": base_id,
            "dimension": dimension,
            "width": denormalize_length(width, unit),
            "height": denormalize_length(height, unit),
            "area": analysis.area,
            "winding": analysis.winding,
            "warnings": analysis.warnings,
            "solver_status": solver_status,
            "profile_status": "valid" if analysis.closed and not analysis.warnings else "invalid",
        },
    )


def _handle_set_line_polar(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    start_id = str(command.parameters.get("start", command.selection[0] if command.selection else ""))
    end_id = str(command.parameters.get("end", command.selection[1] if len(command.selection) > 1 else ""))
    start = _resolve_point(state, start_id, "start")
    end = _resolve_point(state, end_id, "end")
    _ensure_mutable(state, [end.id], command.command_type)
    length = float(_parameter(command, "length"))
    angle = float(_parameter(command, "angle"))
    length_unit = str(_parameter(command, "length_unit", default=state.units))
    angle_unit = str(_parameter(command, "angle_unit", default="deg"))
    try:
        new_end = set_line_polar(start.coords, length, angle, length_unit=length_unit, angle_unit=angle_unit)
    except ValueError as exc:
        if "unit" in str(exc).lower():
            raise InvalidUnitsError(str(exc), detail={"command_type": command.command_type, "length_unit": length_unit, "angle_unit": angle_unit}) from exc
        raise
    state.replace_entity(_replace_point(end, new_end))
    return state, [end.id], None, None, {}


def _handle_set_angle(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    if len(command.selection) < 3:
        raise SelectionResolutionError("Expected anchor, pivot, and moving point", detail={"selection": command.selection})
    anchor = _resolve_point(state, command.selection[0], "anchor")
    pivot = _resolve_point(state, command.selection[1], "pivot")
    moving = _resolve_point(state, command.selection[2], "moving")
    _ensure_mutable(state, [moving.id], command.command_type)
    target = float(_parameter(command, "angle"))
    angle_unit = str(_parameter(command, "angle_unit", default="deg"))
    anchor_vec = subtract(anchor.coords, pivot.coords)
    base_angle = math.atan2(anchor_vec[1], anchor_vec[0])
    target_radians = normalize_angle(target, angle_unit)
    radius = distance(pivot.coords, moving.coords)
    if radius == 0.0:
        raise ClarificationRequiredError("Cannot set angle with zero-length moving segment", detail={"command_type": command.command_type})
    new_coords = (
        pivot.coords[0] + radius * math.cos(base_angle + target_radians),
        pivot.coords[1] + radius * math.sin(base_angle + target_radians),
    )
    state.replace_entity(_replace_point(moving, new_coords))
    constraint = AngleConstraint(id=f"constraint_{command.command_id}", points=(anchor.id, pivot.id, moving.id), angle=target, unit=angle_unit)
    state.replace_constraint(constraint)
    return state, [moving.id], None, None, {"constraint_id": constraint.id}


def _handle_make_parallel(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    ref_a, ref_b, target_a, target_b = _resolve_segment4(state, command.selection)
    ref_vector = subtract(ref_b.coords, ref_a.coords)
    if ref_vector == (0.0, 0.0):
        raise SolverError("Reference segment is zero-length", detail={"command_type": command.command_type})
    constraint = ParallelConstraint(id=f"constraint_{command.command_id}", points=(ref_a.id, ref_b.id, target_a.id, target_b.id))
    target_vector = subtract(target_b.coords, target_a.coords)
    if target_vector != (0.0, 0.0) and math.isclose(_cross(target_vector, ref_vector), 0.0, rel_tol=1e-9, abs_tol=1e-9):
        state.replace_constraint(constraint)
        return state, [], None, None, {"constraint_id": constraint.id}
    target_length = distance(target_a.coords, target_b.coords)
    direction = normalize(ref_vector)
    if target_b.locked and not target_a.locked:
        _ensure_mutable(state, [target_a.id], command.command_type)
        new_end = subtract(target_b.coords, scale(direction, target_length))
        state.replace_entity(_replace_point(target_a, new_end))
        moved = target_a
    else:
        _ensure_mutable(state, [target_b.id], command.command_type)
        new_end = add(target_a.coords, scale(direction, target_length))
        state.replace_entity(_replace_point(target_b, new_end))
        moved = target_b
    state.replace_constraint(constraint)
    return state, [moved.id], None, None, {"constraint_id": constraint.id}


def _handle_make_perpendicular(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    ref_a, ref_b, target_a, target_b = _resolve_segment4(state, command.selection)
    ref_vector = subtract(ref_b.coords, ref_a.coords)
    if ref_vector == (0.0, 0.0):
        raise SolverError("Reference segment is zero-length", detail={"command_type": command.command_type})
    constraint = PerpendicularConstraint(id=f"constraint_{command.command_id}", points=(ref_a.id, ref_b.id, target_a.id, target_b.id))
    target_vector = subtract(target_b.coords, target_a.coords)
    if target_vector != (0.0, 0.0) and math.isclose(_dot(target_vector, ref_vector), 0.0, rel_tol=1e-9, abs_tol=1e-9):
        state.replace_constraint(constraint)
        return state, [], None, None, {"constraint_id": constraint.id}
    target_length = distance(target_a.coords, target_b.coords)
    perp = (-ref_vector[1], ref_vector[0])
    direction = normalize(perp)
    if target_b.locked and not target_a.locked:
        _ensure_mutable(state, [target_a.id], command.command_type)
        new_end = subtract(target_b.coords, scale(direction, target_length))
        state.replace_entity(_replace_point(target_a, new_end))
        moved = target_a
    else:
        _ensure_mutable(state, [target_b.id], command.command_type)
        new_end = add(target_a.coords, scale(direction, target_length))
        state.replace_entity(_replace_point(target_b, new_end))
        moved = target_b
    state.replace_constraint(constraint)
    return state, [moved.id], None, None, {"constraint_id": constraint.id}


def _handle_make_equal_length(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    ref_a, ref_b, target_a, target_b = _resolve_segment4(state, command.selection)
    ref_length = distance(ref_a.coords, ref_b.coords)
    target_vector = subtract(target_b.coords, target_a.coords)
    direction = normalize(target_vector)
    if target_b.locked and not target_a.locked:
        _ensure_mutable(state, [target_a.id], command.command_type)
        new_end = subtract(target_b.coords, scale(direction, ref_length))
        state.replace_entity(_replace_point(target_a, new_end))
        moved = target_a
    else:
        _ensure_mutable(state, [target_b.id], command.command_type)
        new_end = add(target_a.coords, scale(direction, ref_length))
        state.replace_entity(_replace_point(target_b, new_end))
        moved = target_b
    constraint = EqualLengthConstraint(id=f"constraint_{command.command_id}", points=(ref_a.id, ref_b.id, target_a.id, target_b.id))
    state.replace_constraint(constraint)
    return state, [moved.id], None, None, {"constraint_id": constraint.id}


def _handle_make_equal_angle(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    if len(command.selection) < 6:
        raise SelectionResolutionError("Expected two point triples", detail={"selection": command.selection})
    a1, a2, a3 = _resolve_point(state, command.selection[0], "source_a"), _resolve_point(state, command.selection[1], "source_b"), _resolve_point(state, command.selection[2], "source_c")
    b1, b2, b3 = _resolve_point(state, command.selection[3], "target_a"), _resolve_point(state, command.selection[4], "target_b"), _resolve_point(state, command.selection[5], "target_c")
    _ensure_mutable(state, [b3.id], command.command_type)
    source_angle = _point_triple_angle(a1.coords, a2.coords, a3.coords)
    target_radius = distance(b2.coords, b3.coords)
    base_angle = math.atan2(a1.coords[1] - a2.coords[1], a1.coords[0] - a2.coords[0])
    new_coords = (
        b2.coords[0] + target_radius * math.cos(base_angle + source_angle),
        b2.coords[1] + target_radius * math.sin(base_angle + source_angle),
    )
    state.replace_entity(_replace_point(b3, new_coords))
    constraint = EqualAngleConstraint(id=f"constraint_{command.command_id}", points=(a1.id, a2.id, a3.id, b1.id, b2.id, b3.id))
    state.replace_constraint(constraint)
    return state, [b3.id], None, None, {"constraint_id": constraint.id}


def _axis_constraint_points(command: GeometryCommand, state: SelectionContext) -> tuple[Point2DEntity, Point2DEntity]:
    if len(command.selection) == 1:
        line = _resolve_line_like(state, command.selection[0], "line")
        if not isinstance(line, (Line2DEntity, ConstructionLine2DEntity)) or not line.start_point_id or not line.end_point_id:
            raise SelectionResolutionError(
                "Selected line does not have addressable endpoint identities",
                detail={"command_type": command.command_type, "entity_id": line.id},
            )
        return _resolve_point(state, line.start_point_id, "start"), _resolve_point(state, line.end_point_id, "end")
    return _resolve_points(state, command.selection)


def _handle_make_horizontal(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    a, b = _axis_constraint_points(command, state)
    constraint = HorizontalConstraint(id=f"constraint_{command.command_id}", points=(a.id, b.id))
    outcome = _apply_horizontal_constraint(constraint, state)
    state.replace_constraint(constraint)
    return state, outcome["changed_entity_ids"], None, None, {"constraint_id": constraint.id}


def _handle_make_vertical(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    a, b = _axis_constraint_points(command, state)
    constraint = VerticalConstraint(id=f"constraint_{command.command_id}", points=(a.id, b.id))
    outcome = _apply_vertical_constraint(constraint, state)
    state.replace_constraint(constraint)
    return state, outcome["changed_entity_ids"], None, None, {"constraint_id": constraint.id}


def _handle_make_coincident(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    a, b = _resolve_points(state, command.selection)
    constraint = CoincidentConstraint(id=f"constraint_{command.command_id}", points=(a.id, b.id))
    outcome = _apply_coincident_constraint(constraint, state)
    state.replace_constraint(constraint)
    return state, outcome["changed_entity_ids"], None, None, {"constraint_id": constraint.id}


def _handle_detect_profiles(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    candidates = detect_line_profiles(state)
    return state, [], None, None, {"profile_candidates": candidates, "candidate_count": len(candidates)}


def _circle_profile(circle: Circle2DEntity, profile_id: str, *, segments: int = 48) -> Profile2DEntity:
    analysis = analyze_closed_polygon(_circle_profile_vertices(circle.center, circle.radius, segments))
    return Profile2DEntity(
        id=profile_id,
        vertices=analysis.vertices,
        area=analysis.area,
        winding=analysis.winding,  # type: ignore[arg-type]
        warnings=analysis.warnings,
        closed=True,
        label=circle.label or "Circle profile",
    )


def _handle_define_circle(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    name = str(_parameter(command, "name"))
    center = _point_tuple(_parameter(command, "center"))
    radius = float(_parameter(command, "radius"))
    if radius <= 0:
        raise SelectionResolutionError("Circle radius must be positive", detail={"command_type": command.command_type, "radius": radius})
    circle = Circle2DEntity(
        id=name,
        center=center,
        radius=radius,
        center_point_id=command.parameters.get("center_point_id"),
        locked=bool(command.parameters.get("locked", False)),
        label=command.parameters.get("label"),
    )
    state.replace_entity(circle)
    return state, [circle.id], radius, state.units, {"radius": radius, "diameter": radius * 2}


def _handle_update_circle(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    if len(command.selection) != 1:
        raise SelectionResolutionError("update_circle requires one circle", detail={"selection": command.selection})
    circle = state.get_entity(command.selection[0])
    if not isinstance(circle, Circle2DEntity):
        raise WrongEntityTypeError("Selected entity is not a circle", detail={"entity_id": circle.id})
    _ensure_mutable(state, [circle.id], command.command_type)
    radius = float(command.parameters.get("radius", circle.radius))
    center = _point_tuple(command.parameters.get("center", circle.center))
    if radius <= 0:
        raise SelectionResolutionError("Circle radius must be positive", detail={"radius": radius})
    updated = Circle2DEntity(**{**circle.model_dump(), "center": center, "radius": radius})
    state.replace_entity(updated)
    return state, [updated.id], radius, state.units, {"radius": radius, "diameter": radius * 2}


def _handle_make_circle_profile(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    if len(command.selection) != 1:
        raise SelectionResolutionError("make_circle_profile requires one circle", detail={"selection": command.selection})
    circle = state.get_entity(command.selection[0])
    if not isinstance(circle, Circle2DEntity):
        raise WrongEntityTypeError("Selected entity is not a circle", detail={"entity_id": circle.id})
    profile = _circle_profile(circle, str(command.parameters.get("name") or f"profile_{circle.id}"), segments=int(command.parameters.get("segments", 48)))
    state.replace_entity(profile)
    return state, [profile.id], profile.area, "square_mm", {"source_circle_id": circle.id, "profile_id": profile.id}


def _handle_solve_constraints(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    constraint_ids = command.parameters.get("constraint_ids")
    if constraint_ids is None:
        constraints = list(state.constraints)
    else:
        constraints = [state.get_constraint(str(constraint_id)) for constraint_id in constraint_ids]
    if not constraints:
        return state, [], None, None, {"warnings": ["no_constraints"]}
    current = state.model_copy(deep=True)
    changed: list[str] = []
    changed.extend(_solve_quadrilateral_intersections(constraints, current))
    unresolved: list[str] = []
    for _ in range(8):
        pass_changed = False
        current_unresolved: list[str] = []
        for constraint in constraints:
            outcome = _apply_constraint(constraint, current)
            if outcome["status"] == "changed":
                pass_changed = True
                changed.extend(outcome["changed_entity_ids"])
            elif outcome["status"] == "ambiguous":
                current_unresolved.append(constraint.id)
            elif outcome["status"] == "conflict":
                raise SolverError("Constraint conflict", detail={"constraint_id": constraint.id, "reason": outcome["reason"]})
        if not pass_changed:
            unresolved = current_unresolved
            break
        unresolved = current_unresolved
    if unresolved:
        raise ClarificationRequiredError(
            "Constraint system is under-constrained",
            detail={"constraint_ids": unresolved},
        )
    return current, _dedupe(changed), None, None, {"solved_constraints": [constraint.id for constraint in constraints]}


def _handle_make_profile(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    if len(command.selection) < 3:
        raise SelectionResolutionError("Profile requires at least three selections", detail={"selection": command.selection})
    entities = [state.get_entity(entity_id) for entity_id in command.selection]
    vertices = _profile_vertices(entities)
    analysis = analyze_closed_polygon(vertices)
    profile = Profile2DEntity(
        id=str(_parameter(command, "name", default=f"profile_{command.command_id}")),
        vertices=analysis.vertices,
        area=analysis.area,
        winding=analysis.winding,  # type: ignore[arg-type]
        warnings=analysis.warnings,
        closed=analysis.closed,
    )
    state.replace_entity(profile)
    return state, [profile.id], analysis.area, "square_mm", {"area": analysis.area, "winding": analysis.winding, "warnings": analysis.warnings}


def _handle_add_profile_hole(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    if not command.selection:
        raise SelectionResolutionError(
            "add_profile_hole requires a selected profile",
            detail={"command_type": command.command_type, "error_code": "missing_profile_selection"},
        )
    profile = _resolve_profile(state, command.selection[0])
    _ensure_mutable(state, [profile.id], command.command_type)
    unit = str(_parameter(command, "unit", default=state.units))
    try:
        diameter_mm = normalize_length(float(_parameter(command, "diameter")), unit)
    except ValueError as exc:
        raise InvalidUnitsError(str(exc), detail={"command_type": command.command_type, "unit": unit}) from exc
    if diameter_mm <= 0:
        raise SelectionResolutionError(
            "Hole diameter must be a positive number",
            detail={"command_type": command.command_type, "error_code": "invalid_hole_diameter", "diameter": diameter_mm},
        )
    center = _point_tuple(_parameter(command, "center"))
    segments = int(command.parameters.get("segments", 32))
    if segments < 12:
        segments = 12
    if segments > 96:
        segments = 96
    hole_id = str(command.parameters.get("name") or f"hole_{profile.id}_{command.command_id}")
    hole_vertices = _circle_profile_vertices(center, diameter_mm / 2.0, segments)
    analysis = analyze_closed_polygon(hole_vertices)
    hole = Profile2DEntity(
        id=hole_id,
        vertices=analysis.vertices,
        area=analysis.area,
        winding="clockwise",
        warnings=analysis.warnings,
        closed=analysis.closed,
        label=command.parameters.get("label") or "Hole",
    )
    existing_holes = [_resolve_profile(state, hole_ref) for hole_ref in profile.holes if hole_ref != hole_id]
    validation = validate_profile_holes(profile, [*existing_holes, hole])
    if not validation.ok:
        raise SelectionResolutionError(
            validation.message or "Invalid profile hole",
            detail={"command_type": command.command_type, **validation.to_dict()},
        )
    updated_profile = Profile2DEntity(**{**profile.model_dump(), "holes": _dedupe([*profile.holes, hole_id])})
    state.replace_entity(updated_profile)
    state.replace_entity(hole)
    return (
        state,
        [profile.id, hole.id],
        denormalize_length(diameter_mm, unit),
        unit,
        {
            "profile_id": profile.id,
            "hole_id": hole.id,
            "diameter": denormalize_length(diameter_mm, unit),
            "unit": unit,
            "center": [center[0], center[1]],
            "segments": segments,
            "profile_hole_validation": validation.to_dict(),
        },
    )


def _handle_update_profile_hole(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float, str, dict[str, Any]]:
    if len(command.selection) < 2:
        raise SelectionResolutionError(
            "update_profile_hole requires a selected profile and hole",
            detail={"command_type": command.command_type, "error_code": "missing_profile_or_hole_selection"},
        )
    profile = _resolve_profile(state, command.selection[0])
    hole = _resolve_profile(state, command.selection[1])
    if hole.id not in profile.holes:
        raise SelectionResolutionError(
            "Selected hole does not belong to the selected profile",
            detail={"command_type": command.command_type, "profile_id": profile.id, "hole_id": hole.id, "error_code": "hole_not_in_profile"},
        )
    _ensure_mutable(state, [profile.id, hole.id], command.command_type)
    unit = str(_parameter(command, "unit", default=state.units))
    try:
        diameter_mm = normalize_length(float(_parameter(command, "diameter")), unit)
    except ValueError as exc:
        raise InvalidUnitsError(str(exc), detail={"command_type": command.command_type, "unit": unit}) from exc
    if diameter_mm <= 0:
        raise SelectionResolutionError(
            "Hole diameter must be a positive number",
            detail={"command_type": command.command_type, "error_code": "invalid_hole_diameter", "diameter": diameter_mm},
        )
    center = _point_tuple(_parameter(command, "center"))
    segments = int(command.parameters.get("segments", max(12, len(hole.vertices) - 1)))
    if segments < 12:
        segments = 12
    if segments > 96:
        segments = 96
    hole_vertices = _circle_profile_vertices(center, diameter_mm / 2.0, segments)
    analysis = analyze_closed_polygon(hole_vertices)
    updated_hole = Profile2DEntity(
        **{
            **hole.model_dump(),
            "vertices": analysis.vertices,
            "area": analysis.area,
            "winding": "clockwise",
            "warnings": analysis.warnings,
            "closed": analysis.closed,
        }
    )
    other_holes = [_resolve_profile(state, hole_ref) for hole_ref in profile.holes if hole_ref != hole.id]
    validation = validate_profile_holes(profile, [*other_holes, updated_hole])
    if not validation.ok:
        raise SelectionResolutionError(
            validation.message or "Invalid profile hole",
            detail={"command_type": command.command_type, **validation.to_dict()},
        )
    state.replace_entity(updated_hole)
    return (
        state,
        [profile.id, updated_hole.id],
        denormalize_length(diameter_mm, unit),
        unit,
        {
            "profile_id": profile.id,
            "hole_id": updated_hole.id,
            "diameter": denormalize_length(diameter_mm, unit),
            "unit": unit,
            "center": [center[0], center[1]],
            "segments": segments,
            "profile_hole_validation": validation.to_dict(),
        },
    )


def _handle_extrude_profile(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], float | None, str | None, dict[str, Any]]:
    if len(command.selection) != 1:
        raise SelectionResolutionError(
            "Extrude profile requires one profile selection",
            detail={"command_type": command.command_type, "selection": command.selection},
        )
    profile = _resolve_profile(state, command.selection[0])
    hole_ids = command.parameters.get("holes", profile.holes)
    if hole_ids is None:
        hole_ids = []
    if not isinstance(hole_ids, list):
        raise MissingParameterError(
            "holes must be a list of profile ids",
            detail={"command_type": command.command_type, "parameter": "holes"},
        )
    holes = [_resolve_profile(state, str(entity_id)) for entity_id in hole_ids]
    validation = validate_profile_holes(profile, holes)
    if not validation.ok:
        raise SelectionResolutionError(
            validation.message or "Invalid profile hole configuration",
            detail={"command_type": command.command_type, **validation.to_dict()},
        )
    depth = float(_parameter(command, "depth"))
    if depth <= 0:
        raise SelectionResolutionError(
            "Extrusion depth must be a positive number",
            detail={"command_type": command.command_type, "error_code": "invalid_extrusion_depth", "depth": depth},
        )
    depth_unit = str(_parameter(command, "depth_unit", default="mm"))
    direction = str(_parameter(command, "direction", default="positive_normal"))
    output_format = str(_parameter(command, "output_format", default="step"))
    adapter = CadAdapter.from_env()
    export = adapter.extrude_profile(
        profile,
        holes=holes,
        depth=depth,
        depth_unit=depth_unit,
        direction=direction,
        output_format=output_format,
        selection_set_id=state.selection_set_id,
        command_id=command.command_id,
    )
    preview_mesh = build_preview_mesh(
        profile,
        holes=holes,
        depth=depth,
        depth_unit=depth_unit,
        validation=validation,
    )
    metadata = {
        "cad_export": export.model_dump(mode="json"),
        "profile_hole_validation": validation.to_dict(),
        "preview_mesh": preview_mesh,
    }
    value = export.measurements.volume_mm3 if export.measurements is not None else None
    return state, [], value, "mm^3" if value is not None else None, metadata


def _handle_translate(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    delta = _vector_tuple(_parameter(command, "vector"))
    changed: list[str] = []
    for entity_id in command.selection:
        entity = state.get_entity(entity_id)
        _ensure_mutable(state, [entity.id], command.command_type)
        state.replace_entity(_translate_entity(entity, delta))
        changed.append(entity.id)
    return state, changed, None, None, {}


def _handle_rotate(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    origin = _point_tuple(command.parameters.get("origin", (0.0, 0.0)))
    angle = float(_parameter(command, "angle"))
    angle_unit = str(_parameter(command, "angle_unit", default="deg"))
    changed: list[str] = []
    for entity_id in command.selection:
        entity = state.get_entity(entity_id)
        _ensure_mutable(state, [entity.id], command.command_type)
        state.replace_entity(_rotate_entity(entity, angle, origin, angle_unit))
        changed.append(entity.id)
    return state, changed, None, None, {}


def _handle_mirror(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    axis_x = float(_parameter(command, "axis_x", default=0.0))
    changed: list[str] = []
    for entity_id in command.selection:
        entity = state.get_entity(entity_id)
        _ensure_mutable(state, [entity.id], command.command_type)
        state.replace_entity(_mirror_entity(entity, axis_x))
        changed.append(entity.id)
    return state, changed, None, None, {}


def _handle_copy_linear(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    delta = _vector_tuple(_parameter(command, "vector"))
    count = int(_parameter(command, "count", default=1))
    if count < 1:
        raise SelectionResolutionError("copy_linear count must be at least 1", detail={"command_type": command.command_type, "count": count})
    prefix = str(_parameter(command, "id_prefix", default="copy"))
    changed: list[str] = []
    for index in range(1, count + 1):
        offset = scale(delta, float(index))
        for entity_id in command.selection:
            entity = state.get_entity(entity_id)
            copy_id = f"{prefix}_{command.command_id}_{index}_{entity.id}"
            state.replace_entity(_copy_entity(entity, offset, copy_id))
            changed.append(copy_id)
    return state, changed, None, None, {}


def _handle_intersect_lines(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    if len(command.selection) < 2:
        raise SelectionResolutionError("Expected two selected lines", detail={"command_type": command.command_type, "selection": command.selection})
    a = _resolve_line_like(state, command.selection[0], "first")
    b = _resolve_line_like(state, command.selection[1], "second")
    a_start, a_end = _line_points(a)
    b_start, b_end = _line_points(b)
    try:
        point = intersect_lines(a_start, a_end, b_start, b_end)
    except ValueError as exc:
        raise SolverError(str(exc), detail={"command_type": command.command_type, "selection": command.selection}) from exc
    name = str(command.parameters.get("name", f"{a.id}_{b.id}_intersection"))
    state.replace_entity(Point2DEntity(id=name, coords=point))
    return state, [name], None, None, {}


def _handle_project_point_to_line(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    if len(command.selection) < 2:
        raise SelectionResolutionError("Expected point and line selections", detail={"command_type": command.command_type, "selection": command.selection})
    point_entity = _resolve_point(state, command.selection[0], "point")
    line_entity = _resolve_line_like(state, command.selection[1], "line")
    line_start, line_end = _line_points(line_entity)
    try:
        projected = project_point_to_line(point_entity.coords, line_start, line_end)
    except ValueError as exc:
        raise SolverError(str(exc), detail={"command_type": command.command_type, "selection": command.selection}) from exc
    name = str(command.parameters.get("name", f"{point_entity.id}_projected"))
    state.replace_entity(Point2DEntity(id=name, coords=projected))
    return state, [name], None, None, {}


def _handle_batch(command: GeometryCommand, state: SelectionContext) -> tuple[SelectionContext, list[str], None, None, dict[str, Any]]:
    raw_commands = command.parameters.get("commands")
    if not isinstance(raw_commands, list) or not raw_commands:
        raise MissingParameterError("batch requires a commands list", detail={"command_type": command.command_type, "parameter": "commands"})
    working = state.model_copy(deep=True)
    changed: list[str] = []
    subresults: list[dict[str, Any]] = []
    for index, raw_command in enumerate(raw_commands):
        subcommand = GeometryCommand.model_validate(raw_command)
        working, sub_changed, value, unit, metadata = apply_geometry_command(subcommand, working)
        changed.extend(sub_changed)
        subresults.append(
            {
                "index": index,
                "command_id": subcommand.command_id,
                "command_type": subcommand.command_type,
                "changed_entity_ids": sub_changed,
                "value": value,
                "unit": unit,
                "metadata": metadata,
            }
        )
    return working, _dedupe(changed), None, None, {"batch": True, "subresults": subresults}


def _apply_constraint(constraint: ConstraintEntity, state: SelectionContext) -> dict[str, Any]:
    if isinstance(constraint, FixedPointConstraint):
        return _apply_fixed_point_constraint(constraint, state)
    if isinstance(constraint, DistanceConstraint):
        return _apply_distance_constraint(constraint, state)
    if isinstance(constraint, AngleConstraint):
        return _apply_angle_constraint(constraint, state)
    if isinstance(constraint, ParallelConstraint):
        return _apply_parallel_constraint(constraint, state)
    if isinstance(constraint, PerpendicularConstraint):
        return _apply_perpendicular_constraint(constraint, state)
    if isinstance(constraint, EqualLengthConstraint):
        return _apply_equal_length_constraint(constraint, state)
    if isinstance(constraint, EqualAngleConstraint):
        return _apply_equal_angle_constraint(constraint, state)
    if isinstance(constraint, HorizontalConstraint):
        return _apply_horizontal_constraint(constraint, state)
    if isinstance(constraint, VerticalConstraint):
        return _apply_vertical_constraint(constraint, state)
    if isinstance(constraint, CoincidentConstraint):
        return _apply_coincident_constraint(constraint, state)
    raise SolverError("Unsupported constraint type", detail={"constraint_id": constraint.id})


def _apply_fixed_point_constraint(constraint: FixedPointConstraint, state: SelectionContext) -> dict[str, Any]:
    point = _resolve_point(state, constraint.point_id, "fixed_point")
    if point.locked and point.coords != constraint.coords:
        raise SolverError("Locked point conflicts with fixed point constraint", detail={"constraint_id": constraint.id, "entity_id": point.id})
    if point.coords != constraint.coords:
        state.replace_entity(_replace_point(point, constraint.coords))
        return {"status": "changed", "changed_entity_ids": [point.id]}
    return {"status": "ok", "changed_entity_ids": []}


def _axis_target(a: Point2DEntity, b: Point2DEntity, *, horizontal: bool) -> tuple[Point2DEntity, Point2D]:
    if a.locked and b.locked:
        aligned = math.isclose(a.coords[1 if horizontal else 0], b.coords[1 if horizontal else 0], abs_tol=1e-9)
        if not aligned:
            raise SolverError(
                f"{'Horizontal' if horizontal else 'Vertical'} constraint conflicts with locked points",
                detail={"point_ids": [a.id, b.id]},
            )
        return b, b.coords
    if b.locked:
        moving, anchor = a, b
    else:
        moving, anchor = b, a
    coords = (moving.coords[0], anchor.coords[1]) if horizontal else (anchor.coords[0], moving.coords[1])
    return moving, coords


def _apply_horizontal_constraint(constraint: HorizontalConstraint, state: SelectionContext) -> dict[str, Any]:
    a, b = _resolve_points(state, list(constraint.points))
    moving, coords = _axis_target(a, b, horizontal=True)
    if moving.coords == coords:
        return {"status": "ok", "changed_entity_ids": []}
    state.replace_entity(_replace_point(moving, coords))
    return {"status": "changed", "changed_entity_ids": [moving.id]}


def _apply_vertical_constraint(constraint: VerticalConstraint, state: SelectionContext) -> dict[str, Any]:
    a, b = _resolve_points(state, list(constraint.points))
    moving, coords = _axis_target(a, b, horizontal=False)
    if moving.coords == coords:
        return {"status": "ok", "changed_entity_ids": []}
    state.replace_entity(_replace_point(moving, coords))
    return {"status": "changed", "changed_entity_ids": [moving.id]}


def _apply_coincident_constraint(constraint: CoincidentConstraint, state: SelectionContext) -> dict[str, Any]:
    a, b = _resolve_points(state, list(constraint.points))
    if a.coords == b.coords:
        return {"status": "ok", "changed_entity_ids": []}
    if a.locked and b.locked:
        raise SolverError("Coincident constraint conflicts with locked points", detail={"constraint_id": constraint.id, "point_ids": [a.id, b.id]})
    moving, anchor = (a, b) if b.locked else (b, a)
    state.replace_entity(_replace_point(moving, anchor.coords))
    return {"status": "changed", "changed_entity_ids": [moving.id]}


def _apply_distance_constraint(constraint: DistanceConstraint, state: SelectionContext) -> dict[str, Any]:
    a = _resolve_point(state, constraint.points[0], "distance_a")
    b = _resolve_point(state, constraint.points[1], "distance_b")
    target = float(constraint.distance)
    unit = constraint.unit
    try:
        target_mm = float(denormalize_length(target, unit))
    except ValueError as exc:
        raise InvalidUnitsError(str(exc), detail={"constraint_id": constraint.id, "unit": unit}) from exc
    current = distance(a.coords, b.coords)
    if math.isclose(current, target_mm, rel_tol=1e-9, abs_tol=1e-9):
        return {"status": "ok", "changed_entity_ids": []}
    if a.locked and b.locked:
        raise SolverError("Distance constraint conflicts with locked points", detail={"constraint_id": constraint.id})
    if a.locked and not b.locked:
        direction = normalize(subtract(b.coords, a.coords))
        if direction == (1.0, 0.0) and current == 0.0:
            direction = (1.0, 0.0)
        state.replace_entity(_replace_point(b, add(a.coords, scale(direction, target_mm))))
        return {"status": "changed", "changed_entity_ids": [b.id]}
    if b.locked and not a.locked:
        direction = normalize(subtract(a.coords, b.coords))
        if direction == (1.0, 0.0) and current == 0.0:
            direction = (1.0, 0.0)
        state.replace_entity(_replace_point(a, add(b.coords, scale(direction, target_mm))))
        return {"status": "changed", "changed_entity_ids": [a.id]}
    return {"status": "ambiguous", "changed_entity_ids": [], "reason": "distance constraint needs one fixed point"}


def _apply_angle_constraint(constraint: AngleConstraint, state: SelectionContext) -> dict[str, Any]:
    anchor, pivot, moving = (_resolve_point(state, point_id, role) for point_id, role in zip(constraint.points, ("anchor", "pivot", "moving"), strict=True))
    if moving.locked:
        raise SolverError("Locked point conflicts with angle constraint", detail={"constraint_id": constraint.id, "entity_id": moving.id})
    target_radians = normalize_angle(constraint.angle, constraint.unit)
    base_angle = math.atan2(anchor.coords[1] - pivot.coords[1], anchor.coords[0] - pivot.coords[0])
    radius = distance(pivot.coords, moving.coords)
    if radius == 0.0:
        return {"status": "ambiguous", "changed_entity_ids": [], "reason": "moving ray has zero length"}
    new_coords = (
        pivot.coords[0] + radius * math.cos(base_angle + target_radians),
        pivot.coords[1] + radius * math.sin(base_angle + target_radians),
    )
    if moving.coords != new_coords:
        state.replace_entity(_replace_point(moving, new_coords))
        return {"status": "changed", "changed_entity_ids": [moving.id]}
    return {"status": "ok", "changed_entity_ids": []}


def _apply_parallel_constraint(constraint: ParallelConstraint, state: SelectionContext) -> dict[str, Any]:
    ref_a, ref_b, target_a, target_b = _resolve_segment4(state, constraint.points)
    ref_vector = subtract(ref_b.coords, ref_a.coords)
    if ref_vector == (0.0, 0.0):
        return {"status": "ambiguous", "changed_entity_ids": [], "reason": "reference segment zero length"}
    target_vector = subtract(target_b.coords, target_a.coords)
    if _cross(target_vector, ref_vector) == 0.0:
        return {"status": "ok", "changed_entity_ids": []}
    target_length = distance(target_a.coords, target_b.coords)
    direction = normalize(ref_vector)
    if target_b.locked and not target_a.locked:
        new_coords = subtract(target_b.coords, scale(direction, target_length))
        if target_a.coords != new_coords:
            state.replace_entity(_replace_point(target_a, new_coords))
            return {"status": "changed", "changed_entity_ids": [target_a.id]}
        return {"status": "ok", "changed_entity_ids": []}
    if not target_b.locked:
        new_coords = add(target_a.coords, scale(direction, target_length))
        if target_b.coords != new_coords:
            state.replace_entity(_replace_point(target_b, new_coords))
            return {"status": "changed", "changed_entity_ids": [target_b.id]}
        return {"status": "ok", "changed_entity_ids": []}
    return {"status": "ambiguous", "changed_entity_ids": [], "reason": "parallel constraint needs one unlocked target point"}


def _apply_perpendicular_constraint(constraint: PerpendicularConstraint, state: SelectionContext) -> dict[str, Any]:
    ref_a, ref_b, target_a, target_b = _resolve_segment4(state, constraint.points)
    ref_vector = subtract(ref_b.coords, ref_a.coords)
    if ref_vector == (0.0, 0.0):
        return {"status": "ambiguous", "changed_entity_ids": [], "reason": "reference segment zero length"}
    target_vector = subtract(target_b.coords, target_a.coords)
    if _dot(target_vector, ref_vector) == 0.0:
        return {"status": "ok", "changed_entity_ids": []}
    target_length = distance(target_a.coords, target_b.coords)
    direction = normalize((-ref_vector[1], ref_vector[0]))
    if target_b.locked and not target_a.locked:
        new_coords = subtract(target_b.coords, scale(direction, target_length))
        if target_a.coords != new_coords:
            state.replace_entity(_replace_point(target_a, new_coords))
            return {"status": "changed", "changed_entity_ids": [target_a.id]}
        return {"status": "ok", "changed_entity_ids": []}
    if not target_b.locked:
        new_coords = add(target_a.coords, scale(direction, target_length))
        if target_b.coords != new_coords:
            state.replace_entity(_replace_point(target_b, new_coords))
            return {"status": "changed", "changed_entity_ids": [target_b.id]}
        return {"status": "ok", "changed_entity_ids": []}
    return {"status": "ambiguous", "changed_entity_ids": [], "reason": "perpendicular constraint needs one unlocked target point"}


def _apply_equal_length_constraint(constraint: EqualLengthConstraint, state: SelectionContext) -> dict[str, Any]:
    ref_a, ref_b, target_a, target_b = _resolve_segment4(state, constraint.points)
    ref_length = distance(ref_a.coords, ref_b.coords)
    target_vector = subtract(target_b.coords, target_a.coords)
    if target_vector == (0.0, 0.0):
        return {"status": "ambiguous", "changed_entity_ids": [], "reason": "target segment has zero length"}
    direction = normalize(target_vector)
    if math.isclose(distance(target_a.coords, target_b.coords), ref_length, rel_tol=1e-9, abs_tol=1e-9):
        return {"status": "ok", "changed_entity_ids": []}
    if target_b.locked and not target_a.locked:
        new_coords = subtract(target_b.coords, scale(direction, ref_length))
        if target_a.coords != new_coords:
            state.replace_entity(_replace_point(target_a, new_coords))
            return {"status": "changed", "changed_entity_ids": [target_a.id]}
        return {"status": "ok", "changed_entity_ids": []}
    if not target_b.locked:
        new_coords = add(target_a.coords, scale(direction, ref_length))
        if target_b.coords != new_coords:
            state.replace_entity(_replace_point(target_b, new_coords))
            return {"status": "changed", "changed_entity_ids": [target_b.id]}
        return {"status": "ok", "changed_entity_ids": []}
    return {"status": "ambiguous", "changed_entity_ids": [], "reason": "equal length constraint needs one unlocked target point"}


def _apply_equal_angle_constraint(constraint: EqualAngleConstraint, state: SelectionContext) -> dict[str, Any]:
    a1, a2, a3 = (_resolve_point(state, point_id, role) for point_id, role in zip(constraint.points[:3], ("source_a", "source_b", "source_c"), strict=True))
    b1, b2, b3 = (_resolve_point(state, point_id, role) for point_id, role in zip(constraint.points[3:], ("target_a", "target_b", "target_c"), strict=True))
    if b3.locked:
        raise SolverError("Locked point conflicts with equal angle constraint", detail={"constraint_id": constraint.id, "entity_id": b3.id})
    source_angle = _point_triple_angle(a1.coords, a2.coords, a3.coords)
    target_radius = distance(b2.coords, b3.coords)
    if target_radius == 0.0:
        return {"status": "ambiguous", "changed_entity_ids": [], "reason": "target ray has zero length"}
    base_angle = math.atan2(b1.coords[1] - b2.coords[1], b1.coords[0] - b2.coords[0])
    new_coords = (
        b2.coords[0] + target_radius * math.cos(base_angle + source_angle),
        b2.coords[1] + target_radius * math.sin(base_angle + source_angle),
    )
    if b3.coords != new_coords:
        state.replace_entity(_replace_point(b3, new_coords))
        return {"status": "changed", "changed_entity_ids": [b3.id]}
    return {"status": "ok", "changed_entity_ids": []}


def _profile_vertices(entities: list[SelectionEntity]) -> list[Point2D]:
    if all(isinstance(entity, Point2DEntity) for entity in entities):
        vertices = [entity.coords for entity in entities]
    elif all(isinstance(entity, (Line2DEntity, ConstructionLine2DEntity)) for entity in entities):
        vertices = [entities[0].start]  # type: ignore[union-attr]
        for entity in entities:
            start, end = _line_points(entity)  # type: ignore[arg-type]
            if vertices[-1] == start:
                vertices.append(end)
            elif vertices[-1] == end:
                vertices.append(start)
            else:
                raise SelectionResolutionError("Profile lines are not continuous", detail={"entity_id": entity.id})
    else:
        raise SelectionResolutionError("Profile requires ordered points or ordered lines", detail={"selection": [entity.id for entity in entities]})
    if vertices[0] != vertices[-1]:
        raise SelectionResolutionError("Profile is open", detail={"first": vertices[0], "last": vertices[-1]})
    return vertices


def _sync_linked_geometry(state: SelectionContext) -> None:
    points = {item.id: item for item in state.items if isinstance(item, Point2DEntity)}
    for entity in list(state.items):
        if isinstance(entity, (Line2DEntity, ConstructionLine2DEntity)):
            start = points.get(entity.start_point_id or "")
            end = points.get(entity.end_point_id or "")
            if start is None and end is None:
                continue
            payload = entity.model_dump()
            if start is not None:
                payload["start"] = start.coords
            if end is not None:
                payload["end"] = end.coords
            state.replace_entity(type(entity)(**payload))
        elif isinstance(entity, Circle2DEntity) and entity.center_point_id in points:
            state.replace_entity(Circle2DEntity(**{**entity.model_dump(), "center": points[entity.center_point_id].coords}))


def _translate_entity(entity: SelectionEntity, delta: Point2D) -> SelectionEntity:
    if isinstance(entity, Point2DEntity):
        return _replace_point(entity, translate_point(entity.coords, delta))
    if isinstance(entity, Line2DEntity):
        return Line2DEntity(**{**entity.model_dump(), "start": translate_point(entity.start, delta), "end": translate_point(entity.end, delta)})
    if isinstance(entity, ConstructionLine2DEntity):
        return ConstructionLine2DEntity(**{**entity.model_dump(), "start": translate_point(entity.start, delta), "end": translate_point(entity.end, delta)})
    if isinstance(entity, Axis2DEntity):
        return Axis2DEntity(**{**entity.model_dump(), "origin": translate_point(entity.origin, delta)})
    if isinstance(entity, Profile2DEntity):
        return Profile2DEntity(**{**entity.model_dump(), "vertices": [translate_point(vertex, delta) for vertex in entity.vertices]})
    raise SketchMathError(f"Unsupported entity for translate: {entity.type}")


def _rotate_entity(entity: SelectionEntity, angle_value: float, origin: Point2D, angle_unit: str) -> SelectionEntity:
    if isinstance(entity, Point2DEntity):
        return _replace_point(entity, rotate_point_around(entity.coords, angle_value, origin=origin, angle_unit=angle_unit))
    if isinstance(entity, Line2DEntity):
        return Line2DEntity(**{**entity.model_dump(), "start": rotate_point_around(entity.start, angle_value, origin=origin, angle_unit=angle_unit), "end": rotate_point_around(entity.end, angle_value, origin=origin, angle_unit=angle_unit)})
    if isinstance(entity, ConstructionLine2DEntity):
        return ConstructionLine2DEntity(**{**entity.model_dump(), "start": rotate_point_around(entity.start, angle_value, origin=origin, angle_unit=angle_unit), "end": rotate_point_around(entity.end, angle_value, origin=origin, angle_unit=angle_unit)})
    if isinstance(entity, Axis2DEntity):
        rotated_origin = rotate_point_around(entity.origin, angle_value, origin=origin, angle_unit=angle_unit)
        direction_tip = add(entity.origin, entity.direction)
        rotated_tip = rotate_point_around(direction_tip, angle_value, origin=origin, angle_unit=angle_unit)
        return Axis2DEntity(**{**entity.model_dump(), "origin": rotated_origin, "direction": subtract(rotated_tip, rotated_origin)})
    if isinstance(entity, Profile2DEntity):
        return Profile2DEntity(**{**entity.model_dump(), "vertices": [rotate_point_around(vertex, angle_value, origin=origin, angle_unit=angle_unit) for vertex in entity.vertices]})
    raise SketchMathError(f"Unsupported entity for rotate: {entity.type}")


def _mirror_entity(entity: SelectionEntity, axis_x: float) -> SelectionEntity:
    if isinstance(entity, Point2DEntity):
        return _replace_point(entity, mirror_point_across_vertical_axis(entity.coords, axis_x))
    if isinstance(entity, Line2DEntity):
        return Line2DEntity(**{**entity.model_dump(), "start": mirror_point_across_vertical_axis(entity.start, axis_x), "end": mirror_point_across_vertical_axis(entity.end, axis_x)})
    if isinstance(entity, ConstructionLine2DEntity):
        return ConstructionLine2DEntity(**{**entity.model_dump(), "start": mirror_point_across_vertical_axis(entity.start, axis_x), "end": mirror_point_across_vertical_axis(entity.end, axis_x)})
    if isinstance(entity, Axis2DEntity):
        return Axis2DEntity(**{**entity.model_dump(), "origin": mirror_point_across_vertical_axis(entity.origin, axis_x), "direction": (-float(entity.direction[0]), float(entity.direction[1]))})
    if isinstance(entity, Profile2DEntity):
        return Profile2DEntity(**{**entity.model_dump(), "vertices": [mirror_point_across_vertical_axis(vertex, axis_x) for vertex in entity.vertices]})
    raise SketchMathError(f"Unsupported entity for mirror: {entity.type}")


def _copy_entity(entity: SelectionEntity, delta: Point2D, copy_id: str) -> SelectionEntity:
    if isinstance(entity, Point2DEntity):
        return Point2DEntity(**{**entity.model_dump(), "id": copy_id, "coords": translate_point(entity.coords, delta)})
    if isinstance(entity, Line2DEntity):
        return Line2DEntity(**{**entity.model_dump(), "id": copy_id, "start": translate_point(entity.start, delta), "end": translate_point(entity.end, delta)})
    if isinstance(entity, ConstructionLine2DEntity):
        return ConstructionLine2DEntity(**{**entity.model_dump(), "id": copy_id, "start": translate_point(entity.start, delta), "end": translate_point(entity.end, delta)})
    if isinstance(entity, Axis2DEntity):
        return Axis2DEntity(**{**entity.model_dump(), "id": copy_id, "origin": translate_point(entity.origin, delta)})
    if isinstance(entity, Profile2DEntity):
        return Profile2DEntity(**{**entity.model_dump(), "id": copy_id, "vertices": [translate_point(vertex, delta) for vertex in entity.vertices]})
    raise SketchMathError(f"Unsupported entity for copy_linear: {entity.type}")


def _circle_profile_vertices(center: Point2D, radius: float, segments: int) -> list[Point2D]:
    vertices: list[Point2D] = []
    for index in range(segments):
        angle = -2.0 * math.pi * index / segments
        vertices.append((center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
    vertices.append(vertices[0])
    return vertices


def _rectangle_base_id_from_selection(selection: list[str]) -> str:
    for entity_id in selection:
        if entity_id.startswith("profile_rect_"):
            return entity_id.removeprefix("profile_")
        parts = entity_id.rsplit("_", 1)
        if len(parts) == 2 and parts[0].startswith("rect_") and parts[1] in {"a", "b", "c", "d", "ab", "bc", "cd", "da"}:
            return parts[0]
    raise SelectionResolutionError("set_rectangle_dimension requires a rectangle selection", detail={"selection": selection})


def _rectangle_suffix(entity_id: str) -> str:
    if entity_id.startswith("profile_rect_"):
        return "profile"
    parts = entity_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in {"a", "b", "c", "d", "ab", "bc", "cd", "da"}:
        return parts[1]
    raise SelectionResolutionError("Invalid rectangle entity id", detail={"entity_id": entity_id})


def _resolve_rectangle_bundle(state: SelectionContext, base_id: str) -> dict[str, Any]:
    expected = {
        "a": f"{base_id}_a",
        "b": f"{base_id}_b",
        "c": f"{base_id}_c",
        "d": f"{base_id}_d",
        "ab": f"{base_id}_ab",
        "bc": f"{base_id}_bc",
        "cd": f"{base_id}_cd",
        "da": f"{base_id}_da",
        "profile": f"profile_{base_id}",
    }
    bundle = {key: state.get_entity(entity_id) for key, entity_id in expected.items()}
    for key in ("a", "b", "c", "d"):
        if not isinstance(bundle[key], Point2DEntity):
            raise WrongEntityTypeError(
                "Rectangle corner must be point_2d",
                detail={"entity_id": expected[key], "expected": "point_2d", "actual": bundle[key].type},
            )
    for key in ("ab", "bc", "cd", "da"):
        if not isinstance(bundle[key], Line2DEntity):
            raise WrongEntityTypeError(
                "Rectangle edge must be line_2d",
                detail={"entity_id": expected[key], "expected": "line_2d", "actual": bundle[key].type},
            )
    if not isinstance(bundle["profile"], Profile2DEntity):
        raise WrongEntityTypeError(
            "Rectangle profile must be profile_2d",
            detail={"entity_id": expected["profile"], "expected": "profile_2d", "actual": bundle["profile"].type},
        )
    return bundle


def _resolve_points(state: SelectionContext, selection: list[str]) -> tuple[Point2DEntity, Point2DEntity]:
    if len(selection) < 2:
        raise SelectionResolutionError("Expected at least two selected points", detail={"selection": selection})
    start = _resolve_point(state, selection[0], "first")
    end = _resolve_point(state, selection[1], "second")
    return start, end


def _resolve_segment4(state: SelectionContext, selection: tuple[str, str, str, str] | list[str]) -> tuple[Point2DEntity, Point2DEntity, Point2DEntity, Point2DEntity]:
    if len(selection) < 4:
        raise SelectionResolutionError("Expected four point selections", detail={"selection": selection})
    return (
        _resolve_point(state, selection[0], "ref_a"),
        _resolve_point(state, selection[1], "ref_b"),
        _resolve_point(state, selection[2], "target_a"),
        _resolve_point(state, selection[3], "target_b"),
    )


def _resolve_point(state: SelectionContext, entity_id: str, role: str) -> Point2DEntity:
    entity = state.get_entity(entity_id)
    if not isinstance(entity, Point2DEntity):
        raise WrongEntityTypeError(
            f"Expected point_2d for {role}",
            detail={"entity_id": entity_id, "expected": "point_2d", "actual": entity.type},
        )
    return entity


def _resolve_line_like(state: SelectionContext, entity_id: str, role: str) -> Line2DEntity | ConstructionLine2DEntity | Axis2DEntity:
    entity = state.get_entity(entity_id)
    if not isinstance(entity, (Line2DEntity, ConstructionLine2DEntity, Axis2DEntity)):
        raise WrongEntityTypeError(
            f"Expected line-like entity for {role}",
            detail={"entity_id": entity_id, "expected": "line_2d|construction_line_2d|axis_2d", "actual": entity.type},
        )
    return entity


def _resolve_profile(state: SelectionContext, entity_id: str) -> Profile2DEntity:
    entity = state.get_entity(entity_id)
    if not isinstance(entity, Profile2DEntity):
        raise WrongEntityTypeError(
            "Expected profile_2d",
            detail={"entity_id": entity_id, "expected": "profile_2d", "actual": entity.type},
        )
    if not entity.closed:
        raise CadExportError(
            "Profile must be closed before extrusion",
            detail={"entity_id": entity_id},
        )
    return entity


def _ensure_mutable(state: SelectionContext, entity_ids: list[str], command_type: str) -> None:
    for entity_id in entity_ids:
        entity = state.get_entity(entity_id)
        if entity.locked:
            raise LockedEntityMutationError(
                f"Cannot mutate locked entity: {entity_id}",
                detail={"command_type": command_type, "entity_id": entity_id},
            )


def _parameter(command: GeometryCommand, name: str, *, default: object | None = None) -> object:
    if name not in command.parameters or command.parameters[name] is None:
        if default is not None:
            return default
        raise MissingParameterError(
            f"Missing required parameter: {name}",
            detail={"command_type": command.command_type, "parameter": name},
        )
    return command.parameters[name]


def _point_tuple(value: object) -> Point2D:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (float(value[0]), float(value[1]))
    raise SelectionResolutionError("Expected a 2D coordinate pair", detail={"value": value})


def _vector_tuple(value: object) -> Point2D:
    return _point_tuple(value)


def _replace_point(entity: Point2DEntity, coords: Point2D) -> Point2DEntity:
    return Point2DEntity(**{**entity.model_dump(), "coords": coords})


def _sync_named_reference(state: SelectionContext, entity_id: str, label: object | None) -> None:
    for name, mapped_id in list(state.named_references.items()):
        if mapped_id == entity_id:
            state.named_references.pop(name, None)
    if label is None:
        return
    label_text = str(label).strip()
    if not label_text:
        return
    state.named_references[label_text] = entity_id


def _line_points(entity: Line2DEntity | ConstructionLine2DEntity | Axis2DEntity) -> tuple[Point2D, Point2D]:
    if isinstance(entity, Axis2DEntity):
        direction = entity.direction
        return entity.origin, (entity.origin[0] + direction[0], entity.origin[1] + direction[1])
    return entity.start, entity.end


def _point_triple_angle(a: Point2D, b: Point2D, c: Point2D) -> float:
    v1 = subtract(a, b)
    v2 = subtract(c, b)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    return math.atan2(cross, dot)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _cross(a: Point2D, b: Point2D) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _dot(a: Point2D, b: Point2D) -> float:
    return float(a[0] * b[0] + a[1] * b[1])


def _solve_quadrilateral_intersections(constraints: list[ConstraintEntity], state: SelectionContext) -> list[str]:
    changed: list[str] = []
    parallels = [constraint for constraint in constraints if isinstance(constraint, ParallelConstraint)]
    perpendiculars = [constraint for constraint in constraints if isinstance(constraint, PerpendicularConstraint)]
    for parallel_constraint in parallels:
        for perpendicular_constraint in perpendiculars:
            if _constraint_satisfied(parallel_constraint, state) and _constraint_satisfied(perpendicular_constraint, state):
                continue
            shared_targets = set(parallel_constraint.points[2:4]) & set(perpendicular_constraint.points[2:4])
            if len(shared_targets) != 1:
                continue
            shared_target_id = next(iter(shared_targets))
            parallel_line = _constraint_line(parallel_constraint, state, shared_target_id, perpendicular=False)
            perpendicular_line = _constraint_line(perpendicular_constraint, state, shared_target_id, perpendicular=True)
            if parallel_line is None or perpendicular_line is None:
                continue
            intersection = intersect_lines(parallel_line[0], parallel_line[1], perpendicular_line[0], perpendicular_line[1])
            target_point = _resolve_point(state, shared_target_id, "shared_target")
            if target_point.locked and target_point.coords != intersection:
                raise SolverError(
                    "Locked point conflicts with quadrilateral solve",
                    detail={"entity_id": target_point.id, "constraints": [parallel_constraint.id, perpendicular_constraint.id]},
                )
            if target_point.coords != intersection:
                state.replace_entity(_replace_point(target_point, intersection))
                changed.append(target_point.id)
    return changed


def _constraint_line(
    constraint: ParallelConstraint | PerpendicularConstraint,
    state: SelectionContext,
    shared_target_id: str,
    *,
    perpendicular: bool = False,
) -> tuple[Point2D, Point2D] | None:
    ref_a = _resolve_point(state, constraint.points[0], "ref_a")
    ref_b = _resolve_point(state, constraint.points[1], "ref_b")
    target_a = _resolve_point(state, constraint.points[2], "target_a")
    target_b = _resolve_point(state, constraint.points[3], "target_b")
    ref_vector = subtract(ref_b.coords, ref_a.coords)
    if ref_vector == (0.0, 0.0):
        return None
    if target_a.id == shared_target_id:
        start = target_b.coords
    elif target_b.id == shared_target_id:
        start = target_a.coords
    else:
        return None
    direction = (-ref_vector[1], ref_vector[0]) if perpendicular else ref_vector
    return start, add(start, direction)


def _constraint_satisfied(constraint: ParallelConstraint | PerpendicularConstraint, state: SelectionContext) -> bool:
    ref_a, ref_b, target_a, target_b = _resolve_segment4(state, constraint.points)
    ref_vector = subtract(ref_b.coords, ref_a.coords)
    target_vector = subtract(target_b.coords, target_a.coords)
    if ref_vector == (0.0, 0.0) or target_vector == (0.0, 0.0):
        return False
    if isinstance(constraint, ParallelConstraint):
        return math.isclose(_cross(target_vector, ref_vector), 0.0, rel_tol=1e-9, abs_tol=1e-9)
    return math.isclose(_dot(target_vector, ref_vector), 0.0, rel_tol=1e-9, abs_tol=1e-9)
