# SketchMath Shell Feature Contract

Updated: 2026-08-09

Status: passed for a bounded rectangular top-open shell with deterministic rebuild, guarded browser editing, and native STEP validation.

## Enablement

- Backend: `FRIDAY_SKETCHMATH_SHELL_FEATURES_ENABLED=1`
- Frontend: `REACT_APP_SKETCHMATH_SHELL_FEATURES_ENABLED=1`
- Document-v1, feature-history, and artifact-job flags remain prerequisites for the full browser-to-STEP lifecycle.

Both shell flags default off.

## Canonical Model

`shell` is a persisted feature record with positive finite `thickness_mm`, fixed `opening: top`, fixed `operation: modify`, exactly one base-extrusion dependency, and exactly one semantic top-face opening selector.

The stable initial graph is deliberately bounded to one positive, one-sided, independent new-body extrusion from a solid axis-aligned rectangular profile. The body may contain only that base and the shell.

## Rebuild and Refusal

For outer bounds `(xmin, xmax, ymin, ymax, zmin, zmax)` and thickness `t`, rebuild defines the open-top cavity as:

`(xmin+t, xmax-t, ymin+t, ymax-t, zmin+t, zmax)`.

It reports exact removed volume, cavity bounds, floor area, one `shell_floor`, and four stable `shell_inner_wall` references. The shell is rejected atomically for an unresolved/missing opening face, non-rectangular or holed profile, unsupported body graph/extent/direction, or thickness that leaves non-positive inner width, height, or cavity depth.

## Native STEP

The revision-bound feature graph sends the exact cavity bounds to FreeCAD, subtracts a native box cutter, validates final volume and unchanged outer bounds against the rebuild ledger, then exports STEP. The 20×10×10 mm fixture with 1 mm thickness validates at 704 mm³ and outer bounds 0..20 × 0..10 × 0..10. Shell STL remains explicitly unsupported.

## Browser and Persistence

The guarded feature-history panel exposes thickness on a supported terminal extrusion, records the current semantic top face, creates the shell, replaces thickness without changing feature identity, and offers STEP only. Canonical feature history provides revision checks, undo/redo, deterministic signatures, and disk reload.

## Current Boundary

Curved/non-rectangular shells, multiple removed faces, outward/mid-plane thickness, shells after other body operations, variable thickness, general kernel face matching, and shell STL remain open.

## Verification

- `python3 -m pytest -q tests/test_sketchmath_feature_history.py tests/test_sketchmath_api.py tests/test_sketchmath_feature_artifact.py`
- `python3 -m sketchmath.schemas.generate --check`
- `cd frontend && CI=true npm test -- --runInBand --watchAll=false --runTestsByPath src/components/sketchmath/SketchMathWorkspace.test.tsx`
- `cd frontend && npm run build`
