# SketchMath Development Status

Updated: 2026-08-09

Current phase: Phase 3/4/6 bounded solid-feature slice — feature history, semantic references, full revolve, kernel edge finishes, and revisioned artifacts

Gate: `SM-FEAT-001` and the documented generated-reference subset pass; `SM-FEAT-002/003/004/005`, `SM-ART-001`, and golden-part evidence pass only for their documented envelopes

## Baseline

- Audited checkout: `21b8153`
- Latest SketchMath product code commits: `d74a10f`, `f445b0c`
- Source branch: `phase0-stabilize`
- Audit working tree: clean
- Verified remote `phase0-stabilize`: `4ed99b3`
- Local branch delta at program start: 68 commits ahead; 24 commits touch SketchMath code/docs/tests
- Deliberate landing branch: `sketchmath-product-gate-a`
- Validated landing code baseline: `54ff17e`
- First published landing commit: `1a4c853`

## Current Resumed Release Regression

On 2026-08-09 after published full-revolve property checkpoint `4002b67`:

- 244 focused Python/runtime tests passed.
- All 55 semantic eval cases passed. Consecutive complete runs produced identical result-artifact SHA-256 `c972db1d00eda08910522e732dd5685286490c340b2b3c00068c7b19d89aceea`; the tracked JSON now reflects the corrected consistent hole-wall triangle winding.
- Generated schemas match the canonical models.
- TypeScript and all 62 focused frontend tests passed.
- The production build passed at the resumed regression checkpoint. Follow-up `7b62e3e` removed the actionable `syncSnapshot` hook-dependency warning; only the stale Browserslist data notice remains.
- Docker Compose config, Python compile, and all 13 repository standards checks passed.
- All 23 shell/product Playwright workflows passed in 4.2 minutes with no unexpected console/page errors, including Gate B, topology, feature history, golden STEP, semantic hole editing, full-revolve axis editing, fillet, and chamfer.

This regression closes the current checkpoint gate; it does not change the full-product release verdict below.

## Implemented Capabilities

- Typed deterministic 2D command execution with preview/commit.
- Point, line, rectangle, circle, and circular-hole workflows.
- Residual-validated nonlinear distance/angle/parallel/perpendicular/equal constraints.
- Horizontal, vertical, and coincident constraints with endpoint-aware dragging.
- Driving horizontal/vertical distance and radius/diameter constraints through contract version `0.4`.
- Simple deterministic line-loop profile detection and explicit promotion.
- Rectangle, detected-line, circle, and holed-profile extrusion.
- Orbitable deterministic 3D preview plus FreeCAD-backed STEP export/download.
- Persistent sessions and backend-authoritative undo/redo across reload.
- Structured errors and Normal/Advanced UI separation.
- Versioned, non-mutating solver analysis with exact Jacobian-rank DOF for modeled point/circle/arc systems and explicit partial/unknown coverage.
- Live Normal-mode solver labels backed by that analysis, with rank/DOF internals kept under Advanced / Debug.

## Published Gate A Baseline Validation

On 2026-08-08 at `54ff17e`:

- 99 focused Python tests passed.
- 42 semantic eval cases passed.
- 37 focused frontend tests passed across the deliberately selected FRIDAY shell and SketchMath workspace.
- 9 live Playwright workflows passed with no test-reported console/page errors.
- TypeScript compile passed.
- Canonical generated schemas match the Pydantic models.
- Production frontend build compiled successfully with no SketchMath source warning.
- Docker Compose config passed.
- 13 repository standards tests passed.

The build still reports the repository-wide stale Browserslist database notice. Updating frontend dependency metadata is intentionally deferred from the SketchMath-only Gate A slice.

## Current Gate B Validation

On 2026-08-09 for code checkpoint `0621e8c`:

- 168 focused Python tests passed.
- 52 semantic eval cases passed.
- 64 focused frontend tests passed.
- 16 live shell/product Playwright workflows passed; deliberately induced `409`/`422` rejection resource messages are asserted, and no unexpected console/page error is accepted.
- Generated schema, TypeScript, production build, Compose, and 13 repository standards checks passed.

