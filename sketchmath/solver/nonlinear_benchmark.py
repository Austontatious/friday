from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import metadata, version
import json
import math
from pathlib import Path
import platform
from statistics import median
from time import perf_counter
from typing import Any, Callable


VectorFunction = Callable[[Any], Any]


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    initial: tuple[float, float]
    probe: tuple[float, float]
    residual: VectorFunction
    jacobian: VectorFunction
    expected_feasible: bool
    degeneracy: str | None = None


def _distance_row(np: Any, point: Any, center: tuple[float, float]) -> Any:
    delta = point - np.asarray(center, dtype=float)
    length = float(np.linalg.norm(delta))
    return delta / length if length > 1e-12 else np.zeros(2, dtype=float)


def _cases(np: Any) -> list[BenchmarkCase]:
    def triangle_residual(point: Any) -> Any:
        return np.asarray(
            [np.linalg.norm(point - np.asarray((0.0, 0.0))) - 3.0, np.linalg.norm(point - np.asarray((4.0, 0.0))) - 5.0]
        )

    def triangle_jacobian(point: Any) -> Any:
        return np.vstack([_distance_row(np, point, (0.0, 0.0)), _distance_row(np, point, (4.0, 0.0))])

    def parallel_length_residual(point: Any) -> Any:
        delta = point - np.asarray((1.0, 1.0))
        return np.asarray([delta[1], np.linalg.norm(delta) - 4.0])

    def parallel_length_jacobian(point: Any) -> Any:
        return np.vstack([np.asarray((0.0, 1.0)), _distance_row(np, point, (1.0, 1.0))])

    tangent_offset = 1.999999

    def near_tangent_residual(point: Any) -> Any:
        return np.asarray(
            [np.linalg.norm(point) - 1.0, np.linalg.norm(point - np.asarray((tangent_offset, 0.0))) - 1.0]
        )

    def near_tangent_jacobian(point: Any) -> Any:
        return np.vstack([_distance_row(np, point, (0.0, 0.0)), _distance_row(np, point, (tangent_offset, 0.0))])

    def inconsistent_residual(point: Any) -> Any:
        return np.asarray(
            [np.linalg.norm(point) - 1.0, np.linalg.norm(point - np.asarray((10.0, 0.0))) - 1.0]
        )

    def inconsistent_jacobian(point: Any) -> Any:
        return np.vstack([_distance_row(np, point, (0.0, 0.0)), _distance_row(np, point, (10.0, 0.0))])

    return [
        BenchmarkCase("triangle_distances", (1.0, 2.0), (0.25, 2.8), triangle_residual, triangle_jacobian, True),
        BenchmarkCase("parallel_plus_length", (3.0, 2.0), (4.5, 1.2), parallel_length_residual, parallel_length_jacobian, True),
        BenchmarkCase("near_tangent_circles", (1.0, 0.01), (1.0, 0.002), near_tangent_residual, near_tangent_jacobian, True),
        BenchmarkCase("inconsistent_distances", (5.0, 1.0), (5.0, 0.5), inconsistent_residual, inconsistent_jacobian, False),
        BenchmarkCase(
            "zero_length_seed",
            (0.0, 0.0),
            (0.1, 0.1),
            triangle_residual,
            triangle_jacobian,
            True,
            degeneracy="The analytic distance Jacobian is undefined at a zero-length seed.",
        ),
    ]


