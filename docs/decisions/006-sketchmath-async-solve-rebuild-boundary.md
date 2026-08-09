# ADR 006: SketchMath async solve, rebuild, and kernel boundary

Status: accepted architecture checkpoint

Date: 2026-08-08

## Decision

- Lightweight deterministic analysis and bounded interactive preview may run synchronously only while measured below the repository's approximately two-second request budget.
- General nonlinear solve, document rebuild, kernel feature execution, AI planning, and export become jobs with status, timeout, cancellation, structured failure, and observable duration.
- Every job captures document ID, input revision, operation ID, and a content hash. Results for a stale revision cannot commit silently.
- Preview results are immutable proposals. Commit revalidates the base revision and all referenced IDs.
- Cancellation or worker failure leaves the last committed document intact.
- Kernel subprocesses receive bounded numeric payloads and validated paths. They return artifacts and geometric measurements, never canonical document state.

## Current debt

Legacy `extrude_profile` still runs FreeCAD during command execution, and replay of legacy geometry history can repeat that side effect. Canonical v1 feature operations are now separated from this path: preview/commit/rebuild/undo/redo are pure document work and never invoke FreeCAD. Kernel-backed canonical rebuild, artifact jobs, cancellation, and stale-result disposal remain open before broad solid features can claim production completion.

## Rollout

New async runtime paths require default-off environment flags, health/readiness reporting, and synchronous compatibility fallback until their acceptance suites pass.
