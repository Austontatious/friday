# SketchMath Command Catalog

SketchMath owns a deterministic 2D command layer under the FRIDAY gateway.

## Execution Loop

1. A translator emits a typed `GeometryCommand`.
2. The executor resolves the command against a deep-copied `SelectionContext`.
3. Preview mode computes a result without mutating session state.
4. Commit mode applies the result to session state and appends a replayable history record.
5. Revert removes the last committed operation and rebuilds the session by replaying history from the initial state.
6. Session snapshots persist to disk so a session can be reloaded by ID.
7. A headless FreeCAD adapter can consume a closed `profile_2d` plus optional inner `profile_2d` holes and export a validated STEP artifact without changing SketchMath's source-of-truth geometry.

## FRIDAY Workspace Route

- Open the browser workspace at `/tools/sketchmath`.
- The frontend uses an SVG drawing surface and a local draft state for point creation and line selection.
- The UI talks to the backend session API under `/api/sketchmath/sessions/...`.
- Preview and commit remain distinct: preview updates only the overlay, commit mutates the persisted session, and revert rebuilds from history.
- The frontend never mutates geometry directly outside typed `GeometryCommand` submission.

## Command Catalog

- `measure_distance`
  - Reads two points and returns a scalar distance.
- `measure_angle`
  - Reads two line-like entities and returns the angle between their directions.
- `define_point`
  - Creates or replaces a point entity.
- `define_line`
  - Creates or replaces a line entity.
- `delete_entity`
  - Removes the full selected set when every selected entity is unlocked and unreferenced.
  - `parameters.cascade=true` is reserved for semantic parent-object deletion, such as deleting a whole rectangle bundle after the UI has warned the user.
- `set_distance`
  - Repositions selected points to enforce a target distance.
- `set_line_polar`
  - Rebuilds a line endpoint from length and angle.
- `set_angle`
  - Rotates one unlocked point around an anchored segment to a target angle.
- `make_parallel`
  - Adjusts one unlocked endpoint so a segment becomes parallel to its reference.
- `make_perpendicular`
  - Adjusts one unlocked endpoint so a segment becomes perpendicular to its reference.
- `make_equal_length`
  - Adjusts one unlocked endpoint so a segment matches the reference length.
- `make_equal_angle`
  - Adjusts one unlocked point so a target angle matches a source angle.
- `solve_constraints`
  - Runs the conservative 2D solver over stored constraints.
- `make_profile`
  - Detects a closed 2D profile and stores its area and winding.
- `translate`
  - Shifts selected geometry by a vector.
- `rotate`
  - Rotates selected geometry around an origin.
- `mirror`
  - Mirrors selected geometry across a vertical axis.
- `copy_linear`
  - Duplicates selected geometry along a repeated translation vector.
- `intersect_lines`
  - Creates a deterministic point at the intersection of two line-like entities.
- `project_point_to_line`
  - Creates a deterministic point projected onto a line-like entity.
- `extrude_profile`
  - Consumes one closed outer `profile_2d` plus optional closed hole profiles and exports a STEP solid through the headless FreeCAD adapter.
  - The adapter first tries face-with-holes construction, then falls back to boolean subtraction if construction, extrusion, export, validation, bbox, or volume sanity checks fail.
  - The export metadata records the strategy used plus profile winding information so hole orientation is not dependent on user-created polygon order.

## Constraint Primitives

- `distance_constraint`
- `angle_constraint`
- `parallel_constraint`
- `perpendicular_constraint`
- `equal_length_constraint`
- `equal_angle_constraint`
- `fixed_point_constraint`

Locked entities act as fixed anchors. The solver only moves unlocked points, and it prefers closed-form cases over iterative search.
Profile hole validation is strict: holes must be closed polygons, strictly inside the outer profile, non-touching, and non-overlapping.

## Validation Errors

- `missing_entity`
- `wrong_entity_type`
- `missing_parameter`
- `unsupported_command_type`
- `locked_entity_mutation`
- `invalid_units`

## Constraint Solver Limits

- No general nonlinear CAD solving yet.
- No full CAD feature tree, trimming workflow, or sketch solver beyond the supported closed-form cases.
- No arbitrary Python execution.
- No hidden geometry mutation outside typed commands.
- Ambiguous or under-constrained input returns `clarification_required`.
- Conflicting locked geometry returns `solver_error`.
- Extrusion is intentionally narrow: closed 2D profiles only, STEP output only, and no GUI/MCP integration.

## Eval Runner Usage

- Run semantic SketchMath evals with:
  - `python3 -m sketchmath.evals.run_sketchmath_evals`
- The runner loads geometry and translator contract cases from `evals/cases/sketchmath_*.json`, executes geometry cases against the deterministic executor, executes translator cases against the deterministic translator helper, and writes `evals/sketchmath_semantic_results.json`.
- Geometry evals now include the `extrude_profile` adapter spike with hole validation and validate the exported STEP artifact metadata when present.

All geometry changes must continue to flow through typed `GeometryCommand` objects. The gateway owns translation and policy boundaries; SketchMath owns geometry execution only.

## Non-Goals

- No UI.
- No FreeCAD GUI, MCP wrapper, arbitrary Python execution, or general CAD feature tree.
- No full CAD sketcher solver.
