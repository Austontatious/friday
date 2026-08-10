# SketchMath Canonical Feature History Contract

Updated: 2026-08-09

Status: passed for the default-off v1 single-sketch extrusion/hole/full-revolve/terminal-fillet-or-chamfer rebuild envelope (`SM-FEAT-001`, semantic-reference subset; partial `SM-FEAT-002` through `SM-FEAT-005`)

## Enablement

Both flags are required for the browser workflow:

- backend: `FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED=1`
- frontend: `REACT_APP_SKETCHMATH_FEATURE_HISTORY_ENABLED=1`
- typed holes additionally require backend `FRIDAY_SKETCHMATH_HOLE_FEATURES_ENABLED=1` and frontend `REACT_APP_SKETCHMATH_HOLE_FEATURES_ENABLED=1`
- full revolves additionally require backend `FRIDAY_SKETCHMATH_REVOLVE_FEATURES_ENABLED=1` and frontend `REACT_APP_SKETCHMATH_REVOLVE_FEATURES_ENABLED=1`
- fillets additionally require backend `FRIDAY_SKETCHMATH_FILLET_FEATURES_ENABLED=1` and frontend `REACT_APP_SKETCHMATH_FILLET_FEATURES_ENABLED=1`
- chamfers additionally require backend `FRIDAY_SKETCHMATH_CHAMFER_FEATURES_ENABLED=1` and frontend `REACT_APP_SKETCHMATH_CHAMFER_FEATURES_ENABLED=1`

Both default to off. The existing `FRIDAY_SKETCHMATH_ENABLED` and `REACT_APP_SKETCHMATH_ENABLED` gates are still required. With document v1 off, legacy sessions keep their prior response and persistence shape.

## Canonical State

`SketchMathDocument` schema version `1.1` owns:

- immutable document, body, sketch, feature, and artifact IDs;
- a monotonic document revision;
- body-to-sketch and body-to-feature membership;
- one or more typed features with explicit dependencies;
- typed design parameters with bounded affine bindings to supported sketch entities and feature properties;
- provenance and revision-associated artifact records;
- the last deterministic rebuild report.

The current compatibility adapter wraps one legacy `SelectionContext` as `body_main` / `sketch_main` without changing any existing sketch entity IDs. The HTTP session adapter intentionally accepts exactly one sketch until the multi-sketch workspace phase.

## Feature Operations

`FeatureCommand` accepts versions `1.0` and `1.1`. Version `1.1` adds the design-parameter operation while retaining:

- `add_feature`
- `replace_feature`
- `delete_feature`
- `set_feature_suppressed`
- `set_design_parameter` (`1.1` only)
- preview-only `rebuild`

Every operation carries `base_revision`. A stale write fails with `revision_conflict` before mutation. Replacement cannot change the feature ID. Delete refuses a feature referenced by downstream dependencies or a design-parameter binding. A parameter commit validates finite bounds and binding targets, mutates a deep candidate, synchronizes the primary sketch/session state, and accepts only a successful downstream rebuild. Successful committed operations increment the document revision and persist a before/after feature-history record.

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
- computes deterministic area, signed volume delta, bounds, and hole count where analytic coverage is exact; otherwise records `kernel_required` without invented measurements; every feature still receives deterministic input/output/document hashes;
- records succeeded, suppressed, failed, or blocked status for every feature.

The modeled extrusion parameters cover new-body, add, and cut semantics; positive/negative direction; symmetric extent; and one-/two-sided depth. Add/cut extrusions require exactly one same-body dependency plus one semantic top/bottom face attachment. Their bounds are placed relative to that face, and a one-sided operation aimed away from the target fails structurally.

Typed hole parameters cover simple, counterbore, and countersink style plus through/blind termination. A hole requires one extrusion target and one semantic top-face selector. Rebuild validates finite conditional parameters, target-material containment, edge breakout, depth versus cumulative target-body thickness, counterbore/countersink geometry, analytic removed volume, and generated rim/wall/bottom/style topology. The guarded browser creates simple holes and can replace an existing hole with simple/counterbore/countersink parameters. New advanced-hole creation and their STL/STEP materialization remain outside the bounded artifact envelope.

Typed revolve parameters name a stable sketch axis entity, a finite angle, and new-body/add/cut operation. The current rebuild accepts exactly 360 degrees, rejects profiles that cross the axis, computes analytic Pappus volume and exact full-revolution bounds, and generates source-derived semantic revolved-face references. An axis may be an `axis_2d`, regular line, or construction line. Add/cut requires exactly one dependency and semantic target face, but remains an analytic signed-volume contract rather than a kernel-validated spatial boolean.

Typed fillet parameters carry a positive radius and semantic convex outer-vertical-edge selectors. Extrusion topology records source/adjacency identity, 3D endpoints, geometric signature, corner class, and a safe radius bound. Rebuild resolves exact/recovered state and refuses missing, ambiguous, duplicate, non-vertical, concave, or oversized selections. Fillet measurements are explicitly `kernel_required`; validated volume/bounds come from the revision-bound FreeCAD STEP job described in `fillet_feature_contract.md`.

Typed chamfer parameters carry a positive distance and reuse that exact edge selector/recovery contract. Rebuild generates `chamfer_surface` references, enforces the same adjacent-edge bound, and leaves measurements `kernel_required`. The bounded job invokes native FreeCAD `makeChamfer`; see `chamfer_feature_contract.md`.

