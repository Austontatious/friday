# SketchMath Open Source Reference Review

This is a reference pass for FRIDAY SketchMath, not an implementation change.
The goal is to stop guessing at sketcher UX and solver architecture by comparing mature open-source parametric sketchers and extracting the smallest viable design for FRIDAY.

## 2026 Gate B Architecture Update

ADR 005 supersedes the earlier frontend-first solver recommendation for the backend-authoritative product architecture. SolveSpace remains reference-only because its official repository is GPL-3.0-or-later. FreeCAD remains an LGPL kernel/oracle behind a subprocess boundary. SciPy `least_squares` is the adopted BSD-licensed production backend behind the solver-neutral proposal/result contract. The adapter closes the benchmark failures documented in `nonlinear_solver_benchmark.md` by classifying feasibility from scaled residuals, using deterministic perturbed seeds, validating finite geometry, and replaying canonical rounded patches; optimizer success alone is never accepted.

## Bottom Line

If we separate the references by what they are best at:

- **Best UX reference for direct-manipulation sketching:** CAD Sketcher
- **Best browser-native architecture reference:** JSketcher
- **Best constraint semantics and topology discipline:** SolveSpace
- **Best candidate for a mature browser-usable solver path:** PlaneGCS via WASM
- **Best lightweight pure-JS solver reference:** Assemble2D

If forced to pick one overall closest match for FRIDAY SketchMath, the answer is:

1. **JSketcher** for the browser/app shape.
2. **CAD Sketcher** for the sketcher UX vocabulary and interaction model.
3. **SolveSpace** for solver correctness, rectangle semantics, and status behavior.

The practical recommendation for FRIDAY is **not** to port a full external sketcher now. Keep the current FRIDAY sketch stack, make the rectangle workflow semantic and parametric, and defer any solver swap until the UI contract is stable.

## Comparison Table

| Project | UX fit | Solver fit | Rectangle behavior | Status / DOF model | Profile / export path | License | Reuse verdict |
|---|---|---|---|---|---|---|---|
| JSketcher | Strong. Browser-based CAD/sketch model with feature/history workflow. | Good. Uses a JS/TS 2D constraint solver. | Web sketcher; rectangle support is present in the project docs/wikis, but the project still treats some sketch tools as in-progress. | Supports dimensions and constraint-driven editing, but the public material is more implementation-oriented than workflow-polished. | Feature/history oriented CAD, with later 3D operations. | Custom license with upstream assignment/commercial licensing terms, not a simple permissive reuse target. | Best architecture inspiration, not a code reuse target. |
| SolveSpace | Medium. Desktop-first, but the workflow is highly relevant. | Very strong. Mature parametric sketcher and solver discipline. | Rectangle topology is treated as fixed; dimensions should change values, not topology. | Strong reference for underdefined / fully defined / overconstrained behavior via DOF reduction. | Sketches feed downstream 3D operations and export workflows. | GPL-3.0-or-later. | Reference-only for FRIDAY unless licensing changes. |
| FreeCAD Sketcher / PlaneGCS | Medium to strong. Sketcher workflow is canonical, but desktop-oriented. | Very strong. PlaneGCS is the FreeCAD Sketcher solver; a WASM wrapper exists. | Good reference for rectangle and constraint behavior inside a sketcher workbench. | Explicit solver/status model; well-established 2D sketch semantics. | Sketches are the base for pads/revolves and other solid features. | FreeCAD is LGPL-2.1; wrapper projects may vary, but FreeCAD-derived solver usage inherits FreeCAD licensing constraints. | Strong solver/reference model. PlaneGCS via WASM is the best technical upgrade candidate if FRIDAY outgrows the current solver. |
| Assemble2D | Medium. Minimal and browser-friendly, but not a full CAD workflow. | Useful. Pure JS geometric constraint solver. | Can model sketch constraints, but it is lighter than a full CAD sketcher. | Energy-based solver; overconstraint is modeled as inability to reach zero energy. | No full feature/history or CAD export story by itself. | MIT. | Best low-friction pure JS solver reference; practical if we want to stay simple. |
| CAD Sketcher | Very strong. Probably the cleanest interaction and vocabulary reference. | Strong, but it is Blender-integrated and builds on SolveSpace concepts. | Rectangle tool, exact dimensions, ESC cancel, selection-first constraint editing, and later conversion are directly relevant. | Clear constraint vocabulary with editable sketches and visible failures. | Converts sketches into downstream Blender geometry, keeping sketches editable. | GPL-3.0. | Best UX reference. Not a direct reuse target for FRIDAY. |

