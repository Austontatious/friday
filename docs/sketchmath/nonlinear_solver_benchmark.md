# SketchMath Nonlinear Solver Benchmark

Date: 2026-08-08

Candidate: `scipy.optimize.least_squares`

Decision: promising, not ready for production adoption

## Boundary

This benchmark exercises SciPy behind the solver-neutral boundary from ADR 005. It does not import SciPy from the production executor, add SciPy to runtime requirements, mutate canonical SketchMath state, or change the active solve path.

The installed SciPy 1.15.3 package metadata reports the BSD 3-clause license text. The recorded metadata hash and bundled-library detail are in `evals/sketchmath_nonlinear_solver_benchmark.json`; this is provenance evidence, not legal advice.

## Cases and result

Environment: Python 3.10.12, NumPy 2.1.3, SciPy 1.15.3, Linux x86_64. Each timing is 25 in-process repetitions and is diagnostic, not an acceptance threshold.

| Case | Analytic residual | Analytic p95 | Finite-difference p95 | Classification |
| --- | ---: | ---: | ---: | --- |
| Triangle distances | 0 | 1.58 ms | 2.59 ms | Correct feasible |
| Parallel plus length | 0 | 0.78 ms | 1.30 ms | Correct feasible |
| Near-tangent circles | 7.48e-12 | 1.74 ms | 2.91 ms | Correct feasible |
| Inconsistent distances | 5.66 | 6.83 ms | 9.11 ms | Correctly infeasible by residual |
| Zero-length analytic seed | 2.0 | 1.27 ms | 3.28 ms | Analytic path incorrectly terminates infeasible; finite difference recovers |

Analytic Jacobians matched central finite differences within `2.2e-10` at nonsingular probes.

## Critical findings

- Optimizer termination is not constraint success. SciPy returned `success=true` for the deliberately inconsistent system while the residual norm remained about `5.66`.
- A mathematically correct analytic distance Jacobian still needs an explicit zero-length policy. At the singular seed, the analytic run returned `success=true` with residual norm `2.0`; finite differences found the feasible solution.
- Nondegenerate and near-tangent cases are fast enough to justify integration work, but timings from this single host are not a deployment SLA.

## Adoption gate

Do not make SciPy a production dependency until all of the following exist behind the neutral interface:

1. Residual-based feasibility classification independent of the optimizer's termination flag.
2. Deterministic zero-length seeding or regularized derivatives with explicit degeneracy diagnostics.
3. Stable variable ordering, residual scaling, Jacobian-rank diagnostics, and canonical coordinate patches.
4. Request timeout/cancellation and async escalation for solves that exceed the interactive budget.
5. Packaging and container-size validation plus license inventory for the actual distributed wheel and bundled libraries.
6. Adversarial benchmarks for inconsistent, redundant, underdetermined, badly scaled, and multiple-solution systems.

## Reproduce

```bash
PYTHONPATH=. python3 -m sketchmath.solver.nonlinear_benchmark \
  --repetitions 25 \
  --output evals/sketchmath_nonlinear_solver_benchmark.json
python3 -m pytest -q tests/test_sketchmath_nonlinear_benchmark.py
```

The JSON artifact records exact residuals, solutions, termination details, evaluation counts, timing samples, environment, license metadata hash, and the adoption decision.

## Rollback

Remove the benchmark module, its tests, report, and JSON artifact. No runtime path or persisted model depends on them.
