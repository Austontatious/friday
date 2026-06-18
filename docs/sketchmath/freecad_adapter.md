# SketchMath FreeCAD Adapter

SketchMath uses a narrow, headless FreeCAD worker only for `extrude_profile`.

## Boundary

- Input stays typed and deterministic inside SketchMath.
- The worker receives a single closed outer `profile_2d` plus optional closed hole profiles.
- The worker exports STEP and writes validation metadata back to the SketchMath adapter.
- No GUI, no MCP wrapper, no arbitrary Python execution, and no general feature tree.

## Strategy

1. Normalize outer winding to counterclockwise.
2. Normalize hole winding to clockwise.
3. Try face-with-holes construction first.
4. If construction, extrusion, export, validation, bbox, or volume sanity checks fail, fall back to boolean subtraction.
5. Accept only validated STEP output.

## Validation Rules

- The outer profile must exist, be closed, and form a valid polygon.
- Hole profiles must exist, be closed, and form valid polygons.
- Holes must be strictly inside the outer profile.
- Holes may not touch the outer boundary.
- Holes may not touch or overlap each other.
- The resulting solid must validate in FreeCAD.
- The solid bbox must match the outer profile bbox plus extrusion depth.
- The solid volume must match outer area minus hole area within tolerance.

## Metadata

The export metadata records:

- adapter strategy used
- fallback reason, if any
- outer and hole winding information
- expected bbox and volume
- hole count