## Project-by-Project Notes

### JSketcher

JSketcher is the closest open-source browser-native analog to FRIDAY SketchMath because it already lives in the same deployment shape:

- browser app
- canvas-based sketcher
- 2D constraint solver
- feature/history modeling
- later 3D operations

That said, its public status is not the same as a polished production sketcher. The repository and wiki show sketch tools and dimensions, but some rectangle/tool coverage is still documented as work in progress. The license is also not a clean permissive reuse path.

**Takeaway:** excellent architectural reference, poor code-reuse candidate.

### SolveSpace

SolveSpace is the best correctness reference for constraint-first sketching:

- rectangle geometry should not be rebuilt as loose lines once the primitive exists
- dimensions should drive the sketch, not replace it
- sketch status should be a first-class user-facing concept
- underdefined and overconstrained states should be understandable, not hidden

SolveSpace is desktop-first, so it is not the closest UI deployment model for FRIDAY, but it is the best reference for how a parametric sketcher should think about geometry and constraints.

**Takeaway:** best semantic model for rectangle constraints and solver status.

### FreeCAD Sketcher / PlaneGCS

FreeCAD Sketcher is the most relevant mature sketcher workflow after SolveSpace. Its solver, PlaneGCS, is especially interesting because a WebAssembly wrapper exists and it is already meant to run outside FreeCAD in browser/node contexts.

This makes PlaneGCS the best “serious solver” upgrade path if FRIDAY eventually outgrows its current lightweight solver and wants a mature constraint engine without moving the whole sketch workflow to a backend service.

The tradeoff is integration complexity:

- larger runtime surface than a custom JS solver
- more build and packaging work
- more solver-specific data translation

**Takeaway:** strongest long-term solver candidate, but not the right first-pass dependency unless the current solver becomes a blocker.

### Assemble2D

Assemble2D is the practical minimal browser-native solver reference:

- TypeScript/JavaScript friendly
- simple to integrate
- constraint vocabulary maps well to sketcher needs
- useful if we want to keep FRIDAY in pure frontend territory

The downside is maturity and completeness. It is useful as a lightweight solver reference, but it is not the same class of battle-tested CAD solver as SolveSpace or PlaneGCS.

**Takeaway:** good fallback if we want the simplest browser-only solver path.

### CAD Sketcher

CAD Sketcher is the best UX reference in this set for the behavior FRIDAY wants:

- sketch-first interaction
- tool palette
- selection-first constraint application
- dimensions as a separate act from drawing
- conversion as a later step
- non-destructive editable sketches

It also uses SolveSpace concepts and constraint vocabulary closely enough that its workflow maps cleanly onto the FRIDAY target.

**Takeaway:** if we want a CAD-like sketcher experience, this is the cleanest interaction model to emulate.

## Direct Answers

### 1. Which reference is closest to our desired FRIDAY SketchMath UX?

**CAD Sketcher** is the closest UX reference.

If the question is instead “which project most closely matches FRIDAY’s browser deployment shape,” then **JSketcher** is the closest.

The combined answer is:

- **CAD Sketcher** for the user interaction model
- **JSketcher** for browser-native architecture
- **SolveSpace** for solver semantics

### 2. Which solver approach is most practical for our current React/frontend stack?

The most practical near-term choice is **keep the current lightweight/custom solver** and make the rectangle workflow semantic first.

