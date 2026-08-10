# SketchMath Linear Pattern Feature Contract

Updated: 2026-08-09

Status: passed for a bounded feature-level hole-pattern rebuild and browser history envelope; kernel artifact export remains open.

## Enablement

- Backend: `FRIDAY_SKETCHMATH_PATTERN_FEATURES_ENABLED=1`
- Frontend: `REACT_APP_SKETCHMATH_PATTERN_FEATURES_ENABLED=1`
- The document-v1, feature-history, and hole feature flags remain prerequisites.

Both new flags default off.

## Canonical Model

`linear_pattern` is a persisted `FeatureRecord`, not a sketch transform. Its typed parameters are:

- integer `count` from 2 through 128, including the seed;
- positive finite `spacing_mm`;
- finite, non-zero 2D `direction_xy`, normalized during rebuild;
- fixed `operation: modify`.

The feature has exactly one explicit seed dependency. The stable initial envelope accepts a built terminal hole whose target is an extrusion. The pattern preserves the seed feature and creates instances 1 through `count - 1`.

## Rebuild and Refusal

Rebuild derives every center from the seed position, normalized direction, spacing, and instance index. It computes exact additional removed volume, generated-instance bounds, hole count, and copied semantic topology. Each generated reference records its seed reference, instance index, and X/Y offset so output identity changes deterministically when pattern properties change.

The candidate document is rejected atomically when:

- the seed dependency is missing, duplicated, unbuilt, or not a supported hole;
- the hole target is not a supported extrusion;
- an instance crosses the target material boundary;
- an instance overlaps the seed or another instance;
- count, spacing, or direction fails typed validation.

## Browser and Persistence

The guarded feature-history panel exposes count, spacing, and direction X/Y on a terminal hole. Creation and replacement use the ordinary revision-checked feature command path, so stable ID, rename, suppression, undo, redo, disk reload, and deterministic signatures use the existing canonical history machinery.

## Current Boundary

This checkpoint does not claim shell, patterns of add/cut extrusions or revolves, arbitrary 3D axes, overlapping boolean reconciliation, STL, or STEP. Full-circle hole patterns and bounded sketch-line hole mirrors are covered separately by `circular_pattern_feature_contract.md` and `mirror_feature_contract.md`; partial circular arcs and plane mirrors remain open.

## Verification

- `python3 -m pytest -q tests/test_sketchmath_feature_history.py tests/test_sketchmath_api.py`
- `python3 -m sketchmath.schemas.generate --check`
- `cd frontend && CI=true npm test -- --runInBand --watchAll=false --runTestsByPath src/components/sketchmath/SketchMathWorkspace.test.tsx`
- `cd frontend && npm run build`
