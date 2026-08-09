# SketchMath UI Workspace

## Route

- Open the workspace at `/tools/sketchmath`.
- FRIDAY's main shell shows a `SketchMath` button when its build sets `REACT_APP_SKETCHMATH_ENABLED=1`; the backend must also set `FRIDAY_SKETCHMATH_ENABLED=1`. Both default off.
- The main shell now shows only `Direct Friday` and optional `SketchMath`; `Althing` is hidden from the visible shell UI.

## Runtime Boundary

- Frontend: `frontend/src/components/sketchmath/SketchMathWorkspace.tsx`
- Canvas: `frontend/src/components/sketchmath/SketchCanvas2D.tsx`
- Backend API: `backend/api/sketchmath.py`
- Session store: `backend/sketchmath/service.py`

## State Contract

The workspace keeps these local UI concerns separate:

- `committedContext`
- `selectedEntityIds`
- `topology`
- `selectedRegionId`
- `pendingCommandText`
- `translationOutcome`
- `previewResult`
- `history`
- `theme`
- `tool`
- `viewBoxState`
- `workspaceViewMode`
- `solidPreviewMesh`
- `showDebugLabels`

The backend remains the source of truth for committed geometry and history replay. Session IDs are stored locally so a reload can reopen the same persisted session.

## Delete Contract

- Normal delete submits the full selected set as one typed `delete_entity` command.
- The workspace blocks normal delete when the selection is referenced by constraints or profiles.
- Rectangle edge and corner selections do not delete raw child geometry directly; the UI prompts for whole-rectangle deletion and only then sends a cascade delete for the rectangle bundle.

## Interaction Loop

1. Pick a sketch tool from the toolbar.
2. Draw geometry on the canvas/grid.
3. Use the guided workflow panel: Draw, Dimension, Hole, Extrude, Export.
4. For independent or nested curve boundaries, use Region select, click clearly inside a backend-detected region, then promote it to a profile.
5. Let the solver update the sketch status in the normal UI.
6. Use the Selected Object and workflow controls for profile dimensions, selected-hole edits, delete, extrusion, and STEP export. When document v1 is enabled, use Feature history for revisioned extrusion creation and depth editing.
7. Use Advanced Constraints or Advanced / Debug only when you need manual constraints, raw JSON, measurements, command history, system events, debug labels, or backend details.

The default workspace is canvas-first and hides raw command JSON, proposed command JSON, backend error payloads, internal point/line IDs, system events, and other DSL internals unless the advanced view is opened explicitly. Normal errors are shown as short user-facing messages; raw backend details stay in `Error details` under Advanced / Debug.

## Live Solver Status

- The workspace requests the preview-only `analyze_constraints` command after the committed session changes. Analysis does not mutate geometry or enter undo/redo history.
- Normal mode reports `Under-constrained`, `Fully constrained`, `Over-constrained`, `Conflicting`, or `Partially analyzed` with a short user-facing explanation.
- `Partially analyzed` is intentional when geometry or constraints fall outside the nonlinear adapter's modeled subset. It must not be presented as fully constrained merely because an edit or optimizer run succeeded.
- Request failures report `Analysis unavailable`; an in-flight analysis reports `Analyzing constraints…`.
- Raw coverage, rank/equation counts, remaining DOF, affected constraint/entity IDs, and diagnostics are visible only under Advanced / Debug.
- Advanced / Debug also shows the unified solver backend, run outcome, termination reason, feasibility, and residual availability.
- A successful `solve_constraints` command does not display a generic `Solved` badge. The live analysis result remains the authority for the status label.

## Supported Tools

