# SketchMath Canonical Feature History Contract

Updated: 2026-08-09

Status: passed for the default-off v1 single-sketch extrusion/rebuild envelope (`SM-FEAT-001`; partial `SM-FEAT-002`)

## Enablement

Both flags are required for the browser workflow:

- backend: `FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED=1`
- frontend: `REACT_APP_SKETCHMATH_FEATURE_HISTORY_ENABLED=1`

Both default to off. The existing `FRIDAY_SKETCHMATH_ENABLED` and `REACT_APP_SKETCHMATH_ENABLED` gates are still required. With document v1 off, legacy sessions keep their prior response and persistence shape.

## Canonical State

`SketchMathDocument` schema version `1.0` owns:

- immutable document, body, sketch, feature, and artifact IDs;
- a monotonic document revision;
- body-to-sketch and body-to-feature membership;
- one or more typed features with explicit dependencies;
- provenance and revision-associated artifact records;
- the last deterministic rebuild report.

The current compatibility adapter wraps one legacy `SelectionContext` as `body_main` / `sketch_main` without changing any existing sketch entity IDs. The HTTP session adapter intentionally accepts exactly one sketch until the multi-sketch workspace phase.

## Feature Operations

`FeatureCommand` schema version `1.0` supports:

- `add_feature`
- `replace_feature`
- `delete_feature`
- `set_feature_suppressed`
- preview-only `rebuild`

Every operation carries `base_revision`. A stale write fails with `revision_conflict` before mutation. Replacement cannot change the feature ID. Delete refuses a feature referenced by downstream dependencies. Successful committed operations increment the document revision and persist a before/after feature-history record.

The API surface is:

- `POST /api/sketchmath/sessions/{session_id}/features/preview`
- `POST /api/sketchmath/sessions/{session_id}/features/commit`
- `POST /api/sketchmath/sessions/{session_id}/features/revert`
- `POST /api/sketchmath/sessions/{session_id}/features/redo`

Feature undo/redo is separate from sketch-command undo/redo. Undo and redo restore the canonical before/after document while assigning a new monotonic revision; revisions never move backward.

## Deterministic Rebuild

The pure rebuild layer:

- orders features by explicit dependencies with insertion order as the stable tie-break;
- rejects missing/duplicate dependencies and cycles structurally;
- marks downstream work blocked when a dependency fails;
- resolves the source sketch, profile, promoted-region identity, and explicit hole profiles;
- rejects stale region references and invalid or non-positive net profile area;
- computes deterministic area, signed volume delta, bounds, hole count, input hash, output signature, and document content hash;
- records succeeded, suppressed, failed, or blocked status for every feature.

The modeled extrusion parameters cover new-body, add, and cut semantics; positive/negative direction; symmetric extent; and one-/two-sided depth. Add/cut operations require an explicit same-body dependency. This is canonical history and geometric measurement evidence, not yet a broad solid-kernel rebuild.

Preview is side-effect free. Feature commits, rebuild, undo, redo, and reload never invoke the legacy FreeCAD export path. The existing `extrude_profile` preview/STEP workflow remains separate until artifact jobs consume canonical rebuild requests.

## Browser Behavior

When the frontend flag is enabled, the workspace shows Feature history with:

- current document revision and rebuild status;
- selected-profile extrusion creation;
- stable feature IDs, build status, measurements, and shortened output signatures;
- in-place extrusion-depth replacement;
- dedicated feature undo and redo.

A revision conflict refreshes the backend-authoritative session before the user retries.

## Evidence

- Unit coverage proves legacy wrapping, deterministic hole-aware rebuild, dependency order, add/cut and extent semantics, preview purity, stable replacement IDs, stale revisions, structured rebuild failures, safe delete, and suppression.
- API coverage proves default-off gating, preview/commit isolation, disk rehydration, conflict status, geometry/document synchronization, and monotonic feature undo/redo.
- Frontend type-check, all 66 existing unit tests, and the production build pass.
- A live Playwright workflow creates a rectangle feature, edits depth, observes a changed signature with a stable ID, performs feature undo/redo, reloads from disk, and accepts no console/page errors.

## Open Boundaries

- The adapter supports one sketch and one process-authoritative session cache.
- Rebuild does not yet materialize STEP/STL artifacts or kernel face/edge topology.
- Revolve, modeled-hole, fillet, chamfer, shell, and feature pattern/mirror operations remain open.
- Semantic solid face/edge naming and repairable ambiguity remain Phase 4 work.
