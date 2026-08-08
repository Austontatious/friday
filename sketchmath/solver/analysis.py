from __future__ import annotations

from dataclasses import dataclass

from sketchmath.geometry.tolerances import DEFAULT_TOLERANCE_POLICY, NumericalTolerancePolicy
from sketchmath.models.constraints import (
    CoincidentConstraint,
    FixedPointConstraint,
    HorizontalConstraint,
    VerticalConstraint,
)
from sketchmath.models.entities import (
    Circle2DEntity,
    ConstructionLine2DEntity,
    Line2DEntity,
    Point2DEntity,
    Profile2DEntity,
)
from sketchmath.models.selection_context import SelectionContext
from sketchmath.models.solver_analysis import SolverAnalysis


@dataclass(frozen=True)
class _Equation:
    coefficients: dict[str, float]
    right_hand_side: float


def _matrix_rank(rows: list[list[float]], width: int, tolerance: float) -> int:
    if not rows or width == 0:
        return 0
    matrix = [row[:width] for row in rows]
    rank = 0
    for column in range(width):
        pivot = max(range(rank, len(matrix)), key=lambda index: abs(matrix[index][column]), default=rank)
        if pivot >= len(matrix) or abs(matrix[pivot][column]) <= tolerance:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        pivot_value = matrix[rank][column]
        matrix[rank] = [value / pivot_value for value in matrix[rank]]
        for row_index, row in enumerate(matrix):
            if row_index == rank or abs(row[column]) <= tolerance:
                continue
            factor = row[column]
            matrix[row_index] = [value - factor * pivot_value for value, pivot_value in zip(row, matrix[rank], strict=True)]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def _ranks(equations: list[_Equation], variable_keys: list[str], tolerance: float) -> tuple[int, int]:
    index = {key: position for position, key in enumerate(variable_keys)}
    coefficient_rows: list[list[float]] = []
    augmented_rows: list[list[float]] = []
    for equation in equations:
        row = [0.0] * len(variable_keys)
        for key, value in equation.coefficients.items():
            row[index[key]] = value
        coefficient_rows.append(row)
        augmented_rows.append([*row, equation.right_hand_side])
    return (
        _matrix_rank(coefficient_rows, len(variable_keys), tolerance),
        _matrix_rank(augmented_rows, len(variable_keys) + 1, tolerance),
    )


def _point_equations(
    state: SelectionContext,
) -> tuple[list[str], list[_Equation], list[str], list[str], list[str], list[str], dict[str, list[_Equation]]]:
    points = {entity.id: entity for entity in state.items if isinstance(entity, Point2DEntity)}
    variable_keys = [key for point_id in sorted(points) for key in (f"{point_id}.x", f"{point_id}.y")]
    implicit: list[_Equation] = []
    fixed_entity_ids: list[str] = []
    for point_id in sorted(points):
        point = points[point_id]
        if point.locked:
            fixed_entity_ids.append(point_id)
            implicit.extend(
                [
                    _Equation({f"{point_id}.x": 1.0}, point.coords[0]),
                    _Equation({f"{point_id}.y": 1.0}, point.coords[1]),
                ]
            )

    supported: list[str] = []
    unsupported: list[str] = []
    invalid: list[str] = []
    grouped: dict[str, list[_Equation]] = {}
    for constraint in sorted(state.constraints, key=lambda item: item.id):
        equations: list[_Equation]
        if isinstance(constraint, FixedPointConstraint):
            if constraint.point_id not in points:
                invalid.append(constraint.id)
                continue
            equations = [
                _Equation({f"{constraint.point_id}.x": 1.0}, constraint.coords[0]),
                _Equation({f"{constraint.point_id}.y": 1.0}, constraint.coords[1]),
            ]
        elif isinstance(constraint, HorizontalConstraint):
            if any(point_id not in points for point_id in constraint.points):
                invalid.append(constraint.id)
                continue
            a, b = constraint.points
            equations = [_Equation({f"{a}.y": 1.0, f"{b}.y": -1.0}, 0.0)]
        elif isinstance(constraint, VerticalConstraint):
            if any(point_id not in points for point_id in constraint.points):
                invalid.append(constraint.id)
                continue
            a, b = constraint.points
            equations = [_Equation({f"{a}.x": 1.0, f"{b}.x": -1.0}, 0.0)]
        elif isinstance(constraint, CoincidentConstraint):
            if any(point_id not in points for point_id in constraint.points):
                invalid.append(constraint.id)
                continue
            a, b = constraint.points
            equations = [
                _Equation({f"{a}.x": 1.0, f"{b}.x": -1.0}, 0.0),
                _Equation({f"{a}.y": 1.0, f"{b}.y": -1.0}, 0.0),
            ]
        else:
            unsupported.append(constraint.id)
            continue
        supported.append(constraint.id)
        grouped[constraint.id] = equations
    return variable_keys, implicit, fixed_entity_ids, supported, unsupported, invalid, grouped


