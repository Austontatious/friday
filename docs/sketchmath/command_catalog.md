# SketchMath Command Catalog

SketchMath owns a deterministic 2D command layer under the FRIDAY gateway.

The canonical machine-readable contracts are generated from the Pydantic models with `python3 -m sketchmath.schemas.generate`. Command version `0.1` remains compatible for the original command set; browser topology/circle commands use version `0.2`; non-mutating solver analysis uses version `0.3`; driving axis and circle dimensions use version `0.4`; canonical arc commands use version `0.5`; the additional Gate B constraint families use version `0.6`. Undeclared versions and command types are rejected as `invalid_command` before execution.

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
- STEP downloads are served through `/api/sketchmath/artifacts/step?path=...`; the API only serves `.step`/`.stp` files inside the configured SketchMath CAD export root.
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
- `define_profile`
  - Creates or replaces an explicitly supplied profile entity after model validation.
- `delete_entity`
  - Removes the full selected set when every selected entity is unlocked and unreferenced.
  - `parameters.cascade=true` is reserved for semantic parent-object deletion, such as deleting a whole rectangle bundle after the UI has warned the user.
- `set_distance`
  - Repositions selected points to enforce a target distance.
- `set_horizontal_distance` / `set_vertical_distance`
  - Version `0.4` driving constraints over the selected point pair.
  - The positive dimension preserves the pair's current axis direction and moves point A, point B, or both according to the stored anchor.
  - Reapplying the same axis dimension to the same point pair replaces that axis constraint rather than stacking a duplicate.
- `set_radius` / `set_diameter`
  - Version `0.4` driving dimensions for one selected circle; values accept canonical length units and update the circle/profile geometry.
  - A circle has one active radius-or-diameter dimension. Switching forms or editing the value replaces the prior circle dimension.
- `set_rectangle_dimension`
  - Rebuilds a semantic rectangle bundle when the user edits width or height.
  - Updates the four corner points, four generated edges, and closed profile together.
  - This command is intentionally separate from `set_distance`: plain point distance edits do not carry enough rectangle/profile ownership to preserve the semantic rectangle bundle.
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
- `make_horizontal`
  - Aligns two addressable points horizontally and persists a horizontal constraint.
- `make_vertical`
  - Aligns two addressable points vertically and persists a vertical constraint.
- `make_coincident`
  - Makes two point identities coincident without merging their stable IDs.
- `make_fixed`
  - Version `0.6`; stores the selected point's current coordinates as a fixed-point constraint and rejects later conflicting drags without partial mutation.
- `make_midpoint`
  - Version `0.6`; selection order is midpoint, segment start, segment end. Moves the midpoint to the exact average and participates in exact linear DOF analysis.
- `make_collinear`
  - Version `0.6`; selection order is reference start, reference end, moving point. Projects the moving point onto the infinite reference line.
- `make_symmetric`
  - Version `0.6`; selection order is reference point, target point, axis start, axis end. Reflects the target across the infinite axis.
- `make_concentric`
  - Version `0.6`; moves the second selected circle or arc center onto the first. Circle-to-circle concentricity participates in exact linear DOF analysis; arc participation remains partial.
- `make_tangent`
  - Version `0.6`; supports line-to-circle and circle-to-circle closed-form tangency with external or internal circle tangency.
  - Finite-arc tangency is explicitly rejected with `error_code=unsupported_arc_tangency`; it is not approximated as full-circle tangency.
- `solve_constraints`
  - Runs the conservative 2D solver over stored constraints through the unified `SolverRunResult` path.
  - Applies only an accepted `solved` coordinate patch. Under-constrained, inconsistent, redundant, and failed proposals return structured errors with the run result and do not commit partial geometry.
- `analyze_constraints`
  - Version `0.3`, preview-only, and non-mutating.
  - Reports exact DOF for the covered linear subset: point and circle scalar variables; locked/fixed points/circles; horizontal, vertical, coincident, midpoint, circle concentricity, horizontal/vertical distance, radius, and diameter constraints.
  - Returns explicit `partial` or `unknown` coverage instead of inventing DOF for nonlinear distance/angle/relation constraints, coordinate-only legacy geometry, or other unmodeled entities.
  - Reports consistency and proven redundancy separately; a deterministic conflict ID is not claimed to be a minimal conflict set.
  - Returns the same unified `solver_run` envelope as solve mode while retaining `solver_analysis` compatibility metadata for live status.
