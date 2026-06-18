from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sketchmath.geometry.profiles import analyze_closed_polygon
from sketchmath.geometry.vectors import Point2D
from sketchmath.models.entities import Profile2DEntity


def _load_shapely() -> tuple[Any, Any]:
    try:
        from shapely.geometry import Polygon
        from shapely.geometry.polygon import orient
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError("shapely is required for SketchMath hole validation") from exc
    return Polygon, orient


@dataclass(frozen=True)
class NormalizedProfile:
    id: str
    vertices: list[Point2D]
    area: float
    winding: Literal["clockwise", "counterclockwise"]
    original_winding: str
    warnings: list[str] = field(default_factory=list)
    closed: bool = True


@dataclass(frozen=True)
class ProfileHoleValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    outer: NormalizedProfile | None = None
    holes: list[NormalizedProfile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "outer": None if self.outer is None else {
                "id": self.outer.id,
                "vertices": [list(vertex) for vertex in self.outer.vertices],
                "area": self.outer.area,
                "winding": self.outer.winding,
                "original_winding": self.outer.original_winding,
                "warnings": list(self.outer.warnings),
                "closed": self.outer.closed,
            },
            "holes": [
                {
                    "id": hole.id,
                    "vertices": [list(vertex) for vertex in hole.vertices],
                    "area": hole.area,
                    "winding": hole.winding,
                    "original_winding": hole.original_winding,
                    "warnings": list(hole.warnings),
                    "closed": hole.closed,
                }
                for hole in self.holes
            ],
            "warnings": list(self.warnings),
        }


def _as_points(vertices: list[tuple[float, float]]) -> list[Point2D]:
    return [(float(x), float(y)) for x, y in vertices]


def _polygon_from_profile(profile: Profile2DEntity) -> Polygon:
    Polygon, _ = _load_shapely()
    if not profile.closed:
        raise ValueError(f"Profile {profile.id} must be closed")
    if len(profile.vertices) < 4:
        raise ValueError(f"Profile {profile.id} requires at least three edges")
    return Polygon(profile.vertices[:-1])


def _normalize_profile(profile: Profile2DEntity, *, clockwise: bool) -> NormalizedProfile:
    Polygon, orient = _load_shapely()
    analysis = analyze_closed_polygon(_as_points(profile.vertices))
    polygon = orient(Polygon(_as_points(profile.vertices[:-1])), sign=-1.0 if clockwise else 1.0)
    oriented_vertices = [(float(x), float(y)) for x, y in polygon.exterior.coords]
    original_winding = str(analysis.winding)
    normalized_winding = "clockwise" if clockwise else "counterclockwise"
    warnings = list(analysis.warnings)
    if original_winding != normalized_winding and original_winding != "degenerate":
        warnings.append(f"normalized winding from {original_winding} to {normalized_winding}")
    return NormalizedProfile(
        id=profile.id,
        vertices=oriented_vertices,
        area=float(polygon.area),
        winding=normalized_winding,  # type: ignore[arg-type]
        original_winding=original_winding,
        warnings=warnings,
        closed=True,
    )


def validate_profile_holes(outer: Profile2DEntity, holes: list[Profile2DEntity]) -> ProfileHoleValidationResult:
    try:
        Polygon, _ = _load_shapely()
    except RuntimeError as exc:
        return ProfileHoleValidationResult(
            ok=False,
            error_code="dependency_missing",
            message=str(exc),
            details={"dependency": "shapely"},
        )
    try:
        outer_polygon = _polygon_from_profile(outer)
    except Exception as exc:  # pragma: no cover - defensive normalization
        return ProfileHoleValidationResult(
            ok=False,
            error_code="outer_profile_invalid",
            message=str(exc),
            details={"profile_id": outer.id},
        )

    if not outer_polygon.is_valid or outer_polygon.area <= 0:
        return ProfileHoleValidationResult(
            ok=False,
            error_code="outer_profile_invalid",
            message="Outer profile must be a valid, non-zero-area polygon",
            details={"profile_id": outer.id, "is_valid": bool(outer_polygon.is_valid), "area": float(outer_polygon.area)},
        )

    normalized_outer = _normalize_profile(outer, clockwise=False)
    outer_for_validation = Polygon(normalized_outer.vertices[:-1])

    normalized_holes: list[NormalizedProfile] = []
    hole_polygons: list[Polygon] = []
    for hole in holes:
        try:
            hole_polygon = _polygon_from_profile(hole)
        except Exception as exc:
            return ProfileHoleValidationResult(
                ok=False,
                error_code="hole_profile_invalid",
                message=str(exc),
                details={"profile_id": hole.id},
                outer=normalized_outer,
                holes=list(normalized_holes),
            )
        if not hole_polygon.is_valid or hole_polygon.area <= 0:
            return ProfileHoleValidationResult(
                ok=False,
                error_code="hole_profile_invalid",
                message="Hole profile must be a valid, non-zero-area polygon",
                details={"profile_id": hole.id, "is_valid": bool(hole_polygon.is_valid), "area": float(hole_polygon.area)},
                outer=normalized_outer,
                holes=list(normalized_holes),
            )
        if outer_for_validation.boundary.intersects(hole_polygon.boundary):
            return ProfileHoleValidationResult(
                ok=False,
                error_code="profile_intersection",
                message="Hole must be strictly inside the outer profile and cannot touch its boundary",
                details={"outer_profile_id": outer.id, "hole_profile_id": hole.id},
                outer=normalized_outer,
                holes=list(normalized_holes),
            )
        if not outer_for_validation.contains(hole_polygon):
            if outer_for_validation.touches(hole_polygon):
                error_code = "profile_intersection"
                message = "Hole must be strictly inside the outer profile and cannot touch its boundary"
            else:
                error_code = "hole_outside_outer"
                message = "Hole must lie strictly inside the outer profile"
            return ProfileHoleValidationResult(
                ok=False,
                error_code=error_code,
                message=message,
                details={"outer_profile_id": outer.id, "hole_profile_id": hole.id},
                outer=normalized_outer,
                holes=list(normalized_holes),
            )
        for existing_hole in hole_polygons:
            if existing_hole.intersects(hole_polygon):
                if existing_hole.touches(hole_polygon):
                    error_code = "profile_intersection"
                    message = "Hole profiles cannot touch or overlap"
                else:
                    error_code = "profile_intersection"
                    message = "Hole profiles cannot intersect"
                return ProfileHoleValidationResult(
                    ok=False,
                    error_code=error_code,
                    message=message,
                    details={"outer_profile_id": outer.id, "hole_profile_id": hole.id},
                    outer=normalized_outer,
                    holes=list(normalized_holes),
                )
        normalized_hole = _normalize_profile(hole, clockwise=True)
        normalized_holes.append(normalized_hole)
        hole_polygons.append(Polygon(normalized_hole.vertices[:-1]))

    return ProfileHoleValidationResult(
        ok=True,
        outer=normalized_outer,
        holes=normalized_holes,
        warnings=[warning for profile in [normalized_outer, *normalized_holes] for warning in profile.warnings],
        details={
            "outer_profile_id": outer.id,
            "hole_profile_ids": [hole.id for hole in holes],
            "outer_area": normalized_outer.area,
            "hole_areas": [hole.area for hole in normalized_holes],
            "outer_winding": normalized_outer.original_winding,
            "hole_windings": [hole.original_winding for hole in normalized_holes],
        },
    )
