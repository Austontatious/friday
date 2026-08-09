# SketchMath Development Status

Updated: 2026-08-09

Current phase: Phase 2 — general planar topology

Gate: General topology passed for the documented v0.9 extraction, selection, promotion, and reference-preservation envelope

## Baseline

- Audited checkout: `21b8153`
- Latest SketchMath product code commit: `326e813`
- Source branch: `phase0-stabilize`
- Audit working tree: clean
- Verified remote `phase0-stabilize`: `4ed99b3`
- Local branch delta at program start: 68 commits ahead; 24 commits touch SketchMath code/docs/tests
- Deliberate landing branch: `sketchmath-product-gate-a`
- Validated landing code baseline: `54ff17e`
- First published landing commit: `1a4c853`

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
- The product lacks a canonical multi-body/feature document model and downstream rebuild graph.
- Multi-sketch, property editing, model tree, and stable face/edge references are not implemented.
- Session persistence uses a filesystem store plus in-process cache and is not multi-worker safe.
- STEP lifecycle is only partially managed; STL is not implemented.
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

Implement canonical feature history and deterministic rebuild (`SM-FEAT-001`) before broadening CAD operations.

## Release Status

Not release-ready. The full-product and final release gates in `docs/sketchmath/product_spec.md` remain open.
