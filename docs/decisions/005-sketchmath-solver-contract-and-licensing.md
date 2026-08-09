# ADR 005: SketchMath solver contract, DOF semantics, and licensing

Status: accepted; SciPy nonlinear backend adopted for production Phase 1 solving

Date: 2026-08-09

## Problem

The current solver is an order-dependent sequence of closed-form mutations. It works for a bounded set of interactions but cannot honestly classify general remaining degrees of freedom, nonlinear redundancy, or minimal conflict sets.

A solver replacement chosen before defining the product contract would couple canonical state to one library and risk false precision or licensing problems.

## Decision

- Keep `SolverRunResult` as the backend-neutral proposal boundary; canonical state is mutated only after a proposal passes feasibility and canonical replay validation.
- Solver analysis is separate from solving. It consumes an immutable sketch snapshot and returns typed coverage, freedom, consistency, redundancy, diagnostics, and tolerance policy.
- Exact DOF is reported only for mathematically covered systems. Partial systems return no exact DOF and expose only a bound over explicitly tracked variables.
- The production nonlinear subset models stable point coordinates, circle center/radius variables, canonical arc center/radius/start/sweep variables, linked line endpoints, and linked arc source points.
- Supported residual families are fixed/locked, horizontal, vertical, coincident, distance, horizontal/vertical distance, radius, diameter, angle, parallel, perpendicular, equal length, equal angle, midpoint, collinear, symmetric, concentric, and finite line/circle/arc tangency.
- Numerical comparisons use the centralized versioned policy in `sketchmath/geometry/tolerances.py`. These are computational tolerances, not manufacturing tolerances.
- Production solving uses deterministic variable/residual ordering, three deterministic seeds, characteristic-length scaling, SciPy three-point finite-difference Jacobians, central-difference rank analysis, residual feasibility independent of optimizer success, finite-geometry post-validation, and canonical rounded-patch replay.
- The closed-form path remains a compatibility fallback when SciPy is unavailable and for explicitly selected constraint-subset solves; it is not allowed to claim generalized feasibility.

## Backend and license review

- [SolveSpace](https://github.com/solvespace/solvespace) is mature but GPL-3.0-or-later. It remains a semantic/reference oracle and is not linked or copied into SketchMath without an explicit product-license decision.
- [FreeCAD](https://github.com/FreeCAD/FreeCAD) is LGPL-2.1-or-later and remains behind the existing subprocess/kernel boundary. Its Sketcher is a useful oracle, but backend latency and identity translation make it unsuitable as the default interactive source of truth.
- [SciPy `least_squares`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) provides mature nonlinear least squares under SciPy's [BSD license](https://github.com/scipy/scipy/blob/main/LICENSE.txt). It is adopted as the production Phase 1 generalized backend through the solver-neutral adapter.
- [Ceres Solver](https://ceres-solver.org/) is Apache-2.0 and production-proven, but adds a native integration surface that is not justified before the Python contract is benchmarked.

`scipy>=1.11,<2` is now a production dependency. The adapter remains isolated behind `SolverRunResult`, so replacing it does not change persisted sketch or command contracts.

## Phase 1 evolution

Command version `0.4` adds driving horizontal/vertical distance and radius/diameter operations without changing the solver-neutral boundary. These constraints are linear in the tracked variables, so they extend exact rank analysis and the existing deterministic mutation path without selecting a generalized nonlinear backend. Circle dimensions replace the prior radius-or-diameter constraint for that circle; equivalent manually constructed constraints remain detectable as redundant.

The first SciPy benchmark initially kept the candidate outside production. Covered nondegenerate cases and analytic Jacobian checks passed, but SciPy reported successful termination for both a deliberately inconsistent system and an analytic zero-length seed with unacceptable residual. That evidence established the residual, degeneracy, and diagnostic gates later closed by the production adapter.

`SolverRunResult` implements that neutral result boundary for both analysis and solve commands. Its initial closed-form implementation established deterministic patches against a copy; the adopted SciPy adapter preserves the same command-layer acceptance boundary. Unsupported geometry still yields partial/unknown coverage instead of a fabricated success claim.

Command version `0.5` adds canonical center and three-point arcs. The nonlinear adapter now models arc variables, linked center/start/through/end equations, source degeneracy, exact rank semantics, and finite-span tangent validation through the same `SolverRunResult` boundary.

The adoption gate is closed by adversarial tests covering far and zero seeds, zero/near-zero/180/near-180-degree angles, contradictory and duplicated constraints, long dependency chains, unit-normalized replay, coincident circle centers, linked arc source identities, and finite versus out-of-span arc contacts. Successful optimizer termination is still never treated as proof of feasibility.

## DOF semantics

- `coverage=exact` means every mutable entity and active constraint is represented by the analyzer.
- `coverage=partial` means supported equations were analyzed but the whole sketch was not covered.
- `coverage=unknown` means the analyzer cannot make a useful whole-sketch classification.
- `remaining_dof` is populated only for exact, consistent coverage.
- Inconsistency is proven when scaled residual or finite-geometry validation fails for the modeled system; optimizer success does not override that result.
- Redundancy is reported when a supported constraint group adds no Jacobian rank at a feasible converged solution.
- A reported conflicting constraint is the deterministic constraint that exposes inconsistency in stable evaluation order; it is not claimed to be a minimal conflict set.

## Rollback

The nonlinear adapter does not own canonical state or persistence. Rollback removes the SciPy routing/dependency and restores `closed_form_v1`; persisted geometry, commands, and history remain readable, while generalized exact coverage returns to partial/unknown.
