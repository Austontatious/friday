# SketchMath Requirement Traceability

This is the canonical requirement-to-evidence ledger for SketchMath. Update it with each coherent slice. `Implemented` means code exists; `Passed` requires current observable evidence; `Deferred` is not completion.

## Gate A Ledger

| Requirement | Current state | Implementation / source | Tests and acceptance evidence | Commit |
| --- | --- | --- | --- | --- |
| SM-GA-001 contract agreement | Passed | `sketchmath/models/`, generated `sketchmath/schemas/`, executor handler discovery, closed frontend command union | 66 focused contract/executor/API tests; schema drift check; 42 semantic evals | `878374b` |
| SM-GA-002 documentation truth | Passed | `docs/sketchmath/command_catalog.md`, `docs/sketchmath/ui_workspace.md`, translator contract prompt | Circle/topology/constraint contradiction scan; focused translation tests | `578b867` |
| SM-GA-003 feature-gate agreement | Passed | `core/config.py`, `frontend/src/services/sketchmath.ts`, `.env.example`, Dockerfile, Compose, ADR 003 | Backend unset/off tests; frontend unset/off/on tests; Compose config | `0647568` |
| SM-GA-004 clean build | Passed | Removed unused `sessionMetadata`; explicit frontend build flag | `npx tsc --noEmit`; production build compiled without SketchMath source warnings | `0647568` |
| SM-GA-005 deliberate landing | Passed | `docs/sketchmath/landing_manifest.md` and dedicated remote branch | Verified `refs/heads/sketchmath-product-gate-a` without force-push or source-branch rewrite | Code baseline `54ff17e`; first published `1a4c853` |
| SM-GA-006 regression baseline | Passed on 2026-08-08 | Deliberate landing implementation | 99 Python, 42 semantic eval, 37 focused frontend, 9 Playwright, schema check, TypeScript, build, Compose, 13 standards | `54ff17e` |

## Verified Existing Capability Ledger

| Capability | State | Evidence surface |
| --- | --- | --- |
| Point/line/rectangle/circle/hole sketching | Passed | `tests/test_sketchmath_foundations.py`, `SketchMathWorkspace.test.tsx`, `frontend/e2e/sketchmath.spec.ts` |
| Distance/angle/parallel/perpendicular/equal constraints | Passed for modeled nonlinear subset | residual/Jacobian solver tests and browser acceptance |
| Driving horizontal/vertical distance and radius/diameter | Passed for Phase 1 linear subset | v0.4 schema/API/solver/frontend/eval tests and live Playwright assertions |
| Horizontal/vertical/coincident constrained drag | Passed | foundation tests and Playwright constrained-drag workflow |
| Fixed/midpoint/collinear/symmetric/concentric/tangent constraints | Passed for the modeled v0.6 envelope | executor/schema/API/semantic/frontend tests; finite arc contacts are span-validated |
| Mixed-geometry full-constraint lifecycle | Passed for exact point-backed line/circle subset | Playwright remaining-DOF drag, full constraint, dimension re-solve, undo/redo, reload identity, and browser-error assertion |
| Construction/reference points and lines | Passed for canonical conversion envelope | v0.7 executor/schema/API/semantic/frontend tests plus live conversion/reload browser workflow; committed profile source lines are protected |
| Center rectangle | Passed for canonical rectangle-bundle envelope | Center/corner unit test and live symmetric-coordinate/reload browser workflow; downstream dimensions/profile/extrusion reuse the corner-rectangle path |
| Open polyline | Passed for canonical point/line envelope | Atomic typed batch, shared adjacent endpoint IDs, unit DOM counts, live API identity assertion, and reload browser workflow |
| Slot and regular polygon | Passed for canonical Gate B bundles | v0.8 typed commands, stable point/line/arc/profile identities, curve-backed profile synchronization, semantic evals, unit tests, and durable browser reload |
| Safe sketch editing | Passed for documented Gate B envelope | Complete-containment box select; point drag; dependency-safe split/trim/extend; independent line/circle/arc offset; linked-bundle duplicate/pattern/mirror; structured atomic refusal outside the safe envelope |
| General planar-region topology | Passed for documented v0.9 envelope | Stable line/circle/finite-arc regions, nested holes/islands, diagnostics, point selection, atomic profile promotion, API/semantic/unit/browser reload evidence |
| Preview/commit/revert and persistent undo/redo | Passed | API/history tests and Playwright reload/history workflow |
| Rectangle/circle/line-profile extrusion | Passed | CAD adapter/API tests and Playwright workflows |
| Holed STEP export/download | Passed | CAD tests and rectangle-to-STEP browser workflow |
| 3D preview orbit mechanics | Passed mechanically | frontend unit and browser assertions; manual CAD-feel acceptance remains open |

