# SketchMath Golden Mounting Plate v1

Updated: 2026-08-09

Status: passed for canonical rebuild, reference recovery, serialization, and layered STL geometry; not the full release acceptance part

## Canonical Part

`build_golden_mounting_plate()` defines one body and one sketch with seven ordered features:

1. 100 × 60 × 8 mm new-body plate.
2. Four 6 mm edge-offset through holes at `(12,12)`, `(88,12)`, `(88,48)`, and `(12,48)`.
3. A 30 × 20 × 5 mm raised boss attached to the plate top face, spanning Z=8..13 mm.
4. A 10 mm through-hole on the boss top face spanning the cumulative body depth Z=0..13 mm.

Every subtractive/additive feature uses a semantic face selector. The four mounting holes and boss reference the stable plate top role; the boss hole references the stable boss top role.

## Analytic Ledger

- Body bounds: `(0, 100, 0, 60, 0, 13)` mm.
- Positive volume: `100×60×8 + 30×20×5 = 51000 mm³`.
- Removed volume: four `Ø6×8` cylinders plus one `Ø10×13` cylinder, or `613π mm³`.
- Expected cumulative volume: `51000 − 613π mm³`.
- Expected through-hole count: five.

The width-edit test changes the plate profile from 100 mm to 120 mm without replacing feature IDs or selectors. Downstream plate references recover semantically, body width becomes 120 mm, and the volume increases by exactly `20×60×8 mm³`.

## STL Evidence

The terminal `feature_boss_hole` produces a two-layer ASCII STL. Validation asserts:

- deterministic content hash across deep-copy rebuild/materialization;
- exact 0..100, 0..60, 0..13 mm bounds;
- mesh volume within 0.5 mm³ of the analytic ledger;
- every undirected mesh edge has incidence two;
- zero non-manifold edges;
- revision-safe output path ending in `_r7.stl`.

The circular mesh boundary is a declared deterministic 360-segment approximation; the analytic volume and approximation error are preserved separately.

## Explicitly Open

This fixture does not yet contain fillets, does not prove counterbore/countersink STL, and does not produce a full-graph STEP artifact without a kernel worker. It is therefore a golden feature/artifact proof for the supported vertical envelope, not completion of product-spec acceptance scenario 1.

Evidence: `sketchmath/features/golden_mounting_plate.py`, `tests/test_sketchmath_golden_mounting_plate.py`, checkpoint `a3d705c`.