def _unmodeled_entities(state: SelectionContext) -> list[str]:
    point_ids = {entity.id for entity in state.items if isinstance(entity, Point2DEntity)}
    unmodeled: list[str] = []
    for entity in state.items:
        if isinstance(entity, Point2DEntity):
            continue
        if isinstance(entity, (Line2DEntity, ConstructionLine2DEntity)):
            if entity.start_point_id in point_ids and entity.end_point_id in point_ids:
                continue
            unmodeled.append(entity.id)
        elif isinstance(entity, Profile2DEntity):
            if entity.source_line_ids or entity.source_circle_id:
                continue
            unmodeled.append(entity.id)
        elif isinstance(entity, Circle2DEntity):
            unmodeled.append(entity.id)
        else:
            unmodeled.append(entity.id)
    return sorted(unmodeled)


def analyze_constraint_system(
    state: SelectionContext,
    *,
    policy: NumericalTolerancePolicy = DEFAULT_TOLERANCE_POLICY,
) -> SolverAnalysis:
    (
        variable_keys,
        equations,
        fixed_entity_ids,
        supported,
        unsupported,
        invalid,
        grouped,
    ) = _point_equations(state)
    unmodeled = _unmodeled_entities(state)
    redundant: list[str] = []
    conflicting: list[str] = []

    coefficient_rank, augmented_rank = _ranks(equations, variable_keys, policy.linear_rank_abs)
    for constraint_id in supported:
        candidate = [*equations, *grouped[constraint_id]]
        next_coefficient_rank, next_augmented_rank = _ranks(candidate, variable_keys, policy.linear_rank_abs)
        if next_augmented_rank > next_coefficient_rank:
            conflicting.append(constraint_id)
        elif next_coefficient_rank == coefficient_rank:
            redundant.append(constraint_id)
        equations = candidate
        coefficient_rank, augmented_rank = next_coefficient_rank, next_augmented_rank

    inconsistent = augmented_rank > coefficient_rank
    incomplete = bool(unsupported or invalid or unmodeled)
    if not incomplete:
        coverage = "exact"
    elif variable_keys or supported:
        coverage = "partial"
    else:
        coverage = "unknown"

    upper_bound = max(0, len(variable_keys) - coefficient_rank)
    if coverage == "exact" and not inconsistent:
        remaining_dof: int | None = upper_bound
        freedom_state = "fully_constrained" if remaining_dof == 0 else "under_constrained"
    else:
        remaining_dof = None
        freedom_state = "unknown"

    if inconsistent:
        consistency_state = "inconsistent"
    elif unsupported or invalid:
        consistency_state = "unknown"
    else:
        consistency_state = "consistent"

    if redundant:
        redundancy_state = "redundant"
    elif incomplete:
        redundancy_state = "unknown"
    else:
        redundancy_state = "none"

    diagnostics: list[str] = []
    if unsupported:
        diagnostics.append("Nonlinear or unsupported constraints prevent exact DOF classification.")
    if invalid:
        diagnostics.append("Constraints with missing point references were excluded from analysis.")
    if unmodeled:
        diagnostics.append("Entities outside the point-backed linear subset prevent exact whole-sketch DOF classification.")
    if inconsistent:
        diagnostics.append("The supported linear equation system is inconsistent.")
    if redundant:
        diagnostics.append("One or more supported constraints add no independent equation.")

    return SolverAnalysis(
        coverage=coverage,
        freedom_state=freedom_state,
        consistency_state=consistency_state,
        redundancy_state=redundancy_state,
        tracked_variable_count=len(variable_keys),
        independent_equation_count=coefficient_rank,
        remaining_dof=remaining_dof,
        remaining_tracked_dof_upper_bound=upper_bound,
        fixed_entity_ids=fixed_entity_ids,
        supported_constraint_ids=supported,
        unsupported_constraint_ids=unsupported,
        invalid_constraint_ids=invalid,
        redundant_constraint_ids=redundant,
        conflicting_constraint_ids=conflicting,
        unmodeled_entity_ids=unmodeled,
        diagnostics=diagnostics,
        tolerance_policy=policy.to_dict(),
    )
