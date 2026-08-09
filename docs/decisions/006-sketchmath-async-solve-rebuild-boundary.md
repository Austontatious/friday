# ADR 006: SketchMath async solve, rebuild, and kernel boundary

Status: accepted; artifact-job subset implemented

Date: 2026-08-08

## Decision

- Lightweight deterministic analysis and bounded interactive preview may run synchronously only while measured below the repository's approximately two-second request budget.
- General nonlinear solve, document rebuild, kernel feature execution, AI planning, and export become jobs with status, timeout, cancellation, structured failure, and observable duration.
- Every job captures document ID, input revision, operation ID, and a content hash. Results for a stale revision cannot commit silently.
- Preview results are immutable proposals. Commit revalidates the base revision and all referenced IDs.
- Cancellation or worker failure leaves the last committed document intact.
- Kernel subprocesses receive bounded numeric payloads and validated paths. They return artifacts and geometric measurements, never canonical document state.

## Implemented subset

Revision-bound artifact jobs now capture document ID, feature ID, input revision, and content hash in persistent READY/RUNNING/DONE/FAILED manifests. Deterministic job directories use step markers for validation, materialization, and registration; identical requests replay idempotently; missing materialized files rerun safely; and registration rechecks revision so stale results fail visibly without mutating the document. The guarded browser polls state, exposes retry, and downloads registered STL. See `docs/sketchmath/artifact_job_contract.md`.

## Current debt

Legacy `extrude_profile` still runs FreeCAD during command execution, and replay of legacy geometry history can repeat that side effect. Canonical v1 preview/commit/rebuild/undo/redo remain pure and separate. Artifact jobs currently use an in-process daemon thread, have no cancellation/TTL/quota controller, and only the supported layered STL path has broad feature-graph materialization. Nonlinear solve, general rebuild, AI planning, full-graph STEP/kernel work, cancellation, worker isolation, and stale-output scavenging remain open before the overall ADR can claim production completion.

## Rollout

New async runtime paths require default-off environment flags and health/readiness reporting. Artifact jobs follow this rule through `FRIDAY_SKETCHMATH_ARTIFACT_JOBS_ENABLED=0`; the legacy synchronous STEP compatibility path remains available separately.
