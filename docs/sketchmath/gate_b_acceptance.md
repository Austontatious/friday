# SketchMath Gate B Acceptance

Validated implementation checkpoint: `0621e8c` (`feat(sketchmath): complete Gate B geometry editing`)

Browser synchronization checkpoint: `2a7a04c` (`test(sketchmath): stabilize polyline browser placement`)

Gate B is passed for the explicitly modeled Phase 1 sketch and safe-editing envelope. This is not a claim of general planar topology, automatic topology repair, feature history, or release readiness.

## Accepted Requirements

| Requirement | Accepted evidence |
| --- | --- |
| `SM-SK-001` geometry | Canonical points, construction points/lines, linked lines and polylines, corner/center rectangles, circles, center/three-point arcs, slots, regular polygons, and curve-backed profiles. |
| `SM-SK-002` editing | Select, multiselect, complete-containment box select, point drag, delete, construction conversion, split/trim/extend within the safe line envelope, line/circle/arc offset, linked-bundle duplicate, linear pattern, and mirror. |
| `SM-SK-003` constraints | Coincident, horizontal, vertical, parallel, perpendicular, tangent, equal length/angle, concentric, collinear, midpoint, symmetric, fixed, distance, horizontal/vertical distance, angle, radius, and diameter in the documented modeled subset. |
| `SM-SK-004` dimensional solve | Driving dimensions update canonical geometry; the browser acceptance changes circle radius/diameter and verifies the solved value through undo, redo, solve, and reload. |
| `SM-SOL-001` / `SM-SOL-002` | Residual-validated nonlinear analysis reports modeled constraint state and exact Jacobian-rank remaining DOF; unmodeled geometry remains explicit `partial`/`unknown`. |
| `SM-SOL-003` | Invalid solver and topology-sensitive edits return structured errors and do not enter history or partially mutate entity identity. |

## Commit-Bound Browser Evidence

`frontend/e2e/sketchmath.spec.ts` contains two complementary live workflows committed with the implementation:

1. `fully constrains mixed line, circle, arc, and construction geometry with conflict recovery and reload`
   - Builds line, circle, finite arc, and construction-line geometry in one session.
   - Shows remaining DOF, drags the remaining circle center, fixes all modeled points, and reaches `Fully constrained`.
   - Attempts a conflicting fixed-point drag, observes the structured `409` conflict, and proves history length is unchanged.
   - Recovers with a diameter edit, then proves solve, undo/redo, arc/construction identity, coordinates, and solver state after reload.
2. `creates mixed Gate B geometry, diagnoses an unsafe edit, recovers, and reloads durable history`
   - Creates polygon and slot bundles, including true finite slot arcs and `source_curve_ids`.
   - Attempts to split a slot profile source, observes the structured `unsafe_referenced_curve_edit` refusal, and proves history and entity IDs are unchanged.
   - Recovers with a valid standalone split and exercises circle offset, construction conversion, duplicate, pattern, mirror, box selection, undo/redo, command history, and reload identity.

Both workflows assert that the only browser console resource errors are the deliberately induced and explicitly checked `409`/`422` HTTP rejections. No unexpected console error or page error is accepted by the suite.

## Safe-Editing Boundary

- Split, trim, and extend support ordinary and construction lines. The target must not be referenced by a profile or constraint.
- Trim and extend use selection order `target, cutter`; the cutter is finite, not an infinite-line approximation.
- Offset produces independent line, circle, or arc geometry. It does not rewrite a source profile.
- Translate, rotate, and mirror expand selected linked bundles before mutation. Linear copies remap point, curve, circle, arc, and profile source IDs per instance.
- General topology repair is intentionally deferred. `unsafe_referenced_curve_edit` is a safe refusal, not a partial implementation of repair.

## Validation

- Focused Python regression: 168 passed.
- Semantic geometry/translator eval: 52 passed.
- Focused frontend regression: 64 passed.
- Live shell/product Playwright workflows: 16 passed with the expected conflict/refusal assertions and no unexpected console/page errors.
- Generated schema drift check, TypeScript compile, production frontend build, Compose validation, and repository standards checks passed.

## Rollback and Next Phase

- Code rollback: `git revert 0621e8c`.
- Gate B remains behind the existing default-off SketchMath feature gate; no new environment flag was added.
- The next implementation phase is `SM-TOP`: deterministic general planar regions and adversarial topology selection.