## Current General Topology Validation

On 2026-08-09 for topology checkpoint `b29d504` plus session serialization fix `326e813`:

- 187 focused Python/runtime tests passed.
- 65 semantic eval cases passed.
- 66 focused frontend tests passed.
- All 17 serial shell/product Playwright workflows passed with no unexpected console/page errors.
- Generated schema drift, TypeScript, production build, Compose, and 13 repository standards checks passed.
- The production build reports only the existing stale Browserslist database notice.

## Current Feature History Validation

On 2026-08-09 for model/rebuild checkpoint `f1431ec`, persistence/API checkpoint `b1e5ac4`, and guarded UI checkpoint `df1363c`:

- 35 focused feature-history and SketchMath API tests passed.
- Nine pure feature/rebuild tests cover deterministic dependency order, hole-aware measurements, extent modes, stale revisions, structured failure, replacement, suppression, and safe delete.
- All 66 existing frontend tests passed with the new feature-history gate absent, proving the legacy UI path remains compatible.
- Generated v1 document, feature-command, rebuild-report, and operation-result schemas match their Pydantic models.
- TypeScript and the production frontend build passed; the build reports only the existing stale Browserslist database notice.
- The targeted live Playwright workflow passed with no console/page errors and proved create, property edit, signature change, stable ID, monotonic feature undo/redo, disk reload, and history persistence.

## Current Semantic Feature, Artifact, and Golden Validation

On 2026-08-09 for the prior hole/artifact foundation through release-spec golden checkpoints `5973c89`/`3e309de`:

- Eight canonical features now produce the 80 × 50 × 5 mm plate, four Ø5 holes at 7 mm edge offsets, centered analytic Ø30 × 8 mm boss, centered Ø10 through-hole, and four 2 mm outer vertical fillets.
- Exact pre-fillet volume is `20000+1350π mm³`; native FreeCAD final volume matches `19920+1370π mm³` within `1e-5`, with bounds `(0,80,0,50,0,13)`, valid solid state, and expected cylindrical face radii.
- Width 80→100 recenters the boss/boss-hole and keeps right holes at X=93; a following Ø5→Ø6 edit preserves all four 7 mm offsets and stable feature IDs. Semantic face/edge references recover.
- Revision-8 STEP passes the durable job state machine, idempotent replay, artifact registration, and session reload. Terminal fillet STL is explicitly refused rather than omitted.
- The focused feature/API/CAD/artifact/golden suite passes all 71 tests. The widened/Ø6 edit still needs one undo/redo browser workflow plus its own final STEP to complete Section 29.
- Generated schemas, TypeScript, Compose, and all 69 frontend tests remain green at the preceding model-tree checkpoint; the golden changes do not alter those contracts.

## Current Full-Revolve Validation

On 2026-08-09 for canonical model `a851d99`, API gate `3481f16`, and guarded UI `07e9880`:

- 59 focused feature/API/artifact/golden Python tests pass, including deterministic Pappus volume, arbitrary stable axis lookup, exact full-revolution bounds, generated semantic faces, reference recovery after axis edits, persistence, and structured partial-sweep/cross-axis/missing-axis refusal.
- TypeScript, generated schemas, Compose, and all 67 frontend tests pass. The UI test proves the editor remains absent by default and selects a construction-line axis when enabled.
- Browser creation is deliberately limited to a new-body 360-degree revolve. API/model add/cut requires a semantic target face but does not claim spatial boolean or kernel artifact validation.

The property-edit checkpoint `1e8db05` with browser proof `7976010` closes the supported full-revolve property envelope:

