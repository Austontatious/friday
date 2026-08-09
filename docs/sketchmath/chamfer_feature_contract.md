# SketchMath Chamfer Feature Contract

Updated: 2026-08-09

Status: passed for a default-off extrusion-to-terminal-chamfer STEP envelope; overall `SM-FEAT-005` remains partial

## Contract

Chamfer uses the same persistent edge-reference discipline as fillet. A canonical feature stores positive finite `distance_mm`, exactly one extrusion dependency, and one or more exact/recoverable convex `vertical_outer_edge` selectors. Selectors retain producing feature, source/adjacency identity, role, ordinal, geometric signature, 3D endpoints, corner class, and adjacent-edge size bound.

Rebuild refuses missing, ambiguous, duplicate, non-vertical, concave, or oversized selections. It generates deterministic `chamfer_surface` semantic records and marks measurements `kernel_required` rather than estimating post-chamfer volume.

## Kernel and Job Boundary

The supported graph is exactly one independent positive one-sided new-body extrusion followed by one terminal chamfer. The feature worker uniquely matches every semantic endpoint pair to an unused FreeCAD edge, calls `makeChamfer`, and requires a valid positive solid, preserved bounds, and measurable material removal. The STEP result runs through the revision-bound artifact job and records semantic resolution plus transient kernel ordinals only as diagnostics.

Enablement:

- `FRIDAY_SKETCHMATH_CHAMFER_FEATURES_ENABLED=1`
- `REACT_APP_SKETCHMATH_CHAMFER_FEATURES_ENABLED=1`
- document/artifact-job flags and `FreeCADCmd` are also required for STEP

## Evidence

- Canonical tests prove parameter typing, reference reuse, generated surface identity, radius-bound-equivalent distance refusal, and `kernel_required` coverage.
- Live FreeCAD tests chamfer all four edges of a `20 × 10 × 5 mm` box by `2 mm`, yielding the expected `960 mm³` valid solid with unchanged bounds and unique semantic endpoint matches.
- Targeted Playwright proves rectangle → extrusion → distance-3 chamfer → asynchronous STEP → metadata/download → reload in 8.7 seconds.

Checkpoints: `24dfc70`, `3be0baa`, `d06b014`, `f1b0b2c`.

## Explicitly Open

Arbitrary edge picking, concave/horizontal/curved edges, unequal-distance chamfer, multi-stage body graphs, chamfer STL, downstream general kernel-topology reconciliation, pattern/mirror, and shell remain open.
