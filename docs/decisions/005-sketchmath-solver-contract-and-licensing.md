# ADR 005: SketchMath solver contract, DOF semantics, and licensing

Status: accepted Phase 1 boundary; generalized backend not yet selected

Date: 2026-08-08

## Problem

The current solver is an order-dependent sequence of closed-form mutations. It works for a bounded set of interactions but cannot honestly classify general remaining degrees of freedom, nonlinear redundancy, or minimal conflict sets.

A solver replacement chosen before defining the product contract would couple canonical state to one library and risk false precision or licensing problems.

## Decision

- Keep the existing closed-form executor as the production mutation path while Phase 1 establishes a solver-neutral contract.
- Solver analysis is separate from solving. It consumes an immutable sketch snapshot and returns typed coverage, freedom, consistency, redundancy, diagnostics, and tolerance policy.
- Exact DOF is reported only for mathematically covered systems. Partial systems return no exact DOF and expose only a bound over explicitly tracked variables.
- The first exact subset is linear equality geometry: point coordinates, circle center/radius variables, locked/fixed points/circles, horizontal, vertical, coincident, horizontal/vertical distance, radius, and diameter constraints.
- Nonlinear distance, angle, parallel, perpendicular, and equality constraints remain explicitly partial until a validated Jacobian-based backend exists.
- Numerical comparisons use the centralized versioned policy in `sketchmath/geometry/tolerances.py`. These are computational tolerances, not manufacturing tolerances.
- A future nonlinear solver must return a proposed coordinate patch, residual/Jacobian diagnostics, termination reason, and analysis; it must not mutate canonical state directly.

## Backend and license review

- [SolveSpace](https://github.com/solvespace/solvespace) is mature but GPL-3.0-or-later. It remains a semantic/reference oracle and is not linked or copied into SketchMath without an explicit product-license decision.
- [FreeCAD](https://github.com/FreeCAD/FreeCAD) is LGPL-2.1-or-later and remains behind the existing subprocess/kernel boundary. Its Sketcher is a useful oracle, but backend latency and identity translation make it unsuitable as the default interactive source of truth.
- [SciPy `least_squares`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) provides mature nonlinear least squares under SciPy's [BSD license](https://github.com/scipy/scipy/blob/main/LICENSE.txt). It is the leading Python backend candidate, contingent on analytic residual/Jacobian tests, degeneracy benchmarks, packaging, and timeout behavior.
- [Ceres Solver](https://ceres-solver.org/) is Apache-2.0 and production-proven, but adds a native integration surface that is not justified before the Python contract is benchmarked.

No new solver dependency is adopted by this decision.

## Phase 1 evolution

Command version `0.4` adds driving horizontal/vertical distance and radius/diameter operations without changing the solver-neutral boundary. These constraints are linear in the tracked variables, so they extend exact rank analysis and the existing deterministic mutation path without selecting a generalized nonlinear backend. Circle dimensions replace the prior radius-or-diameter constraint for that circle; equivalent manually constructed constraints remain detectable as redundant.

The first SciPy benchmark keeps the candidate outside production. Covered nondegenerate cases and analytic Jacobian checks passed, but SciPy reported successful termination for both a deliberately inconsistent system and an analytic zero-length seed with unacceptable residual. Any future adapter must classify feasibility from scaled residuals, define a degeneracy policy, and return diagnostics through the neutral result contract.

`SolverRunResult` now implements that neutral result boundary for both analysis and solve commands. The closed-form backend proposes deterministic entity patches against a copy; the command layer applies only accepted solved patches. Unsupported generalized residuals remain `null`, and partial coverage yields unknown feasibility instead of a fabricated success claim.

Command version `0.5` adds canonical center and three-point arcs without pretending the linear analyzer covers them. Arc entities are listed explicitly as unmodeled, so whole-sketch coverage remains partial until arc equations, rank semantics, and residual validation are implemented behind the same `SolverRunResult` boundary.

## DOF semantics

- `coverage=exact` means every mutable entity and active constraint is represented by the analyzer.
- `coverage=partial` means supported equations were analyzed but the whole sketch was not covered.
- `coverage=unknown` means the analyzer cannot make a useful whole-sketch classification.
- `remaining_dof` is populated only for exact, consistent coverage.
- Inconsistency is proven when the supported augmented linear system has greater rank than its coefficient matrix.
- Redundancy is proven when a supported constraint adds no independent equation to a still-consistent system.
- A reported conflicting constraint is the deterministic constraint that exposes inconsistency in stable evaluation order; it is not claimed to be a minimal conflict set.

## Rollback

The analysis command is non-mutating and versioned. Removing it leaves the existing solver path unchanged.
