# SketchMath Golden Mounting Plate v1

Updated: 2026-08-09

Status: passed for canonical rebuild, semantic recovery, serialization, terminal fillet, native STEP validation, resumable registration, and reload; the full browser parameter-edit scenario remains partial

## Canonical Part

`build_golden_mounting_plate()` defines one body and one sketch with eight ordered features matching the release fixture:

1. 80 × 50 × 5 mm new-body plate.
2. Four Ø5 mm through holes at `(7,7)`, `(73,7)`, `(73,43)`, and `(7,43)`.
3. A centered analytic Ø30 mm circular boss, additive from Z=5 to Z=13 mm.
4. A centered Ø10 mm through-hole spanning Z=0..13 mm.
5. A terminal 2 mm fillet over the four semantic outer vertical plate edges.

Every subtractive/additive feature uses a semantic face selector. The terminal fillet retains source/adjacency signatures and unordered 3D endpoint descriptors; transient FreeCAD edge ordinals remain artifact diagnostics only.

## Geometric Ledger

- Body bounds: `(0, 80, 0, 50, 0, 13)` mm.
- Positive volume before holes: `80×50×5 + π×15²×8 = 20000 + 1800π mm³`.
- Removed hole volume: four `Ø5×5` cylinders plus one `Ø10×13` cylinder, or `450π mm³`.
- Pre-fillet volume: `20000 + 1350π mm³`.
- Four 2 mm corner fillets remove `80(1−π/4) mm³`.
- Final expected kernel volume: `19920 + 1370π mm³`.
- Expected through-hole count: five.

The parameter-intent test widens the plate to 100 mm while keeping corner holes 7 mm from the relevant edges and recentering the boss/through-hole at X=50. A second edit changes all four corner holes to Ø6 without replacing feature IDs. Downstream face/edge references recover semantically.

## STEP and Job Evidence

The bounded feature-graph worker executes the seven analytic pre-finish operations, validates their exact canonical volume/bounds, uniquely matches the four fillet selectors, calls native FreeCAD `makeFillet`, and exports revision-8 STEP. Validation asserts:

- valid positive one-solid result with exact 0..80, 0..50, 0..13 mm bounds;
- final volume within `1e-5 mm³` of `19920 + 1370π`;
- four Ø5 cylindrical hole faces, a Ø10 through-hole face, and an Ø30 boss face;
- four selected fillet edges and 2 mm radius;
- revision-bound READY/RUNNING/DONE registration, idempotent replay, persisted artifact metadata, and session reload.

Layered STL deliberately refuses the terminal kernel-only fillet with `unsupported_stl_feature_type`; it does not silently omit the feature.

## Remaining Acceptance Work

The widened/Ø6 canonical edit is not yet driven through one browser-visible undo/redo workflow and has not produced its own post-edit STEP artifact. Those proofs, plus full browser history-tree acceptance, remain required before declaring the Section 29 and release-train gates complete.

Evidence: `sketchmath/features/golden_mounting_plate.py`, `sketchmath/cad/freecad_feature_graph.py`, `tests/test_sketchmath_golden_mounting_plate.py`; checkpoints `5973c89` and `3e309de`.
