# ADR: SketchMath Headless FreeCAD Extrusion Adapter

## Problem
SketchMath has a closed 2D profile model and a typed command pipeline, but Slice 6 needs a minimal way to turn a profile into a STEP solid without turning the FRIDAY gateway into a CAD execution host.

## Options Considered
1. Keep extrusion out of FRIDAY entirely until a later slice.
2. Call FreeCAD directly from the gateway router or browser.
3. Add a narrow headless CAD adapter below SketchMath and keep the typed command boundary intact.

## Decision
Add a narrow headless FreeCAD adapter under `sketchmath/cad/` and expose it through the typed `extrude_profile` command.

## Rationale
- Keeps SketchMath as the source of truth for entities, profiles, commands, preview, commit, revert, and replay.
- Uses `freecadcmd` headlessly, so no FreeCAD GUI, 3D viewport, or browser integration is introduced.
- Preserves the no-arbitrary-Python rule because the worker script is fixed, versioned, and repo-owned.
- Allows a real STEP export validation spike without promoting the adapter into a general CAD feature tree.

## Consequences
- The command catalog now includes a narrow export path that must remain deterministic and test-visible.
- The adapter adds a repo-local artifact directory for STEP outputs and validation JSON.
- The boundary now depends on a headless FreeCAD runtime being present in the environment or explicitly configured.

## Explicit Deferrals
- No FreeCAD GUI or browser integration.
- No MCP wrapper.
- No arbitrary Python execution from user or LLM output.
- No general CAD feature tree, trimming workflow, CAM, slicer, or G-code path.
