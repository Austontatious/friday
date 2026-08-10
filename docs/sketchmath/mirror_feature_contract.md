# SketchMath Feature Mirror Contract

Updated: 2026-08-09

Status: passed for a bounded hole-feature mirror rebuild and browser history envelope; kernel artifact export remains open.

## Enablement

- Backend: `FRIDAY_SKETCHMATH_MIRROR_FEATURES_ENABLED=1`
- Frontend: `REACT_APP_SKETCHMATH_MIRROR_FEATURES_ENABLED=1`
- Document-v1, feature-history, and hole flags remain prerequisites.

Both mirror flags default off.

## Canonical Model

`mirror` is a persisted feature record. It carries one stable `mirror_line_entity_id`, fixed `operation: modify`, and exactly one explicit seed dependency. The current envelope supports a terminal hole seed on an extrusion. The mirror reference may resolve to an `axis_2d`, line, or construction line in the seed sketch.

## Rebuild and Refusal

Rebuild resolves and normalizes the referenced line, projects the hole center onto it, and reflects the center exactly. It reports the additional removed volume, mirrored-instance bounds, hole count, and copied semantic topology. Generated references retain the seed reference, normalized line geometry, mirrored center, and X/Y offset.

The candidate is rejected atomically when:

- the stable line is missing, zero-length, or not a line/axis;
- the seed lies on the mirror line;
- the mirrored instance overlaps the seed;
- the mirrored hole crosses target material;
- the seed/target graph is outside the supported hole-on-extrusion envelope.

## Browser and Persistence

The guarded feature-history panel selects from stable construction lines, creates the mirror, and can replace the line without changing feature identity. Revision checks, deterministic signatures, undo/redo, and disk reload use canonical feature history.

## Current Boundary

This checkpoint is hole-only and sketch-line-based. Plane/face mirrors, other feature seeds, nested mirror execution, and mirror STL/STEP remain open. The bounded rectangular shell is documented separately in `shell_feature_contract.md`.

## Verification

- `python3 -m pytest -q tests/test_sketchmath_feature_history.py tests/test_sketchmath_api.py`
- `python3 -m sketchmath.schemas.generate --check`
- `cd frontend && CI=true npm test -- --runInBand --watchAll=false --runTestsByPath src/components/sketchmath/SketchMathWorkspace.test.tsx`
- `cd frontend && npm run build`