## Known Contradictions at Program Start

| ID | Contradiction | State | Resolution target |
| --- | --- | --- | --- |
| C-001 | Runtime supports v0.2 circle/topology/constraint commands absent from `geometry_command.schema.json`. | Resolved | SM-GA-001 |
| C-002 | `selection_context.schema.json` omits circle entities, linked line endpoint IDs, profile source metadata/holes, and horizontal/vertical/coincident constraints. | Resolved | SM-GA-001 |
| C-003 | Command catalog/UI docs say standalone circles are unsupported while runtime and acceptance tests support them. | Resolved | SM-GA-002 |
| C-004 | Frontend treats an unset SketchMath flag as enabled; backend treats unset as disabled. | Resolved | SM-GA-003 |
| C-005 | Production build reports unused `sessionMetadata`. | Resolved | SM-GA-004 |
| C-006 | Local validated history is substantially ahead of the remote branch and includes unrelated FRIDAY commits. | Resolved by dedicated branch | SM-GA-005 |
| C-007 | Automated camera movement passes, but prior manual CAD-like pan/tilt concern was never explicitly closed. | Deferred | SM-VIEW-001 |
| C-008 | Filesystem persistence plus process-local cache requires one backend worker. | Deferred | SM-DOC-002 |

## Future Gate Summary

| Requirement family | State | Next proof |
| --- | --- | --- |
| SM-SK / SM-SOL parametric sketcher | Gate B passed for documented modeled envelope | General topology begins at SM-TOP; broader constraint geometry remains explicit partial/unknown |
| SM-TOP general topology | Passed for documented v0.9 envelope | `b29d504`; adversarial fixtures, stable IDs, point selection, promotion/reference recovery, and nested browser reload |
| SM-FEAT feature history | `SM-FEAT-001` passed; `SM-FEAT-002/003/004/005` partial | Prior feature checkpoints plus `1f1b034`/`30af86a` and `24dfc70`/`3be0baa`; deterministic fillet/chamfer contracts, live kernel STEP, guarded editable UI, recovery/reload acceptance |
| SM-REF reference stability | Passed for documented generated topology and supported edge-finish kernel mapping | Stable source/role/adjacency IDs, geometry signatures, exact/recovered states, atomic missing/ambiguous refusal; fillet/chamfer uniquely map semantic endpoints without persisting kernel ordinals |
| SM-WS / SM-VIEW CAD workspace | Partial; minimum tree passed | `bc650ca`; body/sketch plus all typed feature nodes, selection, bounded properties, immutable-ID rename/reload, Normal-mode ID hiding. Visibility mutation, multi-sketch/body, reordering, and manual camera acceptance remain open |
| SM-DOC document architecture | Passed for one-sketch/one-worker v1 envelope | Legacy wrapping, versioned schemas, monotonic revisions, stale-write refusal, disk rehydration; multi-worker coordination remains open |
| SM-ART artifacts | Passed for supported STL and bounded terminal-edge-finish STEP; overall partial | Revision/hash-bound resumable jobs, stale-result refusal, golden eight-feature STEP with analytic circle/hole/fillet validation, idempotent registration/reload; automated cleanup and broader full-graph STEP remain open |
| SM-AI model-aware copilot | Early translator only | Structured model context, typed multi-step proposals, state-based semantic benchmark |
| SM-QA / SM-OPS / SM-SEC hardening | Partial | Artifact jobs and golden geometry pass their bounded envelope; cancellation, TTL/quota, performance, broader instrumentation, and kernel isolation remain open |

