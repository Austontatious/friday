# SketchMath UI Workspace

## Route

- Open the workspace at `/tools/sketchmath`.
- FRIDAY's main shell shows a `SketchMath` button for the same route when `REACT_APP_SKETCHMATH_ENABLED=1`.
- The main shell now shows only `Direct Friday` and optional `SketchMath`; `Althing` is hidden from the visible shell UI.

## Runtime Boundary

- Frontend: `frontend/src/components/sketchmath/SketchMathWorkspace.tsx`
- Canvas: `frontend/src/components/sketchmath/SketchCanvas2D.tsx`
- Backend API: `backend/api/sketchmath.py`
- Session store: `backend/sketchmath/service.py`

## State Contract

The workspace keeps these local UI concerns separate:

- `committedEntities`
- `selectedEntityIds`
- `pendingCommandText`
- `translationOutcome`
- `sessionMetadata`
- `previewResult`
- `history`
- `theme`
- `tool`
- `viewBoxState`
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
4. Let the solver update the sketch status in the normal UI.
5. Use the Selected Object and workflow controls for profile dimensions, selected-hole edits, delete, extrusion, and STEP export.
6. Use Advanced Constraints or Advanced / Debug only when you need manual constraints, raw JSON, measurements, command history, system events, debug labels, or backend details.

The default workspace is canvas-first and hides raw command JSON, proposed command JSON, backend error payloads, internal point/line IDs, system events, and other DSL internals unless the advanced view is opened explicitly. Normal errors are shown as short user-facing messages; raw backend details stay in `Error details` under Advanced / Debug.

## Supported Tools

- Primary canvas modes: Select, Draw rectangle, Add hole, Pan / view.
- Secondary/advanced canvas tools: Point, Line, Dimension, Delete.
- Default guided actions: Start rectangle, Apply Rectangle Dimensions, Add center hole, Add Hole placement, selected-hole update, Fix corner, Delete, Extrude, Commit Preview, Revert Preview, Download STEP.
- Advanced constraint actions: Set Length, Set Angle, Edit Width, Edit Height, Parallel, Perpendicular, Equal Length, Equal Angle, Solve.
- Normal rectangle clicks select the profile by default. Edge and corner selection are available in Dimension mode, Advanced Constraints, or modifier-click so the MVP workflow does not accidentally land on raw child geometry.
- Rectangle width/height controls commit typed `set_rectangle_dimension` commands directly and keep the rectangle/profile selected.
- Add center hole commits a centered typed `add_profile_hole` command. Add Hole enters placement mode; `Add Centered Hole` or a click inside the selected profile commits the same command shape with the chosen center.
- Existing holes can be selected on canvas. The workflow panel exposes diameter/center controls that commit a typed `update_profile_hole` command and immediately refresh the committed session state.
- Selected rectangles show width/height dimension labels on canvas. Selected holes show a diameter label on canvas.
- Profile and hole selection use friendly labels in the default UI. Raw entity IDs remain available only under Advanced / Debug.
- Circle and Arc are intentionally labeled `coming soon` instead of being exposed as active tools. Circular holes are supported through `add_profile_hole`; free-standing circles and arcs are not first-class SketchMath entities in this MVP.

## View Controls

- `Pan / view` mode lets the user drag the 2D canvas view.
- `Zoom in`, `Zoom out`, `Fit sketch`, and `Reset view` manipulate the SVG viewBox only; committed geometry remains session-backed.
- The view widget labels the current surface as `2D sketch plane`.
- `3D orbit coming soon` is disabled because browser 3D preview/orbit is not implemented in this MVP.

## STEP Export

- `extrude_profile` writes STEP artifacts under the configured SketchMath CAD export directory.
- The browser downloads STEP files through `GET /api/sketchmath/artifacts/step?path=...`.
- The API only serves `.step`/`.stp` files under the configured export root.
- The export card shows filename, size when reported, created time when reported, a friendly selected-profile label, extrusion depth, Download STEP, Export again, and Clear export result.
- Failed FreeCAD subprocess exports remove a partial `export.step` if one exists. Broader generated STEP cleanup is manual for this MVP; generated artifacts are runtime output and should not be committed.

## Runtime Dependencies

- The backend runtime must include `shapely>=2.0.0` for profile-hole validation. Missing Shapely is surfaced in the UI as a dependency/configuration message, with the raw backend payload only available under Advanced / Debug.

## Visual System

- SVG canvas with a technical grid.
- Theme-aware CSS variables for light and dark modes.
- Cyan/blue glow accents with glass panels.
- Internal point and line labels are hidden by default. `Show Advanced / Debug` exposes a debug-label toggle for troubleshooting raw entity IDs.
- The sketch workbench surfaces status, dimensions, constraints, and CAD conversion in the normal flow.

## Non-Goals

- No FreeCAD GUI or broad CAD kernel wrapper.
- No 3D preview in the browser. The export card states this explicitly instead of presenting a fake viewer.
- No MCP wrapper.
- No arbitrary Python execution.
- No direct geometry mutation from React state.