- An existing 360-degree revolve can replace its construction-axis reference through a typed revision-checked `replace_feature` operation while retaining its feature ID.
- Targeted backend revolve coverage (5 tests), TypeScript, and focused component coverage pass.
- Live Playwright creates two construction axes, creates a full revolve, changes its axis, observes a changed deterministic rebuild signature, and proves feature undo/redo plus disk reload in 10.8 seconds with no console/page errors.
- The angle field remains explicitly fixed at 360 degrees; partial sweeps, spatial revolve booleans, and revolve artifacts remain open rather than implied.

## Current Advanced-Hole Property Validation

On 2026-08-09 for guarded UI checkpoint `9f0621c`:

- The existing-hole property editor covers simple, counterbore, and countersink styles with through/blind depth plus conditional counterbore diameter/depth and countersink diameter/angle.
- All edits remain revision-checked typed `replace_feature` commits and retain backend style geometry, containment, depth, volume, and generated-topology validation.
- Five focused backend hole tests, TypeScript, all 44 workspace tests, and live counterbore→countersink undo/redo/reload Playwright pass. The browser workflow completed in 8.4 seconds with no console/page errors.
- New-hole creation remains simple-only. Advanced hole STL/STEP is not claimed; the current artifact workers still refuse unsupported advanced-hole graphs structurally.

## Current Extrusion Creation and Property Validation

On 2026-08-09 for guarded UI checkpoints `54bce47` and `775df7d`:

- Existing extrusion properties cover positive/negative direction and one-sided, symmetric, or two-sided extent with conditional second depth, in addition to primary depth.
- Typed replacement preserves operation, dependencies, semantic references, and immutable feature ID.
- Three focused backend tests, TypeScript, all 44 workspace tests, and live browser acceptance pass. The browser verifies exact symmetric `[-5,5]` and two-sided `[-4,10]` Z bounds, signature change, undo/redo, and reload in 7.4 seconds without console/page errors.
- The new-extrusion editor forces the first feature to `new_body` and offers explicit `add`/`cut` downstream. The bounded cut path depends on the latest extrusion, selects its semantic top face, and directs a one-sided cut negative into the target.
- The focused backend boolean invariant, TypeScript, all 44 workspace tests, and live base→cut acceptance pass. The browser verifies exact reference resolution, negative volume, `[6,10]` cut bounds, stable identity, undo/redo, and reload in 8.2 seconds.
- Eight artifact/materializer/job tests pass. The same browser workflow now builds, registers, downloads, and reloads a terminal cut STL; the permanent 10 × 10 × 10 base with a 4 × 4 × 4 top pocket is closed and measures exactly 936 mm³.
- Native FreeCAD now validates the same pocket at exactly 936 mm³ with unchanged bounds and ordered `new_body`/`cut` execution. The browser exposes both revision-bound STL and STEP build/download paths and completes the combined lifecycle in 13.4 seconds.
- Arbitrary face/body target picking and cut-before-edge-finish/general feature-graph execution remain open.

## Current Kernel-Fillet Validation

On 2026-08-09 for semantic model `1f1b034`, FreeCAD boundary `30af86a`, API gate `e6b272f`, and guarded UI `53a39ed`:

- 75 focused feature/API/CAD/artifact/golden Python tests pass. The live FreeCAD rounded-box proof selects four canonical vertical edges, uniquely reconciles them by unordered 3D endpoints, produces the expected volume `1000−80(1−π/4) mm³`, preserves `(0,20,0,10,0,5)` bounds, validates the solid, and registers STEP through resumable job markers.
- Generated schemas, TypeScript, Compose, and all 68 frontend tests pass.
- Targeted Playwright passes rectangle → extrusion → radius-3 outer fillet → asynchronous STEP → metadata/download → reload in 8.4 seconds, without making transient FreeCAD edge ordinals canonical.
- At that checkpoint the envelope was one independent positive one-sided extrusion followed by one terminal convex outer-vertical-edge fillet. Rebuild truthfully marked measurements `kernel_required`; `5973c89`/`3e309de` later closed the bounded golden additive/simple-hole graph while arbitrary picking and fillet STL remain open.

## Current Kernel-Chamfer Validation