## Phase 1 Evidence Ledger

| Requirement | Current state | Evidence | Limitation |
| --- | --- | --- | --- |
| SM-ARCH-001 canonical document boundary | Passed for default-off compatibility envelope | ADR 004; `SketchMathDocument` v1; legacy one-sketch wrapping; generated schemas; disk round trip | Multi-sketch/body authoring and default-on migration remain open. |
| SM-ARCH-003 solver boundary | Adopted Phase 1 backend | ADR 005; `SolverAnalysis`; unified `SolverRunResult` v1.1; generated schema; SciPy benchmark and adversarial production tests | Async cancellation remains an open operations boundary. |
| SM-SOL-001 state reporting | Passed for modeled residual subset | Nonlinear consistency/redundancy/residual tests; live Normal labels plus Advanced diagnostics in unit and Playwright coverage | Minimal conflict sets are not claimed; conflicts are deterministic residual witnesses. |
| SM-SOL-002 defensible DOF | Passed for modeled residual subset | Central-difference Jacobian rank over deterministic point/circle/arc variables; explicit partial/unknown results for unmodeled entities | Coordinate-only legacy geometry and future geometry families remain partial. |
| SM-SK-001 arc geometry | Passed for canonical geometry and solver envelope | Canonical `arc_2d`; v0.5 center/three-point paths; source-link residuals; finite tangency validation; SVG/history/reload; finite-arc topology sampling | Topology uses the documented deterministic 2-degree approximation rather than exact analytic curved boundaries. |
| SM-SK-001 construction geometry | Passed for Gate B envelope | Point construction flag, canonical `construction_line_2d`, v0.7 stable-ID conversion, profile dependency guard, distinct workspace styling | Creation/conversion/schema/API/eval/frontend tests and the mixed fully constrained reload workflow pass; dedicated axis/reference-plane semantics remain open. |
| SM-SK-001 slot/polygon geometry | Passed for Gate B envelope | v0.8 stable point/line/finite-arc/profile bundles with `source_curve_ids` | Executor/schema/eval/frontend tests and durable mixed-geometry browser reload pass at `0621e8c`; regular source lines/arcs are eligible for the v0.9 topology path. |
| SM-SK-002 safe editing | Passed for documented envelope | v0.8 split/trim/extend/offset; linked transform/copy expansion; box selection; existing delete/drag/construction paths | Unit and live browser evidence prove success paths, history/reload stability, and atomic `unsafe_referenced_curve_edit`; automatic topology repair is deferred. |
| SM-SK-003 constraints and driving dimensions | Passed for modeled families | v0.4 driving dimensions plus v0.6 fixed/midpoint/collinear/symmetric/concentric/tangent residuals; exact mixed line/circle/arc tests | General topology-derived relations remain open. |
| SM-SOL-003 invalid commit prevention | Passed for modeled residual subset | Scaled residual gate, optimizer-success separation, finite-geometry validators, canonical replay, and live `409` conflict plus non-committing topology refusal/history assertions | Async cancellation remains open. |
| SM-TOP-001 deterministic planar regions | Passed for documented curve envelope | Shapely noding/polygonization over regular lines, circles, and finite arcs; stable region/loop models; source provenance | Construction geometry is intentionally excluded; curved boundaries are piecewise-linear. |
| SM-TOP-002 stable identity and selection | Passed | Canonical SHA-256 IDs, winding normalization, nesting depth, point statuses, v0.9 preview commands, React backend-authoritative overlays | Boundary clicks require a clear interior point or explicit list choice. |
| SM-TOP-003 adversarial topology | Passed | 17 focused topology tests plus API/semantic/frontend and nested-region Playwright acceptance | Arbitrary automatic split/trim/extend repair remains outside this topology slice. |
| SM-REF-002 topology profile preservation | Passed for region-backed sketch profiles and generated extrusion/hole references | `source_region_id`, source-set recovery, semantic source/role/signature selectors, exact/recovered state, atomic missing/ambiguous/hole-change rollback, disk reload | Browser face/edge picking and kernel-index reconciliation remain open. |
| SM-FEAT-001 canonical feature history | Passed for extrusion/hole/full-revolve rebuild envelope | Immutable IDs, explicit dependencies, revision-checked typed operations, deterministic pure rebuild, structured failure, persistence, guarded UI, feature undo/redo | Later edge/shell/pattern families remain open. |
| SM-FEAT-002 extrusion modes | Partial | Deterministic new-body/add/cut, direction, symmetric, one-/two-sided measurement, semantic face attachment, physical Z placement, and wrong-direction refusal | Browser creates new/add and edits depth; cut property UI and general kernel solid execution remain open. |
| SM-FEAT-003 revolve | Partial | Explicit stable sketch axis, deterministic full-angle Pappus volume/exact bounds, generated semantic faces, default-off API/UI, axis-edit recovery, persistence, and structured invalid/partial refusal | Browser creates new-body 360-degree revolves only; partial sweeps, spatial add/cut boolean proof, and STL/STEP remain open. |
| SM-FEAT-004 typed holes | Passed for the documented simple-hole browser envelope; advanced styles partial | Simple/counterbore/countersink model; through/blind validation; containment/breakout/depth checks; semantic top-face recovery; guarded simple-hole create plus diameter/termination/depth edit; undo/redo/reload and terminal STL | Counterbore/countersink remain canonical API/model operations without browser property editors. |
| SM-FEAT-005 fillet/chamfer/pattern/shell | Partial: fillet/chamfer subsets | Prior edge-finish checkpoints plus `5973c89`/`3e309de`; stable convex vertical-edge references, unique kernel matching, validated two-feature and golden eight-feature STEP, guarded property UI/reload | Bounded positive extrusion/simple-hole intermediates only; arbitrary edges, other graphs, edge-finish STL, pattern, mirror, and shell remain open. |
| SM-DOC-001 versioned persistence | Passed for filesystem compatibility adapter | Dual read/new write behind default-off flag, entity-ID preservation, monotonic revisions, stale conflict, reload | Session cache remains process-local and single-worker. |
| SM-UNIT-001 centralized tolerances | Initial implementation | Versioned `NumericalTolerancePolicy` | Unit expansion and display formatting remain open. |
| SM-ART-001 revisioned artifacts | Passed for supported STL and bounded STEP graphs | Persistent markers, idempotent job ID, revision registration, stale refusal, terminal UI/download, native golden fillet STEP and kernel geometry metadata | General full-graph STEP, automated retention/cleanup, cancellation, and broader non-vertical features remain open. |
| SM-QA-002 golden geometry | Passed for the release fixture and parameter-edit workflow | `5973c89`/`3e309de`/`d74a10f`/`f445b0c`; eight-feature geometry, v1.1 named parameters, analytic ledger, semantic recovery, undo/redo/reload, native base and widened/Ø6 STEP volume/bounds/cylinder/fillet checks, durable registration, and zero-error browser download | AI construction and broader non-golden feature graphs remain open. |
| SM-OPS-002 async boundary | Implemented for artifact jobs; overall partial | ADR 006; durable READY/RUNNING/DONE/FAILED runtime; retry and stale registration tests | Solve/rebuild/AI jobs, cancellation, TTL, and worker-process isolation remain open. |
