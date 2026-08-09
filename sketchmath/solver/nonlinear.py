from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Sequence

from sketchmath.geometry.tolerances import DEFAULT_TOLERANCE_POLICY, NumericalTolerancePolicy
from sketchmath.geometry.units import normalize_angle, normalize_length
from sketchmath.models.constraints import (
    AngleConstraint,
    CoincidentConstraint,
    CollinearConstraint,
    ConcentricConstraint,
    ConstraintEntity,
    DiameterConstraint,
    DistanceConstraint,
    EqualAngleConstraint,
    EqualLengthConstraint,
    FixedPointConstraint,
    HorizontalConstraint,
    HorizontalDistanceConstraint,
    MidpointConstraint,
    ParallelConstraint,
    PerpendicularConstraint,
    RadiusConstraint,
    SymmetricConstraint,
    TangentConstraint,
    VerticalConstraint,
    VerticalDistanceConstraint,
)
from sketchmath.models.entities import (
    Arc2DEntity,
    Circle2DEntity,
    ConstructionLine2DEntity,
    Line2DEntity,
    Point2DEntity,
    Profile2DEntity,
)
from sketchmath.models.selection_context import SelectionContext
from sketchmath.models.solver_analysis import SolverAnalysis


ResidualFunction = Callable[["_Geometry"], Sequence[float]]


@dataclass(frozen=True)
class _ResidualGroup:
    constraint_id: str | None
    evaluate: ResidualFunction


@dataclass(frozen=True)
class NonlinearEvaluation:
    available: bool
    backend: str
    analysis: SolverAnalysis
    proposed_state: SelectionContext
    changed_entity_ids: list[str]
    feasible: bool | None
    residual_norm: float | None
    max_abs_residual: float | None
    residual_count: int
    variable_order: list[str]
    jacobian_rank: int
    function_evaluations: int
    jacobian_evaluations: int | None
    seed_count: int
    characteristic_length_mm: float
    optimizer_success: bool | None
    termination_reason: str
    diagnostics: list[str]