def _central_difference(np: Any, function: VectorFunction, point: Any, step: float = 1e-6) -> Any:
    columns = []
    for index in range(len(point)):
        offset = np.zeros_like(point, dtype=float)
        offset[index] = step
        columns.append((function(point + offset) - function(point - offset)) / (2.0 * step))
    return np.column_stack(columns)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _solve_case(np: Any, least_squares: Any, case: BenchmarkCase, *, analytic: bool, repetitions: int) -> dict[str, Any]:
    jacobian: Any = case.jacobian if analytic else "2-point"
    timings: list[float] = []
    result = None
    for _ in range(repetitions):
        started = perf_counter()
        result = least_squares(
            case.residual,
            np.asarray(case.initial, dtype=float),
            jac=jacobian,
            method="trf",
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
            max_nfev=200,
        )
        timings.append((perf_counter() - started) * 1000.0)
    assert result is not None
    residual_norm = float(np.linalg.norm(result.fun))
    constraint_feasible = residual_norm <= 1e-7
    return {
        "termination_success": bool(result.success),
        "termination_status": int(result.status),
        "termination_message": str(result.message),
        "constraint_feasible": constraint_feasible,
        "classification_correct": constraint_feasible == case.expected_feasible,
        "residual_norm": residual_norm,
        "solution": [float(value) for value in result.x],
        "function_evaluations": int(result.nfev),
        "jacobian_evaluations": int(result.njev) if result.njev is not None else None,
        "timing_ms": {
            "median": median(timings),
            "p95": _percentile(timings, 0.95),
            "repetitions": repetitions,
        },
    }


def run_benchmark(*, repetitions: int = 25) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    try:
        import numpy as np
        from scipy.optimize import least_squares
    except ImportError as exc:
        return {
            "schema_version": "1.0",
            "candidate": "scipy.optimize.least_squares",
            "available": False,
            "error": str(exc),
            "decision": "unavailable",
        }

    scipy_metadata = metadata("scipy")
    license_text = scipy_metadata.get("License") or ""
    case_results: list[dict[str, Any]] = []
    for case in _cases(np):
        probe = np.asarray(case.probe, dtype=float)
        analytic_jacobian = case.jacobian(probe)
        numeric_jacobian = _central_difference(np, case.residual, probe)
        case_results.append(
            {
                "name": case.name,
                "expected_feasible": case.expected_feasible,
                "degeneracy": case.degeneracy,
                "jacobian_max_abs_error": float(np.max(np.abs(analytic_jacobian - numeric_jacobian))),
                "analytic": _solve_case(np, least_squares, case, analytic=True, repetitions=repetitions),
                "finite_difference": _solve_case(np, least_squares, case, analytic=False, repetitions=repetitions),
            }
        )

    nondegenerate = [item for item in case_results if item["degeneracy"] is None]
    zero_seed = next(item for item in case_results if item["name"] == "zero_length_seed")
    nondegenerate_correct = all(
        item[method]["classification_correct"]
        for item in nondegenerate
        for method in ("analytic", "finite_difference")
    )
    jacobians_match = all(item["jacobian_max_abs_error"] <= 1e-5 for item in case_results)
    analytic_degenerate_safe = bool(zero_seed["analytic"]["classification_correct"])
    decision = "promising_not_ready" if nondegenerate_correct and jacobians_match and not analytic_degenerate_safe else "reassess"
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate": "scipy.optimize.least_squares",
        "candidate_status": "benchmark_only_not_a_production_dependency",
        "available": True,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
        },
        "license": {
            "family": "BSD-3-Clause",
            "source": "installed scipy package metadata",
            "metadata_sha256": hashlib.sha256(license_text.encode("utf-8")).hexdigest(),
        },
        "policy": {
            "feasible_residual_norm_max": 1e-7,
            "jacobian_max_abs_error_max": 1e-5,
            "timings_are_acceptance_gates": False,
            "termination_success_is_constraint_success": False,
        },
        "cases": case_results,
        "gate": {
            "nondegenerate_classification_correct": nondegenerate_correct,
            "analytic_jacobians_match_finite_difference": jacobians_match,
            "analytic_zero_length_seed_safe": analytic_degenerate_safe,
            "finite_difference_zero_length_seed_safe": bool(zero_seed["finite_difference"]["classification_correct"]),
        },
        "decision": decision,
        "decision_detail": (
            "SciPy is viable for the covered nondegenerate systems, but the analytic distance Jacobian can terminate "
            "with an infeasible residual at a zero-length seed. Keep it out of production until seed regularization, "
            "residual-based success classification, timeout behavior, and packaging are integrated behind the neutral contract."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark SciPy under the SketchMath neutral nonlinear solver contract")
    parser.add_argument("--repetitions", type=int, default=25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_benchmark(repetitions=args.repetitions)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
