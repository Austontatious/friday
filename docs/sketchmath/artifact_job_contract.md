# SketchMath Revision-Bound Artifact Job Contract

Updated: 2026-08-09

Status: passed for default-off STL jobs over supported vertical analytic graphs and STEP jobs over bounded terminal solid, full-revolve, or edge-finish graphs

## Enablement

Artifact jobs require all existing SketchMath/document flags plus:

- backend: `FRIDAY_SKETCHMATH_ARTIFACT_JOBS_ENABLED=1`
- frontend: `REACT_APP_SKETCHMATH_ARTIFACT_JOBS_ENABLED=1`
- optional job root: `FRIDAY_SKETCHMATH_ARTIFACT_JOB_DIR=artifacts/sketchmath/jobs`

Both capability flags default to off. The CAD output root remains `FRIDAY_SKETCHMATH_CAD_EXPORT_DIR`.

## HTTP Contract

- `POST /api/sketchmath/sessions/{session_id}/artifacts/build` accepts `feature_id`, `format`, and `base_revision`, then returns `202` with an `ArtifactJobManifest`.
- `GET /api/sketchmath/sessions/{session_id}/artifacts/jobs/{job_id}` returns the durable job state.
- `POST /api/sketchmath/sessions/{session_id}/artifacts/jobs/{job_id}/retry` retries a non-terminal job without discarding completed steps.
- `GET /api/sketchmath/artifacts/stl?path=...` and the existing STEP route serve only allowed suffixes below the configured export root.

The deterministic job identity hashes document ID, terminal feature ID, format, input revision, and input content hash. Repeating an identical successful request returns the same job and artifact rather than creating duplicate work.

## Directory Contract

Each job owns exactly one directory:

```text
{job_root}/{job_id}/
  manifest.json
  request.json
  validate.done
  materialized.json
  materialize.done
  result.json | error.json
  register.done
```

`manifest.json` is atomically replaced and carries `READY`, `RUNNING`, `DONE`, or `FAILED`, plus attempt, current step, timestamps, input revision/hash, structured error, and result. A `.done` marker means that step may be reused after process interruption. A missing materialized file invalidates `materialize.done` and safely reruns materialization.

## State and Revision Rules

- Submission snapshots an immutable canonical document only after `base_revision` matches.
- Materialization may finish after the model changes, but registration rechecks the input revision.
- A stale result becomes `FAILED` with `revision_conflict`; it is never attached silently.
- Registration is idempotent and does not increment model revision because the artifact records the already-committed input revision.
- Retry preserves valid materialization output and reruns registration. Retrying a permanently stale request remains a visible failure; the client must submit a new request at the current revision.
- Worker failure leaves the committed model untouched and returns `code`, `message`, `detail`, and `retryable`.

## Supported Materialization Envelope

Deterministic STL materialization consumes the canonical feature graph through the requested terminal body feature. It supports vertically layered new-body/add/cut extrusions and simple typed holes, performs Shapely union/difference per Z slab, triangulates transition faces, checks every mesh edge has incidence two, and compares mesh bounds/volume against the analytic rebuild ledger. Circles use a deterministic 360-segment approximation; analytic and mesh volume plus their difference are retained in artifact metadata. A permanent base-plus-top-pocket fixture proves a closed 936 mm³ cut STL through both direct materialization and the browser job/register/download path.

Counterbore/countersink canonical rebuild is implemented, but layered STL for those styles is intentionally refused. Canonical solid STEP materialization supports one positive one-sided new-body extrusion followed by positive adds, simple holes, or negative one-sided top-face cuts when an extrusion is terminal. It also supports one independent 360-degree new-body revolve around a stable in-plane sketch axis. The FreeCAD worker executes canonical order and refuses export unless native solid validity, bounds, and volume match the analytic ledger. Edge-finish STEP separately supports the bounded positive base/additive-extrusion/simple-hole graph followed by one terminal convex outer-vertical-edge fillet or chamfer. Exact source circles are passed as analytic primitives; semantic edge endpoints are uniquely matched before the native finish. Partial/revolve booleans, cut-before-edge-finish, and other intermediate feature types remain rejected.

## Retention and Cleanup

There is no automatic deletion in this slice. Job manifests and revisioned artifacts are retained for audit/retry. Operators may remove terminal job directories and their referenced CAD revision directories only under an explicit external retention procedure; active job folders must not be removed. Automated TTL, pinning, quota enforcement, and stale-materialization scavenging remain open.

## Evidence

- `tests/test_sketchmath_artifact_jobs.py`: READY/RUNNING/DONE/FAILED directory state, idempotent replay, safe resume, revision registration, stale-result refusal, and fillet/chamfer STEP registration.
- `tests/test_sketchmath_feature_artifact.py` and `tests/test_sketchmath_stl_export.py`: safe revisioned paths, deterministic base/add/cut STL, hole-aware volume/closure, and live FreeCAD edge-finish volume/bounds/reference validation.
- `tests/test_sketchmath_golden_mounting_plate.py`: eight-feature release fixture, parameter-intent recovery, exact analytic circle handoff, native filleted STEP geometry, resumable registration/idempotency, and reload.
- `tests/test_sketchmath_api.py`: default-off gate, submit/poll/register/download/replay contract.
- Targeted Playwright acceptance: terminal feature-graph and semantic-cut build, visible polling state, revision registration, reload persistence, and browser download.

Implementation checkpoints: `718ee6b`, `0ef759c`, `9860570`, `217e741`, `b88b1be`, `a3d705c`, `0979dfe`, `30af86a`, `53a39ed`, `3be0baa`, `f1b0b2c`, `5973c89`, `3e309de`, cut STL evidence `c0a773a`, kernel cut STEP `435b2e4`, and full-revolve STEP `469882a`.
