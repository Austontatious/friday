# ADR: SketchMath Workspace UI Boundary

## Problem
SketchMath now has a browser-visible drawing pad inside FRIDAY. The workspace needs a route, a session API, and a preview/commit UI contract without collapsing the deterministic geometry executor into React state.

## Options Considered
1. Build the workspace entirely in the frontend and keep all geometry state local.
2. Expose SketchMath through a thin HTTP session API and let the frontend act as a client.
3. Embed SketchMath into the existing chat shell as inline controls.

## Decision
Use a dedicated frontend route at `/tools/sketchmath` backed by a thin FRIDAY API namespace under `/api/sketchmath/...`.

## Rationale
- Keeps geometry execution in the typed `sketchmath/` domain package.
- Preserves deterministic preview/commit/revert behavior through the backend session store.
- Avoids direct mutation of committed geometry from React state.
- Makes the workspace independently testable without changing chat routing.

## Consequences
- The UI has a clear session boundary and can be replayed/reverted from history.
- FRIDAY owns the route and transport boundary, while SketchMath continues to own geometry semantics.
- The frontend depends on the SketchMath API contract for preview and commit, so schema changes must stay versioned.

## Explicit Deferrals
- No FreeCAD/OpenCascade integration in the workspace.
- No browser-based solver or arbitrary Python execution.
- No 3D CAD or extrusion workflow in this slice.
