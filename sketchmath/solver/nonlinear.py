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

    def arc(self, arc_id: str) -> tuple[tuple[float, float], float, float, float]:
        entity = self.entities.get(arc_id)
        if not isinstance(entity, Arc2DEntity):
            raise KeyError(arc_id)
        return (
            (
                self.scalar(f"{arc_id}.center_x", entity.center[0]),
                self.scalar(f"{arc_id}.center_y", entity.center[1]),
            ),
            self.scalar(f"{arc_id}.radius", entity.radius),
            self.scalar(f"{arc_id}.start_angle_deg", entity.start_angle_deg),
            self.scalar(f"{arc_id}.sweep_angle_deg", entity.sweep_angle_deg),
        )

    def circle_like(self, entity_id: str) -> tuple[tuple[float, float], float]:
        entity = self.entities.get(entity_id)
        if isinstance(entity, Circle2DEntity):
            return self.circle(entity_id)
        if isinstance(entity, Arc2DEntity):
            center, radius, _, _ = self.arc(entity_id)
            return center, radius
        raise KeyError(entity_id)

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
        self.degenerate_entity_ids: list[str] = []
        self.post_validators: list[tuple[str, Callable[[_Geometry], bool]]] = []
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
        arcs = {entity.id: entity for entity in self.state.items if isinstance(entity, Arc2DEntity)}
        for arc_id in sorted(arcs):
            arc = arcs[arc_id]
            self._add_variable(f"{arc_id}.center_x", arc.center[0])
            self._add_variable(f"{arc_id}.center_y", arc.center[1])
            self._add_variable(f"{arc_id}.radius", arc.radius)
            self._add_variable(f"{arc_id}.start_angle_deg", arc.start_angle_deg)
            self._add_variable(f"{arc_id}.sweep_angle_deg", arc.sweep_angle_deg)

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
            elif isinstance(entity, Arc2DEntity):
                if entity.locked:
                    self.fixed_entity_ids.append(entity.id)
                    self.groups.append(
                        _ResidualGroup(
                            None,
                            lambda geometry, entity=entity: (
                                self._scaled_length(geometry.arc(entity.id)[0][0] - entity.center[0]),
                                self._scaled_length(geometry.arc(entity.id)[0][1] - entity.center[1]),
                                self._scaled_length(geometry.arc(entity.id)[1] - entity.radius),
                                _wrap_angle(math.radians(geometry.arc(entity.id)[2] - entity.start_angle_deg)),
                                math.radians(geometry.arc(entity.id)[3] - entity.sweep_angle_deg),
                            ),
                        )
                    )
                self._build_arc_linkage_groups(entity)

    def _build_arc_linkage_groups(self, arc: Arc2DEntity) -> None:
        center_entity = self.entities.get(arc.center_point_id or "")
        start_entity = self.entities.get(arc.start_point_id or "")
        end_entity = self.entities.get(arc.end_point_id or "")
        initial_center = center_entity.coords if isinstance(center_entity, Point2DEntity) else arc.center
        if (
            isinstance(start_entity, Point2DEntity)
            and _length(_subtract(start_entity.coords, initial_center)) <= self.policy.coordinate_abs_mm
        ) or (
            isinstance(end_entity, Point2DEntity)
            and _length(_subtract(end_entity.coords, initial_center)) <= self.policy.coordinate_abs_mm
        ) or (
            isinstance(start_entity, Point2DEntity)
            and isinstance(end_entity, Point2DEntity)
            and _length(_subtract(start_entity.coords, end_entity.coords)) <= self.policy.coordinate_abs_mm
        ):
            self.degenerate_entity_ids.append(arc.id)
        if arc.center_point_id and self._points_exist((arc.center_point_id,)):
            self.groups.append(
                _ResidualGroup(
                    None,
                    lambda geometry, arc=arc: (
                        self._scaled_length(geometry.arc(arc.id)[0][0] - geometry.point(arc.center_point_id)[0]),  # type: ignore[arg-type]
                        self._scaled_length(geometry.arc(arc.id)[0][1] - geometry.point(arc.center_point_id)[1]),  # type: ignore[arg-type]
                    ),
                )
            )
        if arc.start_point_id and self._points_exist((arc.start_point_id,)):
            self.groups.append(
                _ResidualGroup(None, lambda geometry, arc=arc: self._arc_endpoint_residual(geometry, arc, start=True))
            )
            self.post_validators.append(
                (
                    arc.id,
                    lambda geometry, arc=arc: _length(_subtract(geometry.point(arc.start_point_id), geometry.arc(arc.id)[0]))  # type: ignore[arg-type]
                    > self.policy.coordinate_abs_mm,
                )
            )
        if arc.end_point_id and self._points_exist((arc.end_point_id,)):
            self.groups.append(
                _ResidualGroup(None, lambda geometry, arc=arc: self._arc_endpoint_residual(geometry, arc, start=False))
            )
            self.post_validators.append(
                (
                    arc.id,
                    lambda geometry, arc=arc: _length(_subtract(geometry.point(arc.end_point_id), geometry.arc(arc.id)[0]))  # type: ignore[arg-type]
                    > self.policy.coordinate_abs_mm,
                )
            )
        if arc.start_point_id and arc.end_point_id and self._points_exist((arc.start_point_id, arc.end_point_id)):
            self.post_validators.append(
                (
                    arc.id,
                    lambda geometry, arc=arc: _length(_subtract(geometry.point(arc.start_point_id), geometry.point(arc.end_point_id)))  # type: ignore[arg-type]
                    > self.policy.coordinate_abs_mm,
                )
            )
        if arc.through_point_id and self._points_exist((arc.through_point_id,)):
            self.groups.append(
                _ResidualGroup(
                    None,
                    lambda geometry, arc=arc: (
                        self._scaled_length(
                            _length(_subtract(geometry.point(arc.through_point_id), geometry.arc(arc.id)[0]))  # type: ignore[arg-type]
                            - geometry.arc(arc.id)[1]
                        ),
                    ),
                )
            )
            self.post_validators.append(
                (
                    arc.id,
                    lambda geometry, arc=arc: self._arc_contains_point(geometry, arc.id, geometry.point(arc.through_point_id)),  # type: ignore[arg-type]
                )
            )

    def _arc_endpoint_residual(self, geometry: _Geometry, arc: Arc2DEntity, *, start: bool) -> tuple[float, float]:
        center, radius, start_angle, sweep = geometry.arc(arc.id)
        angle = start_angle if start else start_angle + sweep
        radians = math.radians(angle)
        expected = (center[0] + radius * math.cos(radians), center[1] + radius * math.sin(radians))
        point_id = arc.start_point_id if start else arc.end_point_id
        actual = geometry.point(point_id)  # type: ignore[arg-type]
        return (self._scaled_length(actual[0] - expected[0]), self._scaled_length(actual[1] - expected[1]))

    @staticmethod
    def _arc_contains_point(geometry: _Geometry, arc_id: str, point: tuple[float, float], tolerance_deg: float = 1e-5) -> bool:
        center, radius, start, sweep = geometry.arc(arc_id)
        if radius <= 0 or _length(_subtract(point, center)) <= 0:
            return False
        angle = math.degrees(math.atan2(point[1] - center[1], point[0] - center[0])) % 360.0
        normalized_start = start % 360.0
        if sweep > 0:
            delta = (angle - normalized_start) % 360.0
            return delta <= sweep + tolerance_deg
        delta = (normalized_start - angle) % 360.0
        return delta <= -sweep + tolerance_deg

    def _points_exist(self, point_ids: Sequence[str]) -> bool:
        return all(isinstance(self.entities.get(point_id), Point2DEntity) for point_id in point_ids)

    def _circle_exists(self, circle_id: str) -> bool:
        return isinstance(self.entities.get(circle_id), Circle2DEntity)

    def _circle_like_exists(self, entity_id: str) -> bool:
        return isinstance(self.entities.get(entity_id), (Circle2DEntity, Arc2DEntity))

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
            if not all(self._circle_like_exists(entity_id) for entity_id in constraint.entities):
                return self._invalid(constraint)
            self._register(
                constraint,
                lambda geometry, constraint=constraint: (
                    self._scaled_length(geometry.circle_like(constraint.entities[1])[0][0] - geometry.circle_like(constraint.entities[0])[0][0]),
                    self._scaled_length(geometry.circle_like(constraint.entities[1])[0][1] - geometry.circle_like(constraint.entities[0])[0][1]),
                ),
            )
            return
        if isinstance(constraint, TangentConstraint):
            first = self.entities.get(constraint.entities[0])
            second = self.entities.get(constraint.entities[1])
            if isinstance(first, (Line2DEntity, ConstructionLine2DEntity)) and isinstance(second, (Circle2DEntity, Arc2DEntity)):
                start, end = _Geometry(self.state, self.variable_index, self.initial_values).line(first.id)
                if _length(_subtract(end, start)) <= self.policy.coordinate_abs_mm:
                    return self._invalid(constraint)

                def line_circle_tangent(geometry: _Geometry, line_id: str = first.id, circle_id: str = second.id) -> tuple[float]:
                    line_start, line_end = geometry.line(line_id)
                    line_vector = _subtract(line_end, line_start)
                    center, radius = geometry.circle_like(circle_id)
                    denominator = max(_length(line_vector), self.policy.coordinate_abs_mm)
                    return (self._scaled_length(abs(_cross(line_vector, _subtract(center, line_start))) / denominator - radius),)

                self._register(constraint, line_circle_tangent)
                if isinstance(second, Arc2DEntity):
                    self.post_validators.append(
                        (
                            constraint.id,
                            lambda geometry, line_id=first.id, arc_id=second.id: self._line_arc_contact_is_finite(geometry, line_id, arc_id),
                        )
                    )
                return
            if isinstance(first, (Circle2DEntity, Arc2DEntity)) and isinstance(second, (Circle2DEntity, Arc2DEntity)):
                target_sign = 1.0 if constraint.tangency == "external" else -1.0

                def circle_tangent(geometry: _Geometry, constraint: TangentConstraint = constraint, target_sign: float = target_sign) -> tuple[float]:
                    first_circle = geometry.circle_like(constraint.entities[0])
                    second_circle = geometry.circle_like(constraint.entities[1])
                    target = first_circle[1] + second_circle[1] if target_sign > 0 else abs(first_circle[1] - second_circle[1])
                    return (self._scaled_length(_length(_subtract(second_circle[0], first_circle[0])) - target),)

                self._register(constraint, circle_tangent)
                if isinstance(first, Arc2DEntity) or isinstance(second, Arc2DEntity):
                    self.post_validators.append(
                        (
                            constraint.id,
                            lambda geometry, constraint=constraint: self._circle_arc_contacts_are_finite(geometry, constraint),
                        )
                    )
                return
            self.unsupported_constraint_ids.append(constraint.id)
            return
        self.unsupported_constraint_ids.append(constraint.id)

    def _classify_entities(self) -> None:
        point_ids = {entity.id for entity in self.state.items if isinstance(entity, Point2DEntity)}
        for entity in self.state.items:
            if isinstance(entity, (Point2DEntity, Circle2DEntity, Arc2DEntity)):
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

    def _line_arc_contact_is_finite(self, geometry: _Geometry, line_id: str, arc_id: str) -> bool:
        start, end = geometry.line(line_id)
        vector = _subtract(end, start)
        denominator = _dot(vector, vector)
        if denominator <= self.policy.coordinate_abs_mm**2:
            return False
        center, _, _, _ = geometry.arc(arc_id)
        parameter = _dot(_subtract(center, start), vector) / denominator
        contact = (start[0] + parameter * vector[0], start[1] + parameter * vector[1])
        return self._arc_contains_point(geometry, arc_id, contact)

    def _circle_arc_contacts_are_finite(self, geometry: _Geometry, constraint: TangentConstraint) -> bool:
        first_center, first_radius = geometry.circle_like(constraint.entities[0])
        second_center, second_radius = geometry.circle_like(constraint.entities[1])
        vector = _subtract(second_center, first_center)
        center_distance = _length(vector)
        if center_distance <= self.policy.coordinate_abs_mm:
            return False
        direction = (vector[0] / center_distance, vector[1] / center_distance)
        if constraint.tangency == "external":
            first_contact = (first_center[0] + direction[0] * first_radius, first_center[1] + direction[1] * first_radius)
            second_contact = (second_center[0] - direction[0] * second_radius, second_center[1] - direction[1] * second_radius)
        elif first_radius >= second_radius:
            first_contact = (first_center[0] + direction[0] * first_radius, first_center[1] + direction[1] * first_radius)
            second_contact = (second_center[0] + direction[0] * second_radius, second_center[1] + direction[1] * second_radius)
        else:
            first_contact = (first_center[0] - direction[0] * first_radius, first_center[1] - direction[1] * first_radius)
            second_contact = (second_center[0] - direction[0] * second_radius, second_center[1] - direction[1] * second_radius)
        first = self.entities[constraint.entities[0]]
        second = self.entities[constraint.entities[1]]
        return (
            not isinstance(first, Arc2DEntity) or self._arc_contains_point(geometry, first.id, first_contact)
        ) and (
            not isinstance(second, Arc2DEntity) or self._arc_contains_point(geometry, second.id, second_contact)
        )

    def failed_post_validators(self, values: Sequence[float]) -> list[str]:
        geometry = _Geometry(self.state, self.variable_index, values)
        return sorted({identifier for identifier, validator in self.post_validators if not validator(geometry)})

    def residual(self, values: Sequence[float]) -> list[float]:
        geometry = _Geometry(self.state, self.variable_index, values)
        result: list[float] = []
        for group in self.groups:
            evaluated = group.evaluate(geometry)
            result.extend(float(value) if math.isfinite(float(value)) else 1e6 for value in evaluated)
        return result

    def bounds(self) -> tuple[list[float], list[float]]:
        lower = [-math.inf] * len(self.variable_keys)
        upper = [math.inf] * len(self.variable_keys)
        for index, key in enumerate(self.variable_keys):
            if key.endswith(".radius"):
                lower[index] = self.policy.coordinate_abs_mm
            elif key.endswith(".sweep_angle_deg"):
                initial = self.initial_values[index]
                if initial > 0:
                    lower[index] = 1e-8
                    upper[index] = 360.0 - 1e-8
                else:
                    lower[index] = -360.0 + 1e-8
                    upper[index] = -1e-8
        return lower, upper

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
        for entity in list(proposed.items):
            if not isinstance(entity, Arc2DEntity):
                continue
            if entity.locked:
                continue
            center = (
                canonical(float(values[self.variable_index[f"{entity.id}.center_x"]])),
                canonical(float(values[self.variable_index[f"{entity.id}.center_y"]])),
            )
            radius = max(self.policy.coordinate_abs_mm, canonical(float(values[self.variable_index[f"{entity.id}.radius"]])))
            start_angle = canonical(float(values[self.variable_index[f"{entity.id}.start_angle_deg"]])) % 360.0
            sweep_angle = canonical(float(values[self.variable_index[f"{entity.id}.sweep_angle_deg"]]))
            proposed.replace_entity(
                Arc2DEntity(
                    **{
                        **entity.model_dump(),
                        "center": center,
                        "radius": radius,
                        "start_angle_deg": start_angle,
                        "sweep_angle_deg": sweep_angle,
                    }
                )
            )
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
        diagnostics.append("Entities outside the point/circle/arc nonlinear subset prevent exact whole-sketch DOF classification.")
    if system.degenerate_entity_ids:
        diagnostics.append(
            "Arc source endpoint degeneracy detected for: " + ", ".join(sorted(set(system.degenerate_entity_ids))) + "."
        )

    initial = np.asarray(system.initial_values, dtype=float)
    lower_bounds, upper_bounds = system.bounds()
    if system.groups:
        candidates = []
        seeds = _deterministic_seeds(np, initial, system.length_scale, policy.nonlinear_seed_perturbation_rel)
        for seed in seeds:
            bounded_seed = np.clip(seed, np.asarray(lower_bounds, dtype=float), np.asarray(upper_bounds, dtype=float))
            result = least_squares(
                system.residual,
                bounded_seed,
                jac="3-point",
                method="trf",
                bounds=(lower_bounds, upper_bounds),
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
    failed_post_validators = sorted(
        set(system.failed_post_validators(solution))
        | set(canonical_system.failed_post_validators(canonical_system.initial_values))
    )
    if canonical_max_abs_residual > max_abs_residual:
        residual_norm = canonical_residual_norm
        max_abs_residual = canonical_max_abs_residual
    feasible_supported = (
        max_abs_residual <= policy.nonlinear_feasibility_abs
        and not failed_post_validators
        and not system.degenerate_entity_ids
    )
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
    constraint_ids = {constraint.id for constraint in state.constraints}
    conflicting.extend(identifier for identifier in failed_post_validators if identifier in constraint_ids and identifier not in conflicting)
    inconsistent = not feasible_supported and not (system.unsupported_constraint_ids or system.invalid_constraint_ids)
    if inconsistent and not conflicting and system.supported_constraint_ids:
        conflicting = [system.supported_constraint_ids[-1]]
    if inconsistent:
        diagnostics.append("Residual validation rejected the optimizer result as inconsistent.")
    if failed_post_validators:
        diagnostics.append(
            "Finite-geometry validation failed for: " + ", ".join(failed_post_validators) + "."
        )
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
