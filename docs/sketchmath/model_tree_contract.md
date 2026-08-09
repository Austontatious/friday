# SketchMath Minimum Model Tree Contract

Updated: 2026-08-09

Status: passed for the default-off single-body/single-sketch feature-history envelope; multi-sketch workspace support remains partial

## Contract

The guarded workspace renders the canonical document hierarchy as user-facing body, sketch, and typed feature nodes. Supported feature labels are Extrude, Revolve, Hole, Fillet, and Chamfer. Selecting a node exposes bounded properties: body/sketch visibility state and plane, or feature operation plus type-specific parameters.

Feature rename is a canonical `replace_feature` commit. The immutable feature ID, dependencies, source references, and typed parameters are retained while the trimmed user-facing name changes. The operation participates in revision conflict handling, feature undo/redo, persistence, and downstream rebuild.

Raw body, sketch, feature, profile, and revolve-axis IDs are not rendered as Normal-mode labels. IDs remain transport identity and may appear in Advanced/Debug data and automation attributes.

## Current Boundary

- Existing body and sketch visibility values are displayed but not mutated. A control is intentionally absent until the renderer honors persisted visibility end to end.
- The hierarchy follows the current canonical single-body/single-sketch document. Multi-body, multi-sketch attachments, reordering, drag/drop, and body/sketch rename remain open.
- Typed numeric feature editors remain in the feature-history rows and are reachable alongside tree selection; this slice does not duplicate them into a second parameter system.

## Evidence

- Frontend unit coverage renders body/sketch plus every supported feature type, switches selection, exposes type-specific properties, trims a rename, and verifies a raw revolve-axis ID is absent from visible text.
- All 69 frontend tests and TypeScript pass.
- Targeted Playwright proves rectangle → extrusion → model-tree selection → rename → immutable ID/parameter check → reload in 5.4 seconds.

Checkpoint: `bc650ca`.