Reason:

- it already fits the existing FRIDAY data flow
- it avoids a risky solver swap during UX work
- it keeps the browser experience fast and local
- it lets us prove the product model before introducing a heavier solver runtime

If we decide to upgrade the solver next, the best frontend-compatible path is **PlaneGCS via WASM**.

### 3. Should we use an existing JS/TS solver, use PlaneGCS via WASM, call FreeCAD backend for solving, or keep our current custom lightweight solver?

Recommendation:

1. **Now:** keep the current custom lightweight solver.
2. **Next solver upgrade:** PlaneGCS via WASM.
3. **Fallback/simple alternative:** Assemble2D.
4. **Avoid for default sketch interaction:** FreeCAD backend solving.

Why not FreeCAD backend solving by default:

- higher latency
- more coupling between sketch interaction and server availability
- weaker browser-first feel
- harder to keep the sketcher snappy during drag/preview

Why not jump immediately to PlaneGCS:

- it is the best serious solver path, but it is still an integration project
- FRIDAY needs the UX contract stabilized first

### 4. What is the minimum viable rectangle workflow based on these references?

Minimum viable rectangle workflow:

1. User picks the **Rectangle** tool.
2. Primary gesture is **two-click**:
   - first click sets corner A
   - cursor movement previews the rectangle
   - second click commits corner C
3. Shortcut gesture is **click-drag**:
   - mouse down sets corner A
   - drag previews
   - mouse up commits corner C
4. The tool creates a **semantic rectangle primitive**, not four unrelated strokes.
5. The rectangle commits as four connected edges plus inferred constraints.
6. Width and height are then edited through dimensions, not by manually redrawing geometry.
7. Dragging a corner updates the solved shape while preserving rectangle constraints.
8. Sketch status is always visible.
9. Convert to CAD stays disabled until a valid closed profile exists.

### 5. What entity/constraint data model should SketchMath use?

Use a small, explicit sketch model:

#### Entities

- `point`
- `line`
- `circle`
- `arc`
- `profile`
- optional `construction` variants if needed

#### Constraints

Typed constraints should reference entity ids and, where needed, numeric values:

- `coincident`
- `horizontal`
- `vertical`
- `parallel`
- `perpendicular`
- `equal`
- `length`
- `angle`
- `radius`
- `diameter`
- `midpoint`
- `lock` / `fix`

#### Sketch state

The sketch should carry:

- entity graph
- constraint list
- selected ids
- solver status
- degrees-of-freedom summary
- closed-profile flag
- CAD conversion eligibility

This is enough for a rectangle-first sketcher without dragging in a full feature tree.

### 6. What should remain hidden behind Advanced/Debug?

Keep these hidden by default:

- raw command JSON
- proposed command JSON
- pending command JSON
- command ids
- DSL output
- named-reference internals
- solver trace details
- replay/debug payloads

The default screen should show the sketch, the toolbar, constraints/dimensions, status, and CAD conversion gate. Everything else belongs in an explicitly opened advanced drawer.

### 7. What can be implemented in one focused Codex pass without boiling the ocean?

One focused pass can reasonably deliver:

- rectangle tool as a semantic primitive
- inferred rectangle constraints on commit
- visible dimensions for width and height
- solver status and closed-profile gating
- convert-to-CAD enablement only after a usable profile exists
- advanced/debug drawer for raw JSON and command inspection
- Playwright coverage for the rectangle flow

What should **not** be part of that same pass:

- swapping the solver to PlaneGCS
- importing a full external sketcher
- implementing a feature-history tree
- adding 3D sketch editing
- moving solving to the backend

## Proposed FRIDAY SketchMath Architecture

### Default Surface

The default UI should be a sketcher workbench:

- canvas/grid first
- visible tool palette
- selection tool
- primitive tools
- constraint tools
- dimension tool
- delete/trim
- solve/status indicator
- convert-to-CAD action

