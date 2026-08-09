# SketchMath Minimum Model Tree Contract

Updated: 2026-08-09

Status: passed for the default-off single-body/single-sketch feature-history envelope; multi-sketch workspace support remains partial

## Contract

The guarded workspace renders the canonical document hierarchy as user-facing body, sketch, and typed feature nodes. Supported feature labels are Extrude, Revolve, Hole, Fillet, and Chamfer. Selecting a node exposes bounded properties: body/sketch visibility state and plane, or feature operation plus type-specific parameters.

Feature rename is a canonical `replace_feature` commit. The immutable feature ID, dependencies, source references, and typed parameters are retained while the trimmed user-facing name changes. The operation participates in revision conflict handling, feature undo/redo, persistence, and downstream rebuild.

Raw body, sketch, feature, profile, and revolve-axis IDs are not rendered as Normal-mode labels. IDs remain transport identity and may appear in Advanced/Debug data and automation attributes.

When canonical design parameters exist, the same panel renders their user-facing names, bounded numeric values, and units above the tree. Applying a value uses the version-1.1 feature-operation boundary, so parameter changes share revision checks, rebuild, history, persistence, and error behavior with feature edits; raw binding targets stay hidden.

## Current Boundary

- Existing body and sketch visibility values are displayed but not mutated. A control is intentionally absent until the renderer honors persisted visibility end to end.
- The hierarchy follows the current canonical single-body/single-sketch document. Multi-body, multi-sketch attachments, reordering, drag/drop, and body/sketch rename remain open.
- Typed feature editors remain in the feature-history rows. Cross-feature design intent uses the one canonical document parameter list rather than duplicating values in tree properties.
- Existing extrusions expose depth, one-sided/symmetric/two-sided extent, conditional second depth, and direction. Replacement preserves the feature's operation/dependency/reference intent.
- Existing holes expose simple/counterbore/countersink style, diameter, through/blind/depth, and style-specific diameter/depth/angle editing in their history row. Parameter-bound holes show the design-parameter owner state and disable direct property mutation.
- Existing full revolves expose their user-facing construction-axis choice and the supported 360-degree sweep in the history row. Applying a different axis preserves the immutable feature ID and participates in canonical rebuild, undo/redo, and persistence.

## Evidence

- Frontend unit coverage renders body/sketch plus every supported feature type, switches selection, exposes type-specific properties, trims a rename, and verifies a raw revolve-axis ID is absent from visible text.
- The 44 focused workspace tests and TypeScript pass for the current slice.
- Targeted Playwright proves rectangle → extrusion → model-tree selection → rename → immutable ID/parameter check → reload in 5.4 seconds.
- Golden Playwright proves two named design-parameter edits, undo/redo/reload, rebuilt tree state, and revision-bound STEP download without exposing raw model IDs or emitting browser errors.
- Full-revolve Playwright proves two construction axes, stable-ID axis replacement, changed rebuild signature, undo/redo, and reload without exposing the axis IDs as Normal-mode labels or emitting browser errors.
- Advanced-hole Playwright proves counterbore and countersink conditional properties, stable-ID replacement, undo/redo, and reload without emitting browser errors.
- Extrusion Playwright proves symmetric and two-sided bounds, direction/second-depth properties, stable identity/signature history, undo/redo, and reload.

Checkpoints: `bc650ca`, `1e8db05`, `7976010`, `9f0621c`, `54bce47`.
