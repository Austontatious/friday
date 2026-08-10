# SketchMath Circular Pattern Feature Contract

Updated: 2026-08-09

Status: passed for a bounded full-circle hole-pattern rebuild and browser history envelope; kernel artifact export remains open.

## Enablement

Circular and linear feature patterns share the paired default-off gates:

- Backend: `FRIDAY_SKETCHMATH_PATTERN_FEATURES_ENABLED=1`
- Frontend: `REACT_APP_SKETCHMATH_PATTERN_FEATURES_ENABLED=1`

The document-v1, feature-history, and hole feature flags remain prerequisites.

## Canonical Model

`circular_pattern` is a persisted feature record with:

- integer `count` from 2 through 128, including the seed;
- finite `center_mm` on the sketch plane;
- fixed full-circle `angle_deg: 360`;
- `counterclockwise` or `clockwise` ordered direction;
- fixed `operation: modify`;
- exactly one explicit hole-seed dependency.

The seed stays in place. Rebuild rotates its radial vector around the declared center at `360 / count` degree increments and creates instances 1 through `count - 1`.

## Rebuild and Refusal

The analytic rebuild reports exact additional removed volume, generated-instance bounds, hole count, and copied semantic topology. Each copied reference records the seed reference, instance index, signed rotation, center, and offset.

Rebuild refuses atomically when the seed is on the pattern center, an instance overlaps another instance, an instance crosses target material, or the seed/target graph is outside the supported hole-on-extrusion envelope.

## Browser and Persistence

The guarded feature-history panel exposes count, center X/Y, and ordered direction. Create and replace use revision-checked feature commands and inherit stable IDs, deterministic signatures, rename/suppression, undo/redo, and disk reload from canonical history.

## Current Boundary

This checkpoint is full-circle and hole-only. Partial arcs, 3D axis references, patterns of other feature types, nested pattern execution, shell, and pattern STL/STEP remain open. The bounded sketch-line hole mirror is documented separately in `mirror_feature_contract.md`.

## Verification

- `python3 -m pytest -q tests/test_sketchmath_feature_history.py tests/test_sketchmath_api.py`
- `python3 -m sketchmath.schemas.generate --check`
- `cd frontend && CI=true npm test -- --runInBand --watchAll=false --runTestsByPath src/components/sketchmath/SketchMathWorkspace.test.tsx`
- `cd frontend && npm run build`