Preview is side-effect free. Feature commits, rebuild, undo, redo, and reload never invoke FreeCAD. Kernel work runs only through an explicit revision-bound artifact job; the legacy `extrude_profile` preview/STEP workflow remains a separate compatibility path.

## Browser Behavior

When the frontend flag is enabled, the workspace shows Feature history with:

- current document revision and rebuild status;
- bounded user-facing design-parameter editors without raw binding IDs;
- a minimum model tree for canonical body, sketch, and typed feature nodes, with selection, bounded properties, and immutable-ID feature rename;
- selected-profile extrusion creation, forcing the first feature to `new_body` and exposing `add`/`cut` for downstream profiles;
- stable feature IDs, build status, measurements, and shortened output signatures;
- in-place extrusion depth, one-/two-sided/symmetric extent, second-depth, and direction replacement while preserving operation/dependencies;
- numeric simple-hole placement and existing simple/counterbore/countersink style, diameter, termination/depth, and conditional style-parameter replacement against the current semantic top face;
- default-off new-body full-revolve creation from a selected closed profile and chosen construction-line axis, plus existing-feature axis replacement inside the supported 360-degree envelope;
- default-off outer-vertical-edge fillet creation, radius replacement, kernel STEP build, and download for the supported bounded vertical feature graph;
- default-off outer-vertical-edge chamfer creation, distance replacement, kernel STEP build, and download for its supported bounded vertical feature graph;
- dedicated feature undo and redo.

For the bounded downstream creation path, the browser attaches to the most recent extrusion's semantic top face. Add remains positive and a one-sided cut is automatically directed negative into that face, matching structural rebuild validation. A terminal cut graph can run through the validated layered STL job. This is not arbitrary face picking or a spatial kernel boolean: other target selection and cut STEP remain outside the current envelope.

Normal-mode tree labels use names and feature types rather than raw body/sketch/feature/profile/axis IDs. Persisted body/sketch visibility is shown read-only until renderer behavior supports a truthful mutation control. See `model_tree_contract.md`.

A revision conflict refreshes the backend-authoritative session before the user retries.

## Evidence

- Unit/kernel coverage proves the prior envelope plus stable vertical-edge identities, fillet/chamfer recovery/refusal, unique semantic-to-FreeCAD edge resolution, expected rounded/beveled box volumes, bounds/solid validity, and resumable STEP registration.
- API coverage proves default-off document/hole/revolve/fillet/chamfer gating, preview/commit isolation, disk rehydration, conflict status, geometry/document synchronization, reference recovery, and monotonic feature undo/redo.
- Frontend type-check and the 44 focused workspace tests pass. Targeted Playwright proves model-tree selection/rename/reload plus fillet and chamfer create/edit, kernel STEP polling/download, artifact metadata, and reload.
- A live Playwright workflow creates a rectangle feature, edits depth, observes a changed signature with a stable ID, performs feature undo/redo, reloads, creates a typed through hole, recovers its reference after another base edit, builds/downloads a terminal graph STL, and accepts no console/page errors.
- The golden browser workflow commits 80→100 mm width and Ø5→Ø6 four-hole design parameters, preserves offsets/centering and stable IDs, performs undo/redo/reload, then builds and downloads a revision-12 native STEP with exact supported topology and no browser errors.
- Existing simple-hole property editing is a complete `replace_feature` operation with rebuild, undo/redo, reload, and terminal STL evidence. A feature property owned by a design-parameter binding refuses direct replacement with `feature_parameter_bound`; rename remains allowed because it does not mutate the bound parameters.
- Existing full-revolve axis editing uses the same typed `replace_feature` boundary. Live Playwright creates two construction axes, changes the axis of a 360-degree revolve, observes a new rebuild signature with the same feature ID, and proves undo/redo/reload with no browser errors. The angle control remains fixed at 360 degrees because partial sweeps are structurally unsupported.
- Advanced hole property Playwright creates a simple hole, replaces it with a counterbore and then a countersink, verifies typed conditional parameters, and proves stable-ID undo/redo/reload with no browser errors. Artifact controls remain truthful: the layered STL and bounded STEP workers still support simple-hole graphs only.
- Extrusion property Playwright replaces a new-body feature with symmetric/negative and then two-sided/positive parameters, verifies exact analytic Z bounds and a changed signature with stable identity, and proves undo/redo/reload with no browser errors.

## Open Boundaries

- The adapter supports one sketch and one process-authoritative session cache.
- Deterministic layered STL materializes supported vertical new-body/add/cut extrusion and simple-hole graphs; STEP additionally materializes a bounded positive base/additive-extrusion/simple-hole graph with one terminal fillet or chamfer. Other intermediate feature types and general full-graph STEP remain open.
- Partial revolve, kernel-backed revolve boolean/artifact validation, broader fillet/chamfer, shell, and feature pattern/mirror operations remain open.
- Semantic source/role/signature recovery is implemented for generated extrusion/hole/revolve/edge-finish-input topology. Fillet/chamfer artifact execution uniquely reconciles supported edges by endpoints; arbitrary browser picking and general kernel-topology reconciliation remain open.