On 2026-08-09 for semantic model `24dfc70`, FreeCAD boundary `3be0baa`, API gate `d06b014`, and guarded UI `f1b0b2c`:

- 78 focused feature/API/CAD/artifact/golden Python tests pass. Native FreeCAD `makeChamfer` over four uniquely endpoint-matched semantic edges produces the expected `960 mm³` volume for a `20 × 10 × 5 mm` box with `2 mm` chamfers, unchanged bounds, and a valid solid.
- Generated schemas, TypeScript, Compose, and all 68 frontend tests pass.
- Targeted Playwright passes rectangle → extrusion → distance-3 outer chamfer → asynchronous STEP → metadata/download → reload in 8.7 seconds.
- Chamfer shares fillet's durable selector/recovery and kernel-required measurement contract, but keeps typed `distance_mm` and native chamfer execution distinct. Unequal distances and broader edge/body graphs remain open.

## Current Minimum Model-Tree Validation

On 2026-08-09 for guarded UI checkpoint `bc650ca`:

- The canonical body and sketch plus Extrude, Revolve, Hole, Fillet, and Chamfer nodes render with user-facing labels and deterministic selection.
- Selected nodes expose bounded body/sketch or typed feature properties. Feature rename commits through existing immutable-ID replacement; raw profile/axis/entity IDs are not rendered in Normal-mode summaries.
- TypeScript and all 69 frontend tests pass. Targeted Playwright proves extrusion → tree selection → rename → unchanged ID/depth → backend reload in 5.4 seconds.
- Persisted body/sketch visibility is currently read-only because the renderer does not yet honor mutation. Multi-sketch/body hierarchy, reordering, and body/sketch rename remain open.

## Active Phase 1 Slice

- ADRs 004-006 define the canonical document migration, solver/licensing, and async execution boundaries.
- Command `analyze_constraints` uses contract version `0.3`, is preview-only, and never enters history.
- Exact rank-based analysis covers deterministic point/circle/arc variables plus every documented residual family; coordinate-only legacy lines and unmodeled geometry return honest partial/unknown results.
- The live workspace now refreshes non-mutating analysis after committed changes and reports Under/Fully/Over/Conflicting/Partially analyzed without exposing rank internals in Normal mode.
- Driving axis and circle dimensions update canonical geometry, replace same-semantic edits, persist through history/API replay, and remain exact in live solver state.
- SciPy `least_squares` is adopted behind the neutral run boundary with deterministic seeds, scaled residual feasibility, finite-geometry validation, canonical replay, and optimizer-success separation.
- Analysis and solve now share a typed backend-neutral run result with before/after analysis, feasibility, residual availability, deterministic entity patches, termination reason, and diagnostics.
- Canonical center and three-point arcs now share one persisted `arc_2d` model, v0.5 typed commands, stable source points, SVG rendering, structured degeneracy errors, and reload-stable history.
- Gate B fixed, midpoint, collinear, symmetric, concentric, and tangent constraints use typed v0.6 commands, deterministic direct interaction mutation, nonlinear solve/analysis, persistence/dependency handling, constrained drag where linked geometry is addressable, and selection-aware workspace controls.
- Fixed, midpoint, collinear, symmetric, concentric, tangent, dimensional, and angular relations participate in nonlinear rank/DOF analysis when all referenced geometry is modeled.
- A live mixed line/circle workflow now proves remaining-DOF drag, full constraint, dimensional edit, unified solve, undo/redo, and identical reload recovery without browser errors.
- Canonical construction points and construction lines now use stable existing entity identities plus typed v0.7 conversion, profile-source safety checks, distinct rendering, and reload-stable workspace controls.
- Center rectangle now provides center/corner and center-origin drag construction while committing the existing canonical rectangle bundle, so dimensions, profiles, history, reload, and extrusion remain shared.
- Open polylines now commit atomically as stable point identities plus linked line segments, with explicit finish/cancel controls and reload-stable shared vertices.
- v0.8 slots commit construction centers, linked boundary points, two lines, two finite arcs, and one curve-backed profile; regular polygons commit one stable point/line/profile bundle.
- Complete-containment box selection and the safe editing panel expose split, trim, extend, offset, duplicate, linear pattern, and mirror. Linked transforms/copies preserve canonical source identities; edits requiring topology repair fail atomically.
- One live solver lifecycle covers line, circle, arc, and construction geometry from remaining DOF through full constraint, structured conflict, recovery, solve, undo/redo, and identical reload. A second durable workflow covers slot/polygon editing, topology-sensitive refusal, recovery, history, and reload.
- Current evidence: 168 focused Python tests, 52 semantic evals, 64 focused frontend tests, all 16 shell/product Playwright workflows, generated schema check, TypeScript/build, Compose, and 13 standards tests pass. See `gate_b_acceptance.md`.

