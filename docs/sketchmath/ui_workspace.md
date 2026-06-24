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

The backend remains the source of truth for committed geometry and history replay. Session IDs are stored locally so a reload can reopen the same persisted session.

## Delete Contract

- Normal delete submits the full selected set as one typed `delete_entity` command.
- The workspace blocks normal delete when the selection is referenced by constraints or profiles.
- Rectangle edge and corner selections do not delete raw child geometry directly; the UI prompts for whole-rectangle deletion and only then sends a cascade delete for the rectangle bundle.

## Interaction Loop

1. Pick a sketch tool from the toolbar.
2. Draw geometry on the canvas/grid.
3. Select the resulting geometry and apply dimensions or constraints from the workbench.
4. Let the solver update the sketch status in the normal UI.
5. Convert to CAD only after the sketch is usable.
6. Use the advanced/debug DSL drawer only when you need raw JSON or command inspection.

The default workspace is canvas-first and hides raw command JSON, proposed command JSON, and other DSL internals unless the advanced view is opened explicitly.

## Supported Tools

- Active canvas tools: Select, Point, Line, Rectangle, Dimension.
- Active workbench actions: Set Length, Edit Width, Edit Height, Parallel, Perpendicular, Equal Length, Add Hole, Extrude, Commit Preview, Revert Preview, Download STEP.
- Rectangle width/height controls commit typed `set_rectangle_dimension` commands directly and keep the rectangle/profile selected.
- Add Hole enters placement mode; `Add Centered Hole` or a click inside the selected profile commits a typed `add_profile_hole` command with the current diameter.
- The rectangle inspector exposes `Select profile` so the core workflow does not require selecting hidden profile geometry on the canvas.
- Circle and Arc are intentionally labeled `coming soon` instead of being exposed as active tools. Circular holes are supported through `add_profile_hole`; free-standing circles and arcs are not first-class SketchMath entities in this MVP.

## STEP Export

- `extrude_profile` writes STEP artifacts under the configured SketchMath CAD export directory.
- The browser downloads STEP files through `GET /api/sketchmath/artifacts/step?path=...`.
- The API only serves `.step`/`.stp` files under the configured export root.
- Generated STEP cleanup is manual for this MVP; generated artifacts are runtime output and should not be committed.

## Visual System

- SVG canvas with a technical grid.
- Theme-aware CSS variables for light and dark modes.
- Cyan/blue glow accents with glass panels.
- Entity labels render on canvas from the underlying SketchMath entity names.
- The sketch workbench surfaces status, dimensions, constraints, and CAD conversion in the normal flow.

## Non-Goals

- No FreeCAD GUI or broad CAD kernel wrapper.
- No 3D preview in the browser.
- No MCP wrapper.
- No arbitrary Python execution.
- No direct geometry mutation from React state.