def _wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def _cross(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _subtract(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (a[0] - b[0], a[1] - b[1])


def _length(vector: tuple[float, float]) -> float:
    return math.hypot(vector[0], vector[1])


class _Geometry:
    def __init__(self, state: SelectionContext, variable_index: dict[str, int], values: Sequence[float]) -> None:
        self.state = state
        self.variable_index = variable_index
        self.values = values
        self.entities = state.entity_map()

    def scalar(self, key: str, fallback: float) -> float:
        index = self.variable_index.get(key)
        return float(self.values[index]) if index is not None else float(fallback)

    def point(self, point_id: str) -> tuple[float, float]:
        entity = self.entities.get(point_id)
        if not isinstance(entity, Point2DEntity):
            raise KeyError(point_id)
        return (
            self.scalar(f"{point_id}.x", entity.coords[0]),
            self.scalar(f"{point_id}.y", entity.coords[1]),
        )

    def circle(self, circle_id: str) -> tuple[tuple[float, float], float]:
        entity = self.entities.get(circle_id)
        if not isinstance(entity, Circle2DEntity):
            raise KeyError(circle_id)
        if entity.center_point_id and isinstance(self.entities.get(entity.center_point_id), Point2DEntity):
            center = self.point(entity.center_point_id)
        else:
            center = (
                self.scalar(f"{circle_id}.center_x", entity.center[0]),
                self.scalar(f"{circle_id}.center_y", entity.center[1]),
            )
        return center, self.scalar(f"{circle_id}.radius", entity.radius)

    def line(self, line_id: str) -> tuple[tuple[float, float], tuple[float, float]]:
        entity = self.entities.get(line_id)
        if not isinstance(entity, (Line2DEntity, ConstructionLine2DEntity)):
            raise KeyError(line_id)
        start = self.point(entity.start_point_id) if entity.start_point_id else entity.start
        end = self.point(entity.end_point_id) if entity.end_point_id else entity.end
        return start, end


class _System:
    def __init__(self, state: SelectionContext, policy: NumericalTolerancePolicy) -> None:
        self.state = state
        self.policy = policy
        self.entities = state.entity_map()
        self.variable_keys: list[str] = []
        self.initial_values: list[float] = []
        self.fixed_entity_ids: list[str] = []
        self.groups: list[_ResidualGroup] = []
        self.supported_constraint_ids: list[str] = []
        self.unsupported_constraint_ids: list[str] = []
        self.invalid_constraint_ids: list[str] = []
        self.unmodeled_entity_ids: list[str] = []
        self.length_scale = self._characteristic_length()
        self._build_variables()
        self.variable_index = {key: index for index, key in enumerate(self.variable_keys)}
        self._build_implicit_groups()
        self._build_constraint_groups()
        self._classify_entities()

    def _characteristic_length(self) -> float:
        coordinates: list[tuple[float, float]] = []
        lengths: list[float] = [1.0]
        for entity in self.state.items:
            if isinstance(entity, Point2DEntity):
                coordinates.append(entity.coords)
            elif isinstance(entity, (Line2DEntity, ConstructionLine2DEntity)):
                coordinates.extend((entity.start, entity.end))
            elif isinstance(entity, (Circle2DEntity, Arc2DEntity)):
                coordinates.append(entity.center)
                lengths.append(entity.radius)
        if coordinates:
            xs = [point[0] for point in coordinates]
            ys = [point[1] for point in coordinates]
            lengths.extend((max(xs) - min(xs), max(ys) - min(ys)))
        for constraint in self.state.constraints:
            try:
                if isinstance(constraint, DistanceConstraint):
                    lengths.append(normalize_length(constraint.distance, constraint.unit))
                elif isinstance(constraint, (HorizontalDistanceConstraint, VerticalDistanceConstraint)):
                    lengths.append(normalize_length(constraint.distance, constraint.unit))
                elif isinstance(constraint, RadiusConstraint):
                    lengths.append(normalize_length(constraint.radius, constraint.unit))
                elif isinstance(constraint, DiameterConstraint):
                    lengths.append(normalize_length(constraint.diameter, constraint.unit))
            except ValueError:
                pass
        return max(1.0, *(abs(value) for value in lengths if math.isfinite(value)))

    def _add_variable(self, key: str, value: float) -> None:
        self.variable_keys.append(key)
        self.initial_values.append(float(value))

    def _build_variables(self) -> None:
        points = {entity.id: entity for entity in self.state.items if isinstance(entity, Point2DEntity)}
        for point_id in sorted(points):
            point = points[point_id]
            self._add_variable(f"{point_id}.x", point.coords[0])
            self._add_variable(f"{point_id}.y", point.coords[1])
        circles = {entity.id: entity for entity in self.state.items if isinstance(entity, Circle2DEntity)}
        for circle_id in sorted(circles):
            circle = circles[circle_id]
            if not circle.center_point_id or circle.center_point_id not in points:
                self._add_variable(f"{circle_id}.center_x", circle.center[0])
                self._add_variable(f"{circle_id}.center_y", circle.center[1])
            self._add_variable(f"{circle_id}.radius", circle.radius)

    def _scaled_length(self, value: float) -> float:
        return value / self.length_scale

    def _build_implicit_groups(self) -> None:
        for entity in sorted(self.state.items, key=lambda item: item.id):
            if isinstance(entity, Point2DEntity) and entity.locked:
                self.fixed_entity_ids.append(entity.id)
                self.groups.append(
                    _ResidualGroup(
                        None,
                        lambda geometry, entity=entity: (
                            self._scaled_length(geometry.point(entity.id)[0] - entity.coords[0]),
                            self._scaled_length(geometry.point(entity.id)[1] - entity.coords[1]),
                        ),
                    )
                )
            elif isinstance(entity, Circle2DEntity) and entity.locked:
                self.fixed_entity_ids.append(entity.id)
                self.groups.append(
                    _ResidualGroup(
                        None,
                        lambda geometry, entity=entity: (
                            self._scaled_length(geometry.circle(entity.id)[0][0] - entity.center[0]),
                            self._scaled_length(geometry.circle(entity.id)[0][1] - entity.center[1]),
                            self._scaled_length(geometry.circle(entity.id)[1] - entity.radius),
                        ),
                    )
                )

    def _points_exist(self, point_ids: Sequence[str]) -> bool:
        return all(isinstance(self.entities.get(point_id), Point2DEntity) for point_id in point_ids)

    def _circle_exists(self, circle_id: str) -> bool:
        return isinstance(self.entities.get(circle_id), Circle2DEntity)

    def _register(self, constraint: ConstraintEntity, function: ResidualFunction) -> None:
        self.supported_constraint_ids.append(constraint.id)
        self.groups.append(_ResidualGroup(constraint.id, function))

    def _invalid(self, constraint: ConstraintEntity) -> None:
        self.invalid_constraint_ids.append(constraint.id)

    def _build_constraint_groups(self) -> None:
        for constraint in sorted(self.state.constraints, key=lambda item: item.id):
            try:
                self._build_constraint_group(constraint)
            except (KeyError, ValueError, ZeroDivisionError):
                self._invalid(constraint)

    def _build_constraint_group(self, constraint: ConstraintEntity) -> None:
        if isinstance(constraint, FixedPointConstraint):
            if not self._points_exist((constraint.point_id,)):
                return self._invalid(constraint)
            self._register(
                constraint,
                lambda geometry, constraint=constraint: (
                    self._scaled_length(geometry.point(constraint.point_id)[0] - constraint.coords[0]),
                    self._scaled_length(geometry.point(constraint.point_id)[1] - constraint.coords[1]),
                ),
            )
            return
        if isinstance(constraint, (HorizontalConstraint, VerticalConstraint, CoincidentConstraint, DistanceConstraint, HorizontalDistanceConstraint, VerticalDistanceConstraint)):
            if not self._points_exist(constraint.points):
                return self._invalid(constraint)
            if isinstance(constraint, HorizontalConstraint):
                self._register(constraint, lambda geometry, constraint=constraint: (self._scaled_length(geometry.point(constraint.points[1])[1] - geometry.point(constraint.points[0])[1]),))
            elif isinstance(constraint, VerticalConstraint):
                self._register(constraint, lambda geometry, constraint=constraint: (self._scaled_length(geometry.point(constraint.points[1])[0] - geometry.point(constraint.points[0])[0]),))
            elif isinstance(constraint, CoincidentConstraint):
                self._register(
                    constraint,
                    lambda geometry, constraint=constraint: (
                        self._scaled_length(geometry.point(constraint.points[1])[0] - geometry.point(constraint.points[0])[0]),
                        self._scaled_length(geometry.point(constraint.points[1])[1] - geometry.point(constraint.points[0])[1]),
                    ),
                )
            elif isinstance(constraint, DistanceConstraint):
                target = normalize_length(constraint.distance, constraint.unit)
                self._register(
                    constraint,
                    lambda geometry, constraint=constraint, target=target: (
                        self._scaled_length(_length(_subtract(geometry.point(constraint.points[1]), geometry.point(constraint.points[0]))) - target),
                    ),
                )
            else:
                target = normalize_length(constraint.distance, constraint.unit) * constraint.direction
                axis = 0 if isinstance(constraint, HorizontalDistanceConstraint) else 1
                self._register(
                    constraint,
                    lambda geometry, constraint=constraint, target=target, axis=axis: (
                        self._scaled_length(geometry.point(constraint.points[1])[axis] - geometry.point(constraint.points[0])[axis] - target),
                    ),
                )
            return
        if isinstance(constraint, (RadiusConstraint, DiameterConstraint)):
            if not self._circle_exists(constraint.circle_id):
                return self._invalid(constraint)
            target = normalize_length(
                constraint.radius if isinstance(constraint, RadiusConstraint) else constraint.diameter / 2.0,
                constraint.unit,
            )
            self._register(
                constraint,
                lambda geometry, constraint=constraint, target=target: (self._scaled_length(geometry.circle(constraint.circle_id)[1] - target),),
            )
            return
        if isinstance(constraint, AngleConstraint):
            if not self._points_exist(constraint.points):
                return self._invalid(constraint)
            target = normalize_angle(constraint.angle, constraint.unit)
            self._register(
                constraint,
                lambda geometry, constraint=constraint, target=target: (
                    _wrap_angle(
                        math.atan2(
                            _cross(
                                _subtract(geometry.point(constraint.points[0]), geometry.point(constraint.points[1])),
                                _subtract(geometry.point(constraint.points[2]), geometry.point(constraint.points[1])),
                            ),
                            _dot(
                                _subtract(geometry.point(constraint.points[0]), geometry.point(constraint.points[1])),
                                _subtract(geometry.point(constraint.points[2]), geometry.point(constraint.points[1])),
                            ),
                        )
                        - target
                    ),
                ),
            )
            return
        if isinstance(constraint, (ParallelConstraint, PerpendicularConstraint, EqualLengthConstraint)):
            if not self._points_exist(constraint.points):
                return self._invalid(constraint)

            def segment_vectors(geometry: _Geometry, constraint: ConstraintEntity = constraint) -> tuple[tuple[float, float], tuple[float, float]]:
                points = constraint.points  # type: ignore[union-attr]
                return _subtract(geometry.point(points[1]), geometry.point(points[0])), _subtract(geometry.point(points[3]), geometry.point(points[2]))

            if isinstance(constraint, ParallelConstraint):
                def parallel(geometry: _Geometry, constraint: ConstraintEntity = constraint) -> tuple[float]:
                    first, second = segment_vectors(geometry, constraint)
                    denominator = max(_length(first) * _length(second), self.policy.coordinate_abs_mm**2)
                    return (_cross(first, second) / denominator,)

                self._register(constraint, parallel)
            elif isinstance(constraint, PerpendicularConstraint):
                def perpendicular(geometry: _Geometry, constraint: ConstraintEntity = constraint) -> tuple[float]:
                    first, second = segment_vectors(geometry, constraint)
                    denominator = max(_length(first) * _length(second), self.policy.coordinate_abs_mm**2)
                    return (_dot(first, second) / denominator,)

                self._register(constraint, perpendicular)
            else:
                self._register(
                    constraint,
                    lambda geometry, constraint=constraint: (
                        self._scaled_length(_length(segment_vectors(geometry, constraint)[0]) - _length(segment_vectors(geometry, constraint)[1])),
                    ),
                )
            return
        if isinstance(constraint, EqualAngleConstraint):
            if not self._points_exist(constraint.points):
                return self._invalid(constraint)

            def equal_angle(geometry: _Geometry, constraint: EqualAngleConstraint = constraint) -> tuple[float]:
                def angle(ids: Sequence[str]) -> float:
                    first = _subtract(geometry.point(ids[0]), geometry.point(ids[1]))
                    second = _subtract(geometry.point(ids[2]), geometry.point(ids[1]))
                    return math.atan2(_cross(first, second), _dot(first, second))

                return (_wrap_angle(angle(constraint.points[:3]) - angle(constraint.points[3:])),)

            self._register(constraint, equal_angle)
            return
        if isinstance(constraint, MidpointConstraint):
            if not self._points_exist((constraint.point_id, *constraint.line_points)):
                return self._invalid(constraint)
            self._register(
                constraint,
                lambda geometry, constraint=constraint: (
                    self._scaled_length(geometry.point(constraint.point_id)[0] - (geometry.point(constraint.line_points[0])[0] + geometry.point(constraint.line_points[1])[0]) / 2.0),
                    self._scaled_length(geometry.point(constraint.point_id)[1] - (geometry.point(constraint.line_points[0])[1] + geometry.point(constraint.line_points[1])[1]) / 2.0),
                ),
            )
            return
        if isinstance(constraint, CollinearConstraint):
            if not self._points_exist(constraint.points):
                return self._invalid(constraint)

            def collinear(geometry: _Geometry, constraint: CollinearConstraint = constraint) -> tuple[float]:
                reference = _subtract(geometry.point(constraint.points[1]), geometry.point(constraint.points[0]))
                offset = _subtract(geometry.point(constraint.points[2]), geometry.point(constraint.points[0]))
                denominator = max(_length(reference), self.policy.coordinate_abs_mm)
                return (self._scaled_length(_cross(reference, offset) / denominator),)

            self._register(constraint, collinear)
            return
        if isinstance(constraint, SymmetricConstraint):
            if not self._points_exist(constraint.points):
                return self._invalid(constraint)

            def symmetric(geometry: _Geometry, constraint: SymmetricConstraint = constraint) -> tuple[float, float]:
                reference = geometry.point(constraint.points[0])
                target = geometry.point(constraint.points[1])
                axis_start = geometry.point(constraint.points[2])
                axis = _subtract(geometry.point(constraint.points[3]), axis_start)
                denominator = max(_dot(axis, axis), self.policy.coordinate_abs_mm**2)
                projection_scale = _dot(_subtract(reference, axis_start), axis) / denominator
                projection = (axis_start[0] + projection_scale * axis[0], axis_start[1] + projection_scale * axis[1])
                reflected = (2.0 * projection[0] - reference[0], 2.0 * projection[1] - reference[1])
                return (self._scaled_length(target[0] - reflected[0]), self._scaled_length(target[1] - reflected[1]))

            self._register(constraint, symmetric)
            return
        if isinstance(constraint, ConcentricConstraint):
            if not all(self._circle_exists(entity_id) for entity_id in constraint.entities):
                self.unsupported_constraint_ids.append(constraint.id)
                return
            self._register(
                constraint,
                lambda geometry, constraint=constraint: (
                    self._scaled_length(geometry.circle(constraint.entities[1])[0][0] - geometry.circle(constraint.entities[0])[0][0]),
                    self._scaled_length(geometry.circle(constraint.entities[1])[0][1] - geometry.circle(constraint.entities[0])[0][1]),
                ),
            )
            return
        if isinstance(constraint, TangentConstraint):
            first = self.entities.get(constraint.entities[0])
            second = self.entities.get(constraint.entities[1])
            if isinstance(first, (Line2DEntity, ConstructionLine2DEntity)) and isinstance(second, Circle2DEntity):
                start, end = _Geometry(self.state, self.variable_index, self.initial_values).line(first.id)
                if _length(_subtract(end, start)) <= self.policy.coordinate_abs_mm:
                    return self._invalid(constraint)

                def line_circle_tangent(geometry: _Geometry, line_id: str = first.id, circle_id: str = second.id) -> tuple[float]:
                    line_start, line_end = geometry.line(line_id)
                    line_vector = _subtract(line_end, line_start)
                    center, radius = geometry.circle(circle_id)
                    denominator = max(_length(line_vector), self.policy.coordinate_abs_mm)
                    return (self._scaled_length(abs(_cross(line_vector, _subtract(center, line_start))) / denominator - radius),)

                self._register(constraint, line_circle_tangent)
                return
            if isinstance(first, Circle2DEntity) and isinstance(second, Circle2DEntity):
                target_sign = 1.0 if constraint.tangency == "external" else -1.0

                def circle_tangent(geometry: _Geometry, constraint: TangentConstraint = constraint, target_sign: float = target_sign) -> tuple[float]:
                    first_circle = geometry.circle(constraint.entities[0])
                    second_circle = geometry.circle(constraint.entities[1])
                    target = first_circle[1] + second_circle[1] if target_sign > 0 else abs(first_circle[1] - second_circle[1])
                    return (self._scaled_length(_length(_subtract(second_circle[0], first_circle[0])) - target),)

                self._register(constraint, circle_tangent)
                return
            self.unsupported_constraint_ids.append(constraint.id)
            return
        self.unsupported_constraint_ids.append(constraint.id)

    def _classify_entities(self) -> None:
        point_ids = {entity.id for entity in self.state.items if isinstance(entity, Point2DEntity)}
        for entity in self.state.items:
            if isinstance(entity, (Point2DEntity, Circle2DEntity)):
                continue
            if isinstance(entity, (Line2DEntity, ConstructionLine2DEntity)):
                if entity.start_point_id in point_ids and entity.end_point_id in point_ids:
                    continue
                self.unmodeled_entity_ids.append(entity.id)
            elif isinstance(entity, Profile2DEntity):
                if entity.source_line_ids or entity.source_circle_id:
                    continue
                self.unmodeled_entity_ids.append(entity.id)
            else:
                self.unmodeled_entity_ids.append(entity.id)
        self.unmodeled_entity_ids.sort()

    def residual(self, values: Sequence[float]) -> list[float]:
        geometry = _Geometry(self.state, self.variable_index, values)
        result: list[float] = []
        for group in self.groups:
            evaluated = group.evaluate(geometry)
            result.extend(float(value) if math.isfinite(float(value)) else 1e6 for value in evaluated)
        return result

    def group_residuals(self, values: Sequence[float]) -> list[tuple[_ResidualGroup, list[float]]]:
        geometry = _Geometry(self.state, self.variable_index, values)
        return [(group, [float(value) for value in group.evaluate(geometry)]) for group in self.groups]

    def proposed_state(self, values: Sequence[float]) -> tuple[SelectionContext, list[str]]:
        proposed = self.state.model_copy(deep=True)
        proposed_map = proposed.entity_map()

        def canonical(value: float) -> float:
            rounded = round(float(value), 9)
            return 0.0 if abs(rounded) <= self.policy.coordinate_abs_mm else rounded

        for entity in list(proposed.items):
            if isinstance(entity, Point2DEntity):
                coords = entity.coords if entity.locked else (
                    canonical(float(values[self.variable_index[f"{entity.id}.x"]])),
                    canonical(float(values[self.variable_index[f"{entity.id}.y"]])),
                )
                proposed.replace_entity(Point2DEntity(**{**entity.model_dump(), "coords": coords}))
        proposed_map = proposed.entity_map()
        for entity in list(proposed.items):
            if not isinstance(entity, Circle2DEntity):
                continue
            if entity.locked:
                center = entity.center
                radius = entity.radius
            elif entity.center_point_id and isinstance(proposed_map.get(entity.center_point_id), Point2DEntity):
                center = proposed_map[entity.center_point_id].coords  # type: ignore[union-attr]
                radius = max(self.policy.coordinate_abs_mm, canonical(float(values[self.variable_index[f"{entity.id}.radius"]])))
            else:
                center = (
                    canonical(float(values[self.variable_index[f"{entity.id}.center_x"]])),
                    canonical(float(values[self.variable_index[f"{entity.id}.center_y"]])),
                )
                radius = max(self.policy.coordinate_abs_mm, canonical(float(values[self.variable_index[f"{entity.id}.radius"]])))
            proposed.replace_entity(Circle2DEntity(**{**entity.model_dump(), "center": center, "radius": radius}))
        proposed_map = proposed.entity_map()
        for entity in list(proposed.items):
            if isinstance(entity, (Line2DEntity, ConstructionLine2DEntity)):
                start = proposed_map.get(entity.start_point_id or "")
                end = proposed_map.get(entity.end_point_id or "")
                if isinstance(start, Point2DEntity) or isinstance(end, Point2DEntity):
                    proposed.replace_entity(
                        type(entity)(
                            **{
                                **entity.model_dump(),
                                "start": start.coords if isinstance(start, Point2DEntity) else entity.start,
                                "end": end.coords if isinstance(end, Point2DEntity) else entity.end,
                            }
                        )
                    )
        before = self.state.entity_map()
        changed = sorted(
            entity.id
            for entity in proposed.items
            if entity.id in before and entity.model_dump(mode="json") != before[entity.id].model_dump(mode="json")
        )
        return proposed, changed


def _central_jacobian(np: object, function: Callable[[Sequence[float]], Sequence[float]], values: Sequence[float]) -> object:
    vector = np.asarray(values, dtype=float)  # type: ignore[attr-defined]
    baseline = np.asarray(function(vector), dtype=float)  # type: ignore[attr-defined]
    jacobian = np.zeros((len(baseline), len(vector)), dtype=float)  # type: ignore[attr-defined]
    epsilon = math.sqrt(float(np.finfo(float).eps))  # type: ignore[attr-defined]
    for index in range(len(vector)):
        step = epsilon * max(1.0, abs(float(vector[index])))
        plus = vector.copy()
        minus = vector.copy()
        plus[index] += step
        minus[index] -= step
        jacobian[:, index] = (np.asarray(function(plus), dtype=float) - np.asarray(function(minus), dtype=float)) / (2.0 * step)  # type: ignore[attr-defined]
    return jacobian


def _rank(np: object, matrix: object, tolerance: float) -> int:
    if getattr(matrix, "size", 0) == 0:
        return 0
    singular_values = np.linalg.svd(matrix, compute_uv=False)  # type: ignore[attr-defined]
    if not len(singular_values):
        return 0
    threshold = max(tolerance, tolerance * max(matrix.shape) * float(singular_values[0]))
    return int(np.sum(singular_values > threshold))  # type: ignore[attr-defined]


def _deterministic_seeds(np: object, initial: Sequence[float], scale: float, perturbation_rel: float) -> list[object]:
    base = np.asarray(initial, dtype=float)  # type: ignore[attr-defined]
    seeds = [base]
    if len(base):
        magnitude = max(1e-6, scale * perturbation_rel)
        forward = base.copy()
        reverse = base.copy()
        for index in range(len(base)):
            direction = 1.0 if index % 2 == 0 else -1.0
            forward[index] += direction * magnitude * (1.0 + index / max(1, len(base)))
            reverse[index] -= direction * magnitude * (1.0 + index / max(1, len(base)))
        seeds.extend((forward, reverse))
    return seeds


def evaluate_nonlinear_system(
    state: SelectionContext,
    *,
    policy: NumericalTolerancePolicy = DEFAULT_TOLERANCE_POLICY,
) -> NonlinearEvaluation | None:
    try:
        import numpy as np
        from scipy.optimize import least_squares
    except ImportError:
        return None

    system = _System(state, policy)
    incomplete = bool(system.unsupported_constraint_ids or system.invalid_constraint_ids or system.unmodeled_entity_ids)
    coverage = "exact" if not incomplete else "partial" if system.variable_keys or system.supported_constraint_ids else "unknown"
    diagnostics: list[str] = []
    if system.unsupported_constraint_ids:
        diagnostics.append("Unsupported constraint families were excluded from nonlinear analysis.")
    if system.invalid_constraint_ids:
        diagnostics.append("Degenerate constraints or constraints with invalid references were excluded from nonlinear analysis.")
    if system.unmodeled_entity_ids:
        diagnostics.append("Entities outside the point/circle nonlinear subset prevent exact whole-sketch DOF classification.")

    initial = np.asarray(system.initial_values, dtype=float)
    if system.groups:
        candidates = []
        seeds = _deterministic_seeds(np, initial, system.length_scale, policy.nonlinear_seed_perturbation_rel)
        for seed in seeds:
            result = least_squares(
                system.residual,
                seed,
                jac="3-point",
                method="trf",
                x_scale="jac",
                ftol=1e-12,
                xtol=1e-12,
                gtol=1e-12,
                max_nfev=int(policy.nonlinear_max_evaluations),
            )
            residual = np.asarray(system.residual(result.x), dtype=float)
            max_abs = float(np.max(np.abs(residual))) if residual.size else 0.0
            norm = float(np.linalg.norm(residual))
            displacement = float(np.linalg.norm(result.x - initial))
            candidates.append((max_abs, norm, displacement, tuple(float(value) for value in result.x), result))
        _, _, _, _, optimizer = min(candidates, key=lambda item: (item[0] > policy.nonlinear_feasibility_abs, item[0], item[1], item[2], item[3]))
        solution = optimizer.x
        residual = np.asarray(system.residual(solution), dtype=float)
        residual_norm = float(np.linalg.norm(residual))
        max_abs_residual = float(np.max(np.abs(residual))) if residual.size else 0.0
        optimizer_success = bool(optimizer.success)
        optimizer_message = str(optimizer.message)
        function_evaluations = int(optimizer.nfev)
        jacobian_evaluations = int(optimizer.njev) if optimizer.njev is not None else None
        seed_count = len(seeds)
    else:
        solution = initial
        residual = np.asarray([], dtype=float)
        residual_norm = 0.0
        max_abs_residual = 0.0
        optimizer_success = True
        optimizer_message = "No residual equations."
        function_evaluations = 0
        jacobian_evaluations = 0
        seed_count = 1

    proposed, changed = system.proposed_state(solution)
    canonical_system = _System(proposed, policy)
    canonical_residual = np.asarray(canonical_system.residual(canonical_system.initial_values), dtype=float)
    canonical_residual_norm = float(np.linalg.norm(canonical_residual)) if canonical_residual.size else 0.0
    canonical_max_abs_residual = float(np.max(np.abs(canonical_residual))) if canonical_residual.size else 0.0
    if canonical_max_abs_residual > max_abs_residual:
        residual_norm = canonical_residual_norm
        max_abs_residual = canonical_max_abs_residual
    feasible_supported = max_abs_residual <= policy.nonlinear_feasibility_abs
    jacobian = _central_jacobian(np, system.residual, solution)
    independent_equations = _rank(np, jacobian, policy.nonlinear_rank_rel)
    redundant: list[str] = []
    row_count = 0
    rank_before = 0
    for group, values in system.group_residuals(solution):
        next_row_count = row_count + len(values)
        if group.constraint_id is not None:
            rank_after = _rank(np, jacobian[:next_row_count, :], policy.nonlinear_rank_rel)
            if rank_after == rank_before and max((abs(value) for value in values), default=0.0) <= policy.nonlinear_feasibility_abs:
                redundant.append(group.constraint_id)
            rank_before = rank_after
        else:
            rank_before = _rank(np, jacobian[:next_row_count, :], policy.nonlinear_rank_rel)
        row_count = next_row_count

    conflicting = [
        group.constraint_id
        for group, values in system.group_residuals(solution)
        if group.constraint_id is not None and max((abs(value) for value in values), default=0.0) > policy.nonlinear_feasibility_abs
    ]
    inconsistent = not feasible_supported and not (system.unsupported_constraint_ids or system.invalid_constraint_ids)
    if inconsistent and not conflicting and system.supported_constraint_ids:
        conflicting = [system.supported_constraint_ids[-1]]
    if inconsistent:
        diagnostics.append("Residual validation rejected the optimizer result as inconsistent.")
    if redundant:
        diagnostics.append("One or more constraints add no independent equation at the converged solution.")
    if optimizer_success and not feasible_supported:
        diagnostics.append("Optimizer termination was successful, but constraint residuals were not feasible.")
    diagnostics.append(f"Nonlinear residuals are normalized by characteristic length {system.length_scale:.12g} mm; angular residuals use radians.")
    diagnostics.append(f"SciPy termination: {optimizer_message}")

    upper_bound = max(0, len(system.variable_keys) - independent_equations)
    if coverage == "exact" and not inconsistent:
        remaining_dof: int | None = upper_bound
        freedom_state = "fully_constrained" if upper_bound == 0 else "under_constrained"
    else:
        remaining_dof = None
        freedom_state = "unknown"
    if inconsistent:
        consistency_state = "inconsistent"
    elif system.unsupported_constraint_ids or system.invalid_constraint_ids:
        consistency_state = "unknown"
    else:
        consistency_state = "consistent"
    redundancy_state = "redundant" if redundant else "unknown" if incomplete else "none"
    analysis = SolverAnalysis(
        coverage=coverage,
        freedom_state=freedom_state,
        consistency_state=consistency_state,
        redundancy_state=redundancy_state,
        tracked_variable_count=len(system.variable_keys),
        independent_equation_count=independent_equations,
        remaining_dof=remaining_dof,
        remaining_tracked_dof_upper_bound=upper_bound,
        fixed_entity_ids=system.fixed_entity_ids,
        supported_constraint_ids=system.supported_constraint_ids,
        unsupported_constraint_ids=system.unsupported_constraint_ids,
        invalid_constraint_ids=system.invalid_constraint_ids,
        redundant_constraint_ids=redundant,
        conflicting_constraint_ids=conflicting,
        unmodeled_entity_ids=system.unmodeled_entity_ids,
        diagnostics=diagnostics,
        tolerance_policy=policy.to_dict(),
    )
    if incomplete:
        feasible: bool | None = None
        termination_reason = "nonlinear_coverage_partial"
    elif inconsistent:
        feasible = False
        termination_reason = "nonlinear_residual_infeasible"
    else:
        feasible = True
        termination_reason = "nonlinear_residual_feasible"
    return NonlinearEvaluation(
        available=True,
        backend="scipy_least_squares_v1",
        analysis=analysis,
        proposed_state=proposed,
        changed_entity_ids=changed,
        feasible=feasible,
        residual_norm=residual_norm,
        max_abs_residual=max_abs_residual,
        residual_count=len(residual),
        variable_order=list(system.variable_keys),
        jacobian_rank=independent_equations,
        function_evaluations=function_evaluations,
        jacobian_evaluations=jacobian_evaluations,
        seed_count=seed_count,
        characteristic_length_mm=system.length_scale,
        optimizer_success=optimizer_success,
        termination_reason=termination_reason,
        diagnostics=diagnostics,
    )