- Primary canvas modes: Select, Region select, Box select, Draw rectangle, Center rectangle, Polyline, Slot, Polygon, Circle, Arc, 3-point arc, Add hole, Pan / view.
- Secondary/advanced canvas tools: Point, Line, Dimension, Delete.
- Default guided actions: Start rectangle, Apply Rectangle Dimensions, Add center hole, Add Hole placement, selected-hole update, Fix corner, Delete, Extrude, Commit Preview, Revert Preview, Download STEP.
- Dimension actions: Set Length, Set horizontal distance, Set vertical distance, Edit Width, Edit Height, Apply radius, and Apply diameter.
- Advanced constraint actions: Set Angle, Horizontal, Vertical, Coincident, Parallel, Perpendicular, Equal Length, Equal Angle, Fixed, Midpoint, Collinear, Symmetric, Concentric, Tangent, and Solve.
- Safe editing actions: Split midpoint, Trim target, Extend target, Offset, Duplicate, Linear pattern, and Mirror about X=0.
- Fixed accepts one point. Midpoint and Collinear accept three points in selection order. Symmetric accepts reference, target, then two axis endpoints. Concentric accepts two circles/arcs. Tangent accepts a line plus circle/arc or two circle-like entities; an arc contact must lie on its finite sweep.
- Make construction / Make regular converts selected point and line geometry through the typed v0.7 command. Construction lines render dashed, construction points render as hollow/dashed reference points, and the stable entity IDs survive reload.
- Normal rectangle clicks select the profile by default. Edge and corner selection are available in Dimension mode, Advanced Constraints, or modifier-click so the MVP workflow does not accidentally land on raw child geometry.
- Rectangle width/height controls commit typed `set_rectangle_dimension` commands directly and keep the rectangle/profile selected.
- Center rectangle takes a center and corner (or a center-origin drag), then commits the same canonical four-point/four-edge/profile batch as the corner rectangle tool. Shift-drag produces a centered square. No second rectangle representation is persisted.
- Polyline collects an open vertex chain and commits it as one typed batch of stable point identities and linked line segments. Enter or Finish polyline commits; Escape cancels. Adjacent segments share the same endpoint ID, so constraints, profile detection, history, and reload use the ordinary canonical point/line path.
- Slot takes two center points and a positive width, then commits construction centers, linked boundary points, two lines, two finite arcs, and one curve-backed profile through v0.8.
- Polygon takes a center, radius point, and integer side count from 3 through 128, then commits one stable point/line/profile bundle through v0.8.
- Box select uses complete containment: both line endpoints, the full circle/arc bounds, or every profile vertex must lie inside the dragged box.
- Split, trim, and extend currently support line and construction-line targets only. Trim/extend use selection order `target, cutter` and require contact on the finite cutter. A target referenced by a profile or constraint is rejected atomically until general topology repair exists.
- Offset creates an independent line, circle, or arc. Duplicate and linear pattern copy complete linked bundles with remapped stable references; mirror transforms the selected linked bundle in place.
- The Planar regions panel is refreshed from preview-only backend topology after committed session changes. It lists net area and hole count, exposes diagnostics, and can promote a listed region directly.
- Region select disables ordinary entity hit targets while active so a canvas click reaches the backend `select_region` command. Returned outer/hole paths use even-odd SVG fill; boundary and ambiguous selections require an explicit retry or list choice.
- Region promotion commits `make_region_profile`, creates the outer/hole profiles in one history step, and keeps the resulting `source_region_id` across reload. React never calculates or assigns region identity itself.
- Add center hole commits a centered typed `add_profile_hole` command. Add Hole enters placement mode; `Add Centered Hole` or a click inside the selected profile commits the same command shape with the chosen center.
- Existing holes can be selected on canvas. The workflow panel exposes diameter/center controls that commit a typed `update_profile_hole` command and immediately refresh the committed session state.
- The default-off Feature history panel consumes the backend `SketchMathDocument` directly. It shows the monotonic revision, deterministic rebuild status/signature/measurements, creates an extrusion from the selected profile, replaces depth without changing feature identity, and exposes dedicated feature undo/redo.
- Add extrusions attach to the most recent supported extrusion top face by semantic reference. The browser refuses creation when that attachment is unavailable rather than inventing a raw face index.
- With `FRIDAY_SKETCHMATH_HOLE_FEATURES_ENABLED=1` and `REACT_APP_SKETCHMATH_HOLE_FEATURES_ENABLED=1`, each built extrusion exposes numeric X/Y/diameter placement for simple through or blind holes. The request records the current semantic top face; typed counterbore/countersink exists at the API/model layer but is not exposed by this editor.
- With `FRIDAY_SKETCHMATH_REVOLVE_FEATURES_ENABLED=1` and `REACT_APP_SKETCHMATH_REVOLVE_FEATURES_ENABLED=1`, an empty feature history exposes a full-revolve editor. It creates a new body from the selected closed profile about a chosen construction line. Profiles crossing the axis are rejected by rebuild; partial angles, browser add/cut, and revolve artifacts are outside this guarded UI slice.
- With `FRIDAY_SKETCHMATH_ARTIFACT_JOBS_ENABLED=1` and `REACT_APP_SKETCHMATH_ARTIFACT_JOBS_ENABLED=1`, the terminal supported body feature exposes Build STL. The panel displays READY/RUNNING/DONE/FAILED, step, input revision, retry, and Download STL; reload recovers the registered artifact from the document.
- Feature history requires `FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED=1` and `REACT_APP_SKETCHMATH_FEATURE_HISTORY_ENABLED=1`. Canonical commits never invoke the legacy synchronous FreeCAD path. Revision-bound STL jobs are separate, while legacy STEP remains an explicit workflow.
- Selected rectangles show width/height dimension labels on canvas. Selected holes show a diameter label on canvas.
- Profile and hole selection use friendly labels in the default UI. Raw entity IDs remain available only under Advanced / Debug.
- Circle is a first-class selectable entity with direct drawing, driving radius/diameter editing, an extrusion profile adapter, exact center/radius DOF analysis, and optional reuse as a profile hole.
- Arc creates center/start/end points and one canonical center arc; 3-point arc creates start/through/end points and one canonical circumarc. Selection reports radius and sweep, and linked arc source identities participate in nonlinear rank/DOF analysis and finite tangency validation.

