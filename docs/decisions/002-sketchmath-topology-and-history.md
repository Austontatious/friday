# ADR 002: SketchMath topology, circle adapters, and revision history

## Problem

SketchMath lines historically embedded endpoint coordinates while editable point entities lived separately. That made persistent endpoint constraints, automatic profile detection, constrained drag, and deterministic undo/redo unreliable. Circular holes also existed only as polygonal profile metadata, with no selectable general circle primitive.

## Options considered

1. Replace all geometry with a new graph/topology store. This would break existing sessions, commands, rectangle workflows, and CAD adapters.
2. Merge coincident point identities. This would make deletion, selection, replay, and old named references unsafe.
3. Add optional endpoint references to existing line entities, retain point identities, and adapt circles to the existing profile/CAD boundary.

## Decision

- `Line2DEntity` and `ConstructionLine2DEntity` gain optional `start_point_id` and `end_point_id` references. Coordinate-only legacy entities remain valid.
- Horizontal, vertical, and coincident constraints reference point IDs. Coincidence preserves both IDs and establishes equivalence for topology.
- `detect_profiles` is a typed, non-mutating command. It returns deterministic simple line-cycle candidates and never creates profiles implicitly.
- `Circle2DEntity` is the canonical editable circular primitive. `make_circle_profile` creates a polygonal adapter entity for the established preview/FreeCAD profile boundary.
- Active undo history and retained redo history are backend-owned. A new commit clears the redo branch; previews and failures never enter either history.
- The existing SketchMath feature gate covers these capabilities; no second feature flag or alternate execution path is introduced.

## Rationale

This preserves the typed command router, backend session authority, existing serialized sessions, rectangle-hole behavior, and CAD adapter contract while adding the minimum explicit topology needed for constraints and profile discovery.

## Consequences

- New line creation should supply endpoint IDs; old lines can still render and execute legacy commands but cannot receive single-line endpoint constraints until their endpoints are addressable.
- Derived profile geometry must be refreshed after source geometry changes; profile candidates are intentionally invalidated and re-detected instead of mutating automatically.
- Circle extrusion continues through the proven profile adapter, so STEP validation and preview meshing remain unchanged.
- Session persistence stores redo records separately from active history.

## Boundary ownership

- Producer/schema/version owner: `sketchmath.models` and the typed command executor.
- Consumers: Friday backend API/session store and Friday SketchMath frontend.
- Compatibility owner: Friday; additive fields and commands must continue accepting command version `0.1` while new frontend commands use `0.2`.

## Failure modes and trust boundary

- Command payloads and serialized sessions are untrusted and validated by Pydantic.
- Locked-point conflicts produce structured solver errors.
- Branched, open, construction-line, near-but-not-coincident, degenerate, and self-intersecting geometry is not promoted to a valid profile candidate.
- CAD conversion remains a hard explicit command; detection and circle editing have no filesystem side effects.

## Explicit deferrals

- Arc and spline topology.
- Implicit vertices at line crossings.
- General graph-cycle enumeration for branched components.
- Replacing the established polygonal FreeCAD adapter with native analytic-circle transport.