## Active Phase 2 Slice

- v0.9 `detect_regions` and `select_region` are preview-only; `make_region_profile` is the sole topology promotion command.
- Deterministic line/circle/finite-arc noding produces stable region and loop IDs, counterclockwise outer loops, clockwise holes, nesting depth, source provenance, and typed diagnostics.
- The adversarial envelope covers disjoint and nested loops, islands, multiple holes, shared edges, branches, intersections, touching/overlapping curves, near gaps, self-intersection, T-junctions, nested circles, and finite arcs.
- The browser consumes the backend result directly, supports boundary-safe point selection, promotes outer/hole profiles atomically, and preserves `source_region_id` across disk reload.
- Topology-backed profiles follow valid bundle transforms and source-set recovery; missing, ambiguous, or changed hole structures fail atomically.
- The filesystem session store now serializes mutation, undo, and redo per session so overlapping browser commits cannot collide on the atomic persistence file.
- Current evidence: 187 Python/runtime tests, 65 semantic evals, 66 frontend tests, all 17 serial shell/product Playwright workflows, generated schema check, TypeScript/build, Compose, and 13 standards checks pass. See `general_topology_contract.md`.

## Active Phase 3 Slice

- `SketchMathDocument` v1 now owns immutable body/sketch/feature IDs, revision, explicit dependencies, artifact records, provenance, and the last rebuild report.
- The default-off compatibility adapter preserves legacy sketch entity IDs while wrapping one `SelectionContext` as `body_main` / `sketch_main`.
- Revision-checked add/replace/delete/suppress operations persist independently from sketch-command history; feature undo/redo assigns new monotonic revisions.
- Pure rebuild topologically orders dependencies, detects missing references/cycles, propagates blocked status, validates source profiles/holes/region identity, and emits deterministic hashes, signatures, bounds, net area, signed volume, and structured errors.
- Typed extrusion parameters cover new-body/add/cut, positive/negative direction, symmetric, and one-/two-sided measurement semantics. Existing features expose the supported depth/direction/extent property envelope; broad kernel-backed feature reconstruction is not claimed.
- Add/cut extrusions attach through semantic top/bottom references and are placed at the resolved face Z; missing attachments and one-sided directions away from the target fail structurally. The browser can now author a bounded latest-extrusion top-face add/cut, while arbitrary target picking remains open.
- Typed holes cover simple/counterbore/countersink and through/blind analytic semantics. The guarded React panel exposes simple placement plus existing advanced-style conditional property editing, extrusion depth editing, rebuild/reference evidence, and dedicated feature undo/redo.
- Typed revolve covers an explicit stable axis, deterministic 360-degree Pappus volume/bounds, semantic generated faces, structured invalid-axis/profile/partial-sweep refusal, persistence, guarded new-body creation, and existing-axis replacement with feature undo/redo/reload.
- Typed fillet covers convex extrusion vertical edges, semantic adjacency/signature/endpoints, exact/recovered selection, finite radius editing, kernel-required measurement state, and a resumable validated FreeCAD STEP path with guarded browser creation/download.
- Typed chamfer reuses the stable edge contract with finite distance editing, deterministic `chamfer_surface` identity, native FreeCAD STEP validation, and guarded browser creation/download.
- Revision-bound artifact jobs persist READY/RUNNING/DONE/FAILED manifests and resumable step markers. Supported terminal vertical new-body/add/cut extrusion and simple-hole graphs produce validated layered STL; bounded terminal solid and terminal-fillet/chamfer graphs produce validated STEP; stale results never register.
- Legacy FreeCAD `extrude_profile` preview/export remains separate; canonical feature commits never replay external CAD work. See `feature_history_contract.md`, `artifact_job_contract.md`, and `golden_mounting_plate_v1.md`.

