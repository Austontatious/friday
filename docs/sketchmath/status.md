# SketchMath Development Status

Updated: 2026-08-08

Current phase: Phase 0 — stabilize and land

Gate: Gate A implementation passed locally; remote landing in progress

## Baseline

- Audited checkout: `21b8153`
- Latest SketchMath product commit: `8236828`
- Branch: `phase0-stabilize`
- Audit working tree: clean
- Verified remote `phase0-stabilize`: `4ed99b3`
- Local branch delta at program start: 68 commits ahead; 24 commits touch SketchMath code/docs/tests
- Current local Gate A implementation commit: `799a7db`

## Implemented Capabilities

- Typed deterministic 2D command execution with preview/commit.
- Point, line, rectangle, circle, and circular-hole workflows.
- Existing closed-form distance/angle/parallel/perpendicular/equal constraints.
- Horizontal, vertical, and coincident constraints with endpoint-aware dragging.
- Simple deterministic line-loop profile detection and explicit promotion.
- Rectangle, detected-line, circle, and holed-profile extrusion.
- Orbitable deterministic 3D preview plus FreeCAD-backed STEP export/download.
- Persistent sessions and backend-authoritative undo/redo across reload.
- Structured errors and Normal/Advanced UI separation.

## Current Gate A Validation

On 2026-08-08 through `799a7db`:

- 99 focused Python tests passed.
- 42 semantic eval cases passed.
- 42 frontend tests passed across the FRIDAY shell and SketchMath workspace.
- 9 live Playwright workflows passed with no test-reported console/page errors.
- TypeScript compile passed.
- Canonical generated schemas match the Pydantic models.
- Production frontend build compiled successfully with no SketchMath source warning.
- Docker Compose config passed.
- 13 repository standards tests passed.

The build still reports the repository-wide stale Browserslist database notice. Updating frontend dependency metadata is intentionally deferred from the SketchMath-only Gate A slice.

## Active Phase 0 Work

Completed locally:

1. Reconciled v0.1/v0.2 runtime, generated JSON schemas, frontend command types, docs, and eval contracts.
2. Corrected stale supported-envelope documentation.
3. Made frontend/backend feature-gate defaults explicitly off and aligned deployment configuration.
4. Removed the unused SketchMath frontend state/build warning.
5. Passed the complete Gate A regression suite.

Remaining:

6. Land only the deliberate validated SketchMath baseline and record its remote commit.

## Known Limitations

- Arc geometry is not implemented.
- Solver coverage is a conservative closed-form subset with coarse status and no generalized exact DOF.
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

## Next Highest-Value Work

Complete Gate A, then define the canonical document/solver boundary and implement the smallest defensible Phase 1 slice that improves real parametric behavior without creating a second model path.

## Release Status

Not release-ready. The full-product and final release gates in `docs/sketchmath/product_spec.md` remain open.
