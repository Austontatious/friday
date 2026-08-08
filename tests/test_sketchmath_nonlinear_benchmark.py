from __future__ import annotations

import pytest

from sketchmath.solver.nonlinear_benchmark import run_benchmark


def test_scipy_benchmark_records_residual_based_gate_and_degenerate_seed_limit() -> None:
    pytest.importorskip("scipy")

    report = run_benchmark(repetitions=2)

    assert report["available"] is True
    assert report["candidate_status"] == "benchmark_only_not_a_production_dependency"
    assert report["license"]["family"] == "BSD-3-Clause"
    assert report["gate"] == {
        "nondegenerate_classification_correct": True,
        "analytic_jacobians_match_finite_difference": True,
        "analytic_zero_length_seed_safe": False,
        "finite_difference_zero_length_seed_safe": True,
    }
    assert report["decision"] == "promising_not_ready"


def test_inconsistent_case_does_not_treat_optimizer_termination_as_constraint_success() -> None:
    pytest.importorskip("scipy")

    report = run_benchmark(repetitions=1)
    inconsistent = next(item for item in report["cases"] if item["name"] == "inconsistent_distances")

    assert inconsistent["analytic"]["termination_success"] is True
    assert inconsistent["analytic"]["constraint_feasible"] is False
    assert inconsistent["analytic"]["classification_correct"] is True


def test_benchmark_rejects_zero_repetitions() -> None:
    with pytest.raises(ValueError, match="repetitions"):
        run_benchmark(repetitions=0)
