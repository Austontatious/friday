# SketchMath Unified Solver Run Contract

## Purpose

`SolverRunResult` is the backend-neutral result shared by `analyze_constraints` and `solve_constraints`. It separates solver evaluation from canonical mutation so the production SciPy adapter and the closed-form fallback report the same outcome, feasibility, analysis, patch, and diagnostics.

Canonical schema: `sketchmath/schemas/solver_run_result.schema.json`.

## Fields

- `backend`: active implementation identifier; production generalized runs use `scipy_least_squares_v1`, while an unavailable dependency or explicit subset solve can use `closed_form_v1`.
- `mode`: `analyze` or `solve`.
- `outcome`: `analyzed`, `solved`, `under_constrained`, `inconsistent`, `redundant`, or `failed`.
- `termination_reason`: stable machine-oriented reason separate from user-facing error text.
- `requested_constraint_ids`: deterministic selected constraint order.
- `changed_entity_ids`: entities changed by the proposal.
- `proposed_patch`: stable entity before/after payloads sorted by entity ID.
- `feasible`: `true`, `false`, or `null` when the backend cannot prove feasibility.
- `residual_norm`: norm of scaled generalized residuals; `null` only for the closed-form fallback.
- `max_abs_residual`: maximum absolute scaled residual used by the feasibility gate.
- `residual_count`: number of scalar residual equations.
- `variable_order`: deterministic scalar variable ordering used by the run.
- `jacobian_strategy` / `jacobian_rank`: finite-difference strategy and converged rank.
- `function_evaluations` / `jacobian_evaluations`: selected optimizer-run evaluation counts.
- `seed_count`: number of deterministic seeds evaluated.
- `characteristic_length_mm`: length scale used to normalize geometric residuals.
- `optimizer_success`: optimizer termination flag, reported independently from `feasible`.
- `analysis_before` / `analysis_after`: the same typed `SolverAnalysis` envelope used by live status.
- `diagnostics`: structured-path explanations suitable for Advanced UI and AI inspection.

## Command behavior

`analyze_constraints` runs the shared path in analyze mode. It is preview-only, returns no patch, and exposes both `solver_analysis` compatibility metadata and the complete `solver_run`.

`solve_constraints` runs the same path in solve mode. The engine builds a proposal against a deep copy. The command handler applies only an accepted `solved` patch. Under-constrained preview returns a non-committing proposal for interaction/batch diagnostics; under-constrained commit, inconsistent, redundant, and failed outcomes return structured errors containing the complete `solver_run` and do not commit a partial patch.

The SciPy adapter accepts a result only when scaled residuals, finite arc-contact/source validators, and canonical rounded-patch replay all remain feasible. The closed-form backend reports `residual_norm=null` and can report `feasible=null` for partial coverage. Successful mutation or optimizer termination is never fabricated generalized feasibility.

## Nonlinear adapter invariants

SciPy or any replacement backend must populate the same result without mutating `SelectionContext` directly. It must:

1. use deterministic variable and residual ordering;
2. classify feasibility from scaled residuals, not optimizer termination alone;
3. report degeneracy and rank diagnostics;
4. return a canonical patch for validation;
5. stay inside the bounded synchronous policy until the async escalation threshold is implemented;
6. allow the command handler to reject the proposal before commit.

## Rollback

The result is additive metadata and a generated schema. Reverting the nonlinear routing restores the closed-form fallback; persisted geometry and command history formats are unchanged.