- `move_point`
  - Drags one addressable point while preserving the currently supported linked constraints.
- `detect_profiles`
  - Non-mutating detection of deterministic simple closed line cycles; candidates require explicit promotion.
- `make_profile`
  - Detects a closed 2D profile and stores its area and winding.
- `define_circle`
  - Creates a selectable first-class circle with center, radius, and optional center-point identity.
- `update_circle`
  - Edits the center/radius of an existing circle through the typed command path.
- `define_arc`
  - Version `0.5`; creates the canonical `arc_2d` representation from center/start/end plus direction or from start/through/end.
  - Degenerate or collinear inputs return a structured `invalid_arc_geometry` error and never enter history.
- `update_arc`
  - Version `0.5`; edits canonical center/radius/start/sweep values or replaces the complete construction definition.
  - Optional source point IDs keep point moves and persisted arc geometry synchronized.
- `make_circle_profile`
  - Creates the deterministic polygonal adapter profile used by the current preview/FreeCAD boundary.
- `add_profile_hole`
  - Adds a circular inner `profile_2d` hole to a selected closed profile.
  - Preview mode returns the updated outer profile plus hole entity without mutating session state.
  - Commit mode persists the hole, updates the outer profile's `holes` list, and records replayable history.
  - Invalid diameter, missing profile selection, centers outside the profile, and holes that touch or exceed profile bounds return structured selection errors.
- `update_profile_hole`
  - Replaces an existing inner `profile_2d` hole's circular geometry while preserving its id and parent profile reference.
  - Selection must include the parent profile id and existing hole id.
  - Parameters include positive `diameter`, `unit`, and `center`.
  - The command re-runs profile-hole validation before commit, so resized or moved holes must remain strictly inside the parent profile and non-overlapping.
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
- `batch`
  - Applies a validated list of typed subcommands atomically to a working copy before commit.
- `extrude_profile`
  - Consumes one closed outer `profile_2d` plus optional closed hole profiles and exports a STEP solid through the headless FreeCAD adapter.
  - If `parameters.holes` is omitted, stored `profile.holes` are used.
  - The adapter first tries face-with-holes construction, then falls back to boolean subtraction if construction, extrusion, export, validation, bbox, or volume sanity checks fail.
  - The export metadata records the strategy used plus profile winding information so hole orientation is not dependent on user-created polygon order.
  - The result metadata also includes `preview_mesh`, a deterministic browser mesh for the same selected profile, holes, and extrusion depth. The mesh contains vertices and indexed triangles labelled as `top`, `bottom`, `outer_wall`, and `hole_wall`, plus metadata for profile id, extrusion depth, hole count, units, triangle count, vertex count, and bbox.

## Constraint Primitives

- `distance_constraint`
- `horizontal_distance_constraint`
- `vertical_distance_constraint`
- `radius_constraint`
- `diameter_constraint`
- `angle_constraint`
- `parallel_constraint`
- `perpendicular_constraint`
- `equal_length_constraint`
- `equal_angle_constraint`
- `horizontal_constraint`
- `vertical_constraint`
- `coincident_constraint`
- `fixed_point_constraint`
- `midpoint_constraint`
- `collinear_constraint`
- `symmetric_constraint`
- `concentric_constraint`
- `tangent_constraint`

Locked entities act as fixed anchors. The production solver only moves unlocked points, and it prefers closed-form cases over iterative search. Solver analysis uses the versioned numerical policy in `sketchmath/geometry/tolerances.py`; those values are computational tolerances, not manufacturing tolerances.
Profile hole validation is strict: holes must be closed polygons, strictly inside the outer profile, non-touching, and non-overlapping.

## Frontend Dimension Payloads

Edit Width and Edit Height in the browser workspace submit typed `GeometryCommand` payloads through preview first. Commit resubmits the same command with `mode: "commit"` after the user accepts the preview.

Edit Width payload:

```json
{
  "version": "0.1",
  "command_id": "set_rectangle_dimension_<generated>",
  "mode": "preview",
  "command_type": "set_rectangle_dimension",
  "selection": [
    "rect_<id>_a",
    "rect_<id>_b",
    "rect_<id>_c",
    "rect_<id>_d",
    "rect_<id>_ab",
    "rect_<id>_bc",
    "rect_<id>_cd",
    "rect_<id>_da",
    "profile_rect_<id>"
  ],
  "parameters": {
    "dimension": "width",
    "value": 60,
    "unit": "mm"
  }
}
```

