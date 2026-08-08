# SketchMath Arc Geometry Contract

## Canonical entity

`arc_2d` is the single persisted representation for center and three-point arcs. It stores:

- `center` and positive `radius` in the selection context's length units;
- `start_angle_deg` normalized to the canonical angular origin;
- signed `sweep_angle_deg`, non-zero and strictly less than one full turn;
- `construction=center|three_point` as editing provenance;
- optional stable center/start/through/end point IDs.

Angles follow the `canvas_2d` frame: zero points along positive X and positive sweep follows increasing canvas angle, which is clockwise on the SVG canvas. The typed center command accepts the user-facing `clockwise|counterclockwise` direction and converts it to the canonical signed sweep.

The entity does not persist redundant start/end coordinates. They are derived from center, radius, start angle, and sweep. When source point IDs are present, point moves recompute the canonical arc through the normal linked-geometry synchronization path.

## Commands

- `define_arc`, version `0.5`
  - `construction=center`: requires center, start, end, and direction.
  - `construction=three_point`: requires start, through, and end.
  - Canonical center/radius/start/sweep parameters are also accepted by the entity-upsert and persistence boundary.
- `update_arc`, version `0.5`
  - Updates canonical fields or reconstructs the arc from a complete construction payload.

Both commands participate in preview/commit, batch history, undo/redo, disk persistence, schema validation, and structured errors. Center/start coincidence, center/end coincidence, equal start/end directions, zero/full sweeps, and collinear three-point input are rejected as `selection_resolution_error` with `error_code=invalid_arc_geometry`.

## Solver boundary

Arc geometry is intentionally reported in `SolverAnalysis.unmodeled_entity_ids`, making coverage `partial`. The live workspace therefore says `Partially analyzed` instead of inventing arc DOF or feasibility. The unified `SolverRunResult` remains the future seam for adding arc equations.

## Current UI

The toolbar exposes `Arc` for center/start/end placement and `3-point arc` for start/through/end placement. Each placement creates stable source point entities plus one canonical arc in an atomic typed batch. The SVG path is always derived from the canonical entity, and the same paths are recovered after a browser reload.
