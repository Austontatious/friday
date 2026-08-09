# SketchMath FreeCAD Adapter

SketchMath uses narrow, headless FreeCAD workers for legacy `extrude_profile` and the supported canonical extrusion-to-fillet STEP graph.

## Boundary

- Input stays typed and deterministic inside SketchMath.
- The extrusion worker receives a single closed outer `profile_2d` plus optional closed hole profiles.
- The feature-graph worker additionally receives a typed fillet radius and canonical semantic outer-vertical-edge descriptors.
- The worker exports STEP and writes validation metadata back to the SketchMath adapter.
- No GUI, no MCP wrapper, no arbitrary Python execution, and no general feature-tree interpreter.

## Strategy

1. Normalize outer winding to counterclockwise.
2. Normalize hole winding to clockwise.
3. Try face-with-holes construction first.
4. If construction, extrusion, export, validation, bbox, or volume sanity checks fail, fall back to boolean subtraction.
5. Accept only validated STEP output.

For fillet graphs, reconstruct that same base, match every semantic edge descriptor to exactly one unused FreeCAD edge by unordered 3D endpoints, apply the radius, and validate solid state, unchanged bounds, and material removal. FreeCAD edge ordinals are diagnostic output only and never become canonical references.

## Validation Rules

- The outer profile must exist, be closed, and form a valid polygon.
- Hole profiles must exist, be closed, and form valid polygons.
- Holes must be strictly inside the outer profile.
- Holes may not touch the outer boundary.
- Holes may not touch or overlap each other.
- The resulting solid must validate in FreeCAD.
- The solid bbox must match the outer profile bbox plus extrusion depth.
- The solid volume must match outer area minus hole area within tolerance.
- A supported convex fillet must produce a valid positive solid, preserve the base bbox, and remove measurable material.

## Metadata

The export metadata records:

- adapter strategy used
- fallback reason, if any
- outer and hole winding information
- expected bbox and volume
- hole count
- fillet radius, base/final volume, semantic endpoint mapping, and transient matched edge ordinals for fillet artifacts

## Browser Download

Committed exports expose a STEP artifact path in `cad_export.artifacts.step_path`.
The browser downloads that artifact through `GET /api/sketchmath/artifacts/step?path=...`.
The API rejects non-STEP files and paths outside the configured SketchMath CAD export root.