## Gate A Outcome

Completed and published:

1. Reconciled v0.1/v0.2 runtime, generated JSON schemas, frontend command types, docs, and eval contracts.
2. Corrected stale supported-envelope documentation.
3. Made frontend/backend feature-gate defaults explicitly off and aligned deployment configuration.
4. Removed the unused SketchMath frontend state/build warning.
5. Passed the complete Gate A regression suite.

6. Published `sketchmath-product-gate-a` and verified the remote ref at `1a4c853` without rewriting `origin/phase0-stabilize`. See `landing_manifest.md`.

## Known Limitations

- Arc-aware dimensions beyond radius are not implemented.
- Finite-arc tangency is supported only when the actual contact lies on the stored finite sweep; out-of-span contacts are rejected.
- Production solve covers the documented point/circle/arc residual subset. Coordinate-only legacy lines and future geometry/constraint families remain partial/unknown.
- Split/trim/extend intentionally reject profile- or constraint-referenced targets; automatic topology repair is not implemented.
- Circle and finite-arc topology uses a deterministic 2-degree piecewise-linear approximation; exact analytic curved-region area is not claimed.
- Canonical document v1 remains a single-sketch, single-worker compatibility path. The minimum single-body/sketch feature tree passes, while multi-sketch/body workspace behavior and visibility mutation are not implemented.
- Generated extrusion/hole semantic face/edge references are stable and recoverable, but browser face/edge picking and raw kernel-topology reconciliation are not implemented.
- Session persistence uses a filesystem store plus in-process cache and is not multi-worker safe.
- Layered STL supports vertical new-body/add/cut extrusion and simple-hole graphs. STEP supports bounded terminal solid graphs with positive adds/simple holes/negative top-face cuts, plus the prior positive graph with one terminal fillet/chamfer. Counterbore/countersink/revolve/edge-finish STL, partial revolve, revolve booleans, cut-before-edge-finish and other intermediate STEP graphs, shell/pattern features, and general full-graph STEP remain open.
- Artifact cancellation, automatic TTL/quota cleanup, and worker-process isolation are not implemented.
- 3D camera mechanics pass automation, but CAD-like pan/tilt feel requires explicit manual acceptance.
- AI translation covers a small command subset and does not yet plan over a canonical feature model.

## Active Decisions

- Preserve the validated five-layer architecture; no rewrite.
- SketchMath, not FreeCAD, owns the canonical model.
- Manual and AI editing share versioned typed operations.
- Major geometry expansion waits for Gate A.
- Solver work must start with mathematically defensible subsets and explicit unknown/partial states.
- SciPy is the adopted permissive production backend behind the neutral contract; SolveSpace remains reference-only due GPLv3.
- Residual feasibility, source/contact degeneracy, packaging, and adversarial seed/angle/conflict cases are closed for the modeled subset; async cancellation remains governed by ADR 006.

## Next Highest-Value Work

Run the remaining bounded kernel and release-regression gaps next. Full-revolve creation/axis editing and simple-hole diameter/through/blind/depth editing now pass their supported property envelopes; partial revolve and general kernel/artifact expansion remain explicitly out of scope until implemented and validated.

## Release Status

Not release-ready. The full-product and final release gates in `docs/sketchmath/product_spec.md` remain open.