Edit Height payload:

```json
{
  "version": "0.1",
  "command_id": "set_rectangle_dimension_<generated>",
  "mode": "preview",
  "command_type": "set_rectangle_dimension",
  "selection": [
    "rect_<id>_a",
    "rect_<id>_b",
    "rect_<id>_c",
    "rect_<id>_d",
    "rect_<id>_ab",
    "rect_<id>_bc",
    "rect_<id>_cd",
    "rect_<id>_da",
    "profile_rect_<id>"
  ],
  "parameters": {
    "dimension": "height",
    "value": 25,
    "unit": "mm"
  }
}
```

Add Hole payload:

The browser workspace exposes Add Hole only when a semantic rectangle/profile is selected. Add Hole enters placement mode: the user can preview the default centered hole or click inside the selected profile to send the same `add_profile_hole` command with the clicked `parameters.center`.

```json
{
  "version": "0.1",
  "command_id": "add_profile_hole_<generated>",
  "mode": "preview",
  "command_type": "add_profile_hole",
  "selection": ["profile_rect_<id>"],
  "parameters": {
    "diameter": 12,
    "unit": "mm",
    "center": [280, 170]
  }
}
```

Update Hole payload:

The browser workspace exposes this when an existing hole is selected. It is used for post-placement diameter and center edits without adding general circle sketch entities.

```json
{
  "version": "0.1",
  "command_id": "update_profile_hole_<generated>",
  "mode": "commit",
  "command_type": "update_profile_hole",
  "selection": ["profile_rect_<id>", "hole_profile_rect_<id>_<command_id>"],
  "parameters": {
    "diameter": 8,
    "unit": "mm",
    "center": [280, 170]
  }
}
```

Extrude payload:

The browser workspace exposes Extrude only for a selected closed profile. It sends a typed `extrude_profile` preview command, shows a textual success state for the accepted profile/hole count, renders the returned `preview_mesh` in the `3D solid` view, and exposes Export STEP after Commit Preview returns a STEP artifact path.

```json
{
  "version": "0.1",
  "command_id": "extrude_profile_<generated>",
  "mode": "preview",
  "command_type": "extrude_profile",
  "selection": ["profile_rect_<id>"],
  "parameters": {
    "depth": 10,
    "depth_unit": "mm",
    "direction": "positive_normal",
    "output_format": "step"
  }
}
```

Stored profile holes are included by the backend when `parameters.holes` is absent, so rectangle/profile hole UX does not need a second frontend hole list.

## Validation Errors

- `missing_entity`
- `wrong_entity_type`
- `missing_parameter`
- `unsupported_command_type`
- `locked_entity_mutation`
- `invalid_units`
- `invalid_command`

## Constraint Solver Limits

- No general nonlinear CAD solving yet.
- No full CAD feature tree, trimming workflow, or sketch solver beyond the supported closed-form cases.
- First-class circles are supported. Arc entities remain deferred and the UI labels Arc as coming soon.
- Profile detection is limited to deterministic simple line cycles; nested/general planar-region extraction remains deferred.
- No arbitrary Python execution.
- No hidden geometry mutation outside typed commands.
- Ambiguous or under-constrained input returns `clarification_required`.
- Conflicting locked geometry returns `solver_error`.
- Extrusion is intentionally narrow: closed 2D profiles only, STEP output only, and no GUI/MCP integration.

## Eval Runner Usage

- Run semantic SketchMath evals with:
  - `python3 -m sketchmath.evals.run_sketchmath_evals`
- The runner loads geometry and translator contract cases from `evals/cases/sketchmath_*.json`, executes geometry cases against the deterministic executor, executes translator cases against the deterministic translator helper, and writes `evals/sketchmath_semantic_results.json`.
- Geometry evals include v0.2 circle, horizontal-constraint, and profile-detection coverage plus the `extrude_profile` adapter with hole validation and STEP metadata checks when present.

All geometry changes must continue to flow through typed `GeometryCommand` objects. The gateway owns translation and policy boundaries; SketchMath owns geometry execution only.

## Non-Goals

- No full drafting UI or arbitrary CAD feature tree beyond the current focused browser workspace loops.
- No FreeCAD GUI, MCP wrapper, arbitrary Python execution, or general CAD feature tree.
- No full CAD sketcher solver.