## View Controls

- `2D sketch` shows the existing SVG sketch canvas.
- `3D solid` shows the last valid extrusion preview mesh returned by `extrude_profile`.
- `2D sketch` and `3D solid` share a workspace camera model. The 2D sketch plane is treated as the Top camera view, and switching to 3D carries the selected profile target, fit framing, and zoom where practical.
- `Pan / view` mode lets the user drag the 2D canvas view.
- `Zoom in`, `Zoom out`, `Fit sketch`, and `Reset view` manipulate the SVG viewBox only; committed geometry remains session-backed.
- The view widget labels the current surface as `2D sketch plane` or `3D solid preview`.
- In `3D solid`, left-drag orbits/tilts the preview, shift-drag, middle-drag, or right-drag pans, the wheel zooms, and Fit/Reset/Top/Iso/Front controls adjust the camera.
- The 3D preview includes a compact camera HUD with view, azimuth, elevation, zoom, pan, and target values so manual smoke and tests can confirm camera continuity and movement.
- `Tilt to 3D` keeps the same target/framing and moves the camera out of the overhead Top view without changing geometry.
- Before a valid extrusion exists, `3D solid` shows `Extrude a valid profile to preview the 3D solid.`

## 3D Solid Preview

- `extrude_profile` returns a browser-friendly `preview_mesh` payload alongside `cad_export` metadata.
- The mesh contains vertices and indexed triangles for top face, bottom face, outer side walls, and through-hole wall geometry.
- The preview is generated from the same selected profile, stored/profile-requested holes, and extrusion depth used by STEP export.
- The preview is deterministic confidence/orbit geometry, not a STEP parser and not a full CAD feature tree.
- Editing rectangle dimensions or hole diameter/center clears the prior solid preview until the user extrudes again.

## STEP Export

- `extrude_profile` writes STEP artifacts under the configured SketchMath CAD export directory.
- The browser downloads STEP files through `GET /api/sketchmath/artifacts/step?path=...`.
- The API only serves `.step`/`.stp` files under the configured export root.
- The export card shows filename, size when reported, created time when reported, a friendly selected-profile label, extrusion depth, Download STEP, Export again, and Clear export result.
- The export card states that the 3D solid preview uses the same profile, holes, and extrusion depth as the STEP export.
- Failed FreeCAD subprocess exports remove a partial `export.step` if one exists. Broader generated STEP cleanup is manual for this MVP; generated artifacts are runtime output and should not be committed.

## Revisioned STL Export

- Build STL submits a persistent asynchronous request for the selected terminal feature and current document revision.
- The current layered materializer supports vertical extrusion graphs and simple typed holes. It validates analytic bounds/volume, closed edges, safe paths, and content hash before registration.
- STL files are downloaded through `GET /api/sketchmath/artifacts/stl?path=...`, restricted to `.stl` below the configured CAD export root.
- Counterbore/countersink STL, full-graph STEP, cancellation, and automatic artifact cleanup remain outside this UI envelope. See `artifact_job_contract.md`.

## Runtime Dependencies

- The backend runtime must include `shapely>=2.0.0` for profile-hole validation and general planar-region extraction. Missing Shapely is surfaced in the UI as a dependency/configuration message, with the raw backend payload only available under Advanced / Debug.
- The canonical app backend currently runs SketchMath with `FRIDAY_WEB_CONCURRENCY=1` because sessions are cached in the backend process. Multi-worker deployment needs a shared session-store invalidation/pass-through pass before it is safe for this workflow.
- Canonical document v1 is a compatibility adapter over exactly one sketch in the current workspace. Multi-sketch authoring is intentionally refused until the model-tree phase.

## Visual System

- SVG canvas with a technical grid.
- Theme-aware CSS variables for light and dark modes.
- Cyan/blue glow accents with glass panels.
- Internal point and line labels are hidden by default. `Show Advanced / Debug` exposes a debug-label toggle for troubleshooting raw entity IDs.
- The sketch workbench surfaces status, dimensions, constraints, and CAD conversion in the normal flow.

## Non-Goals

- No FreeCAD GUI or broad CAD kernel wrapper.
- No STEP viewer or full 3D CAD workbench in the browser. The interactive preview remains the legacy extrusion mesh; revisioned layered STL is a downloadable artifact, not yet the live viewport model.
- No MCP wrapper.
- No arbitrary Python execution.
- No direct geometry mutation from React state.
