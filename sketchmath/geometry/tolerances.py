from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NumericalTolerancePolicy:
    """Compatibility-preserving numerical policy for deterministic sketch analysis."""

    version: str = "1.0"
    coordinate_abs_mm: float = 1e-9
    scalar_rel: float = 1e-9
    linear_rank_abs: float = 1e-10

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


DEFAULT_TOLERANCE_POLICY = NumericalTolerancePolicy()
