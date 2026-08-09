# SketchMath Canonical Feature History Contract

Updated: 2026-08-09

Status: passed for the default-off v1 single-sketch extrusion/hole/full-revolve rebuild envelope (`SM-FEAT-001`, semantic-reference subset; partial `SM-FEAT-002`, `SM-FEAT-003`, and `SM-FEAT-004`)

## Enablement

Both flags are required for the browser workflow:

- backend: `FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED=1`
- frontend: `REACT_APP_SKETCHMATH_FEATURE_HISTORY_ENABLED=1`
- typed holes additionally require backend `FRIDAY_SKETCHMATH_HOLE_FEATURES_ENABLED=1` and frontend `REACT_APP_SKETCHMATH_HOLE_FEATURES_ENABLED=1`
- full revolves additionally require backend `FRIDAY_SKETCHMATH_REVOLVE_FEATURES_ENABLED=1` and frontend `REACT_APP_SKETCHMATH_REVOLVE_FEATURES_ENABLED=1`

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
- resolves semantic face/edge selectors by stable role/source identity, records exact or recovered state, and refuses missing/ambiguous recovery;
- computes deterministic area, signed volume delta, bounds, hole count, input hash, output signature, and document content hash;
- records succeeded, suppressed, failed, or blocked status for every feature.

The modeled extrusion parameters cover new-body, add, and cut semantics; positive/negative direction; symmetric extent; and one-/two-sided depth. Add/cut extrusions require exactly one same-body dependency plus one semantic top/bottom face attachment. Their bounds are placed relative to that face, and a one-sided operation aimed away from the target fails structurally.

Typed hole parameters cover simple, counterbore, and countersink style plus through/blind termination. A hole requires one extrusion target and one semantic top-face selector. Rebuild validates finite conditional parameters, target-material containment, edge breakout, depth versus cumulative target-body thickness, counterbore/countersink geometry, analytic removed volume, and generated rim/wall/bottom/style topology. The guarded browser currently creates simple through/blind holes; counterbore/countersink are canonical API/model operations only.

Typed revolve parameters name a stable sketch axis entity, a finite angle, and new-body/add/cut operation. The current rebuild accepts exactly 360 degrees, rejects profiles that cross the axis, computes analytic Pappus volume and exact full-revolution bounds, and generates source-derived semantic revolved-face references. An axis may be an `axis_2d`, regular line, or construction line. Add/cut requires exactly one dependency and semantic target face, but remains an analytic signed-volume contract rather than a kernel-validated spatial boolean.

Preview is side-effect free. Feature commits, rebuild, undo, redo, and reload never invoke the legacy FreeCAD export path. The existing `extrude_profile` preview/STEP workflow remains separate until artifact jobs consume canonical rebuild requests.

## Browser Behavior

When the frontend flag is enabled, the workspace shows Feature history with:

- current document revision and rebuild status;
- selected-profile extrusion creation;
- stable feature IDs, build status, measurements, and shortened output signatures;
- in-place extrusion-depth replacement;
- numeric simple-hole placement with through/blind termination against the current semantic top face;
- default-off new-body full-revolve creation from a selected closed profile and chosen construction-line axis;
- dedicated feature undo and redo.

A revision conflict refreshes the backend-authoritative session before the user retries.

## Evidence

- Unit coverage proves legacy wrapping, deterministic profile-hole-aware rebuild, semantic add/cut placement, all typed hole styles/terminations, full-revolve volume/bounds/topology, target/depth/breakout/axis/partial-sweep rejection, dependency order, extent semantics, preview purity, stable replacement IDs, stale revisions, structured rebuild failures, safe delete, and suppression.
- API coverage proves default-off document/hole/revolve gating, preview/commit isolation, disk rehydration, conflict status, geometry/document synchronization, hole/reference recovery, full-revolve persistence, and monotonic feature undo/redo.
- Frontend type-check and all 67 unit tests pass, including default-off/full-revolve editor behavior.
- A live Playwright workflow creates a rectangle feature, edits depth, observes a changed signature with a stable ID, performs feature undo/redo, reloads, creates a typed through hole, recovers its reference after another base edit, builds/downloads a terminal graph STL, and accepts no console/page errors.

## Open Boundaries

- The adapter supports one sketch and one process-authoritative session cache.
- Deterministic layered STL materializes supported vertical extrusion/simple-hole graphs through asynchronous revision-bound jobs; full-graph STEP and counterbore/countersink STL remain open.
- Partial revolve, kernel-backed revolve boolean/artifact validation, fillet, chamfer, shell, and feature pattern/mirror operations remain open.
- Semantic source/role/signature recovery is implemented for generated extrusion/hole topology, but browser face/edge picking and raw kernel-topology reconciliation remain open.
