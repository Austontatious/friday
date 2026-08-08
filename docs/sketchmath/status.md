# SketchMath Development Status

Updated: 2026-08-08

Current phase: Phase 1 — canonical parametric architecture

Gate: Gate A passed

## Baseline

- Audited checkout: `21b8153`
- Latest SketchMath product commit: `8236828`
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
- Existing closed-form distance/angle/parallel/perpendicular/equal constraints.
- Horizontal, vertical, and coincident constraints with endpoint-aware dragging.
- Driving horizontal/vertical distance and radius/diameter constraints through contract version `0.4`.
- Simple deterministic line-loop profile detection and explicit promotion.
- Rectangle, detected-line, circle, and holed-profile extrusion.
- Orbitable deterministic 3D preview plus FreeCAD-backed STEP export/download.
- Persistent sessions and backend-authoritative undo/redo across reload.
- Structured errors and Normal/Advanced UI separation.
- Versioned, non-mutating solver analysis with exact linear point-backed DOF and explicit partial/unknown coverage.
- Live Normal-mode solver labels backed by that analysis, with rank/DOF internals kept under Advanced / Debug.

## Current Gate A Validation

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

## Active Phase 1 Slice

- ADRs 004-006 define the canonical document migration, solver/licensing, and async execution boundaries.
- Command `analyze_constraints` uses contract version `0.3`, is preview-only, and never enters history.
- Exact rank-based analysis currently covers point/circle variables plus locked/fixed, horizontal, vertical, coincident, horizontal/vertical distance, radius, and diameter equations.
- Nonlinear constraints and unmodeled geometry return honest partial/unknown results.
- The live workspace now refreshes non-mutating analysis after committed changes and reports Under/Fully/Over/Conflicting/Partially analyzed without exposing rank internals in Normal mode.
- Driving axis and circle dimensions update canonical geometry, replace same-semantic edits, persist through history/API replay, and remain exact in live solver state.
- SciPy `least_squares` benchmarked successfully for covered nondegenerate systems, but remains unadopted because optimizer termination can mask infeasible residuals and an analytic zero-length seed failed.
- Analysis and solve now share a typed backend-neutral run result with before/after analysis, feasibility, residual availability, deterministic entity patches, termination reason, and diagnostics.
- Canonical center and three-point arcs now share one persisted `arc_2d` model, v0.5 typed commands, stable source points, SVG rendering, structured degeneracy errors, and reload-stable history.
- Gate B fixed, midpoint, collinear, symmetric, concentric, and tangent constraints now use typed v0.6 commands, deterministic closed-form mutation, persistence/dependency handling, constrained drag where linked geometry is addressable, and selection-aware workspace controls.
- Fixed, midpoint, and circle concentricity extend exact linear analysis. Collinearity, symmetry, and tangency remain explicitly partial until their nonlinear equations are modeled.
- A live mixed line/circle workflow now proves remaining-DOF drag, full constraint, dimensional edit, unified solve, undo/redo, and identical reload recovery without browser errors.
- Canonical construction points and construction lines now use stable existing entity identities plus typed v0.7 conversion, profile-source safety checks, distinct rendering, and reload-stable workspace controls.
- Current evidence: 145 focused Python tests, 50 semantic evals, 61 focused frontend tests, 12 live Playwright workflows, generated schema check, TypeScript/build, Compose, and 13 standards tests pass.

## Gate A Outcome

Completed and published:

1. Reconciled v0.1/v0.2 runtime, generated JSON schemas, frontend command types, docs, and eval contracts.
2. Corrected stale supported-envelope documentation.
3. Made frontend/backend feature-gate defaults explicitly off and aligned deployment configuration.
4. Removed the unused SketchMath frontend state/build warning.
5. Passed the complete Gate A regression suite.

6. Published `sketchmath-product-gate-a` and verified the remote ref at `1a4c853` without rewriting `origin/phase0-stabilize`. See `landing_manifest.md`.

## Known Limitations

- Arc solver equations, arc-aware dimensions/constraints, and arc participation in general planar topology are not implemented; solver coverage is explicitly partial.
- Finite-arc tangency is rejected rather than approximated as full-circle tangency.
- Production solve remains a conservative closed-form subset. Exact analysis covers its linear point/circle families; Euclidean distance, angle, parallel/perpendicular, and equality relations remain partial/unknown.
- Topology recognizes deterministic simple line cycles, not general planar regions.
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
- Solver backend adoption is deferred behind the neutral contract; SolveSpace is reference-only due GPLv3, and SciPy remains the leading permissive candidate after its first benchmark.
- The first SciPy benchmark decision is `promising_not_ready`; residual-based feasibility, degeneracy handling, timeout/cancellation, packaging, and broader adversarial cases are required before adoption.

## Next Highest-Value Work

Complete the remaining Gate B geometry/editing envelope (polyline/center rectangle, slot/polygon, and safe trim/extend/split/offset/pattern flows), then expand exact solver coverage for nonlinear and arc systems.

## Release Status

Not release-ready. The full-product and final release gates in `docs/sketchmath/product_spec.md` remain open.
