# SketchMath Unified Solver Run Contract

## Purpose

`SolverRunResult` is the backend-neutral result shared by `analyze_constraints` and `solve_constraints`. It separates solver evaluation from canonical mutation so the current closed-form backend and a future nonlinear adapter must report the same outcome, feasibility, analysis, patch, and diagnostics.

Canonical schema: `sketchmath/schemas/solver_run_result.schema.json`.

## Fields

- `backend`: active implementation identifier; currently `closed_form_v1`.
- `mode`: `analyze` or `solve`.
- `outcome`: `analyzed`, `solved`, `under_constrained`, `inconsistent`, `redundant`, or `failed`.
- `termination_reason`: stable machine-oriented reason separate from user-facing error text.
- `requested_constraint_ids`: deterministic selected constraint order.
- `changed_entity_ids`: entities changed by the proposal.
- `proposed_patch`: stable entity before/after payloads sorted by entity ID.
- `feasible`: `true`, `false`, or `null` when the backend cannot prove feasibility.
- `residual_norm`: scaled generalized residual when the backend provides one; `null` for the current closed-form backend.
- `analysis_before` / `analysis_after`: the same typed `SolverAnalysis` envelope used by live status.
- `diagnostics`: structured-path explanations suitable for Advanced UI and AI inspection.

## Command behavior

`analyze_constraints` runs the shared path in analyze mode. It is preview-only, returns no patch, and exposes both `solver_analysis` compatibility metadata and the complete `solver_run`.

`solve_constraints` runs the same path in solve mode. The engine builds a proposal against a deep copy. The command handler applies only an accepted `solved` patch. Under-constrained, inconsistent, redundant, and failed outcomes return structured errors containing the complete `solver_run`; they do not commit a partial patch.

The closed-form backend reports `residual_norm=null`. It may report `feasible=null` for partial coverage even when its supported operations were applied. This is deliberate: successful mutation is not fabricated generalized feasibility.

## Future nonlinear adapter gate

A future SciPy or other backend must populate the same result without mutating `SelectionContext` directly. It must:

1. use deterministic variable and residual ordering;
2. classify feasibility from scaled residuals, not optimizer termination alone;
3. report degeneracy and rank diagnostics;
4. return a canonical patch for validation;
5. respect timeout/cancellation and async escalation;
6. allow the command handler to reject the proposal before commit.

## Rollback

The result is additive metadata and a generated schema. Reverting the unified-path commit restores the prior direct solve/analyze handlers; persisted geometry and command history formats are unchanged.