### Interaction Model

The canvas is the command surface.

Natural language is optional assistance, not the primary workflow.

The default loop is:

1. choose tool
2. draw geometry
3. select geometry
4. apply dimensions/constraints
5. solve and inspect status
6. convert to CAD only when the sketch is usable

### Data Flow

Keep three layers separate:

- **UI layer:** tool palette, selection, dimensions, status, advanced drawer
- **Sketch model:** entities, constraints, profiles, solver state
- **Command/debug layer:** raw JSON, command ids, replay payloads

This separation is the key to avoiding the “command composer” UX trap.

### Solver Strategy

Short term:

- keep the current solver
- enforce a rectangle as a first-class sketch primitive
- use the solver to preserve constraints and report status

Medium term:

- evaluate PlaneGCS via WASM if the current solver becomes too limiting

Long term:

- only move to a heavier solver or backend flow if SketchMath needs stronger numerical robustness or more complex constraint coverage

## Proposed Rectangle Primitive Behavior

Rectangle should be a true primitive, not a macro that asks users to build four lines manually.

Recommended behavior:

- first click anchors corner A
- second click or drag sets corner C
- preview shows the rectangle live while moving
- `Esc` or right click cancels
- `Shift` optionally forces a square
- delete removes the selected rectangle

On commit, the sketch should infer:

- coincident endpoints
- horizontal top and bottom edges
- vertical left and right edges
- perpendicular adjacent edges
- parallel opposite edges

If dimensions are applied afterward:

- width edits horizontal separation
- height edits vertical separation
- the rectangle remains a rectangle after solve

The result should be a closed profile that can be consumed by CAD generation later.

## Recommended Solver Integration Path

### Phase 1

Keep the current lightweight solver and improve the sketch model/UI contract.

### Phase 2

If solver stability or constraint breadth becomes a limitation, adopt **PlaneGCS via WASM**.

### Phase 3

Only consider a backend FreeCAD solving path if the product moves toward server-mediated sketch solving or if export pipelines already require FreeCAD residency.

### Not Recommended for Default Flow

- backend-first solving
- raw JSON-driven sketching
- switching to a full external sketcher app

## Risks

- **License risk:** JSketcher, SolveSpace, and CAD Sketcher are not clean code-reuse targets for FRIDAY.
- **Numerical risk:** a lightweight solver may struggle with more advanced sketch edits.
- **Data model risk:** if rectangle remains a macro instead of a primitive, the UX will slide back toward line-drawing behavior.
- **Product risk:** hiding debug details is necessary; surfacing them by default will recreate the command-composer problem.
- **Integration risk:** PlaneGCS via WASM is attractive but adds build/package complexity.

## Next Implementation Sheet

This is the smallest useful next pass:

1. Make rectangle a first-class sketch primitive.
2. Commit inferred rectangle constraints automatically.
3. Keep dimensions and constraints visible in the normal workbench.
4. Keep raw JSON and command ids behind Advanced/Debug.
5. Gate Convert to CAD on a valid closed profile.
6. Add Playwright coverage for the rectangle workflow.

That gets FRIDAY from “drawing surface” to “parametric sketcher” without jumping straight into a full CAD platform rewrite.

## Source References

- JSketcher repository: https://github.com/xibyte/jsketcher
- JSketcher wiki: https://github.com/xibyte/jsketcher/wiki
- SolveSpace repository: https://github.com/solvespace/solvespace
- SolveSpace docs: https://solvespace.com/
- FreeCAD repository: https://github.com/FreeCAD/FreeCAD
- FreeCAD Sketcher docs: https://wiki.freecad.org/Sketcher_Workbench
- PlaneGCS wrapper: https://github.com/Salusoft89/planegcs
- Assemble2D repository: https://github.com/tab58/assemble2d
- CAD Sketcher repository: https://github.com/hlorus/CAD_Sketcher
- CAD Sketcher docs: https://hlorus.github.io/CAD_Sketcher/
