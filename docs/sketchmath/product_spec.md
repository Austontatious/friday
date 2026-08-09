# SketchMath Product Specification

Status: canonical development specification

Spec version: `0.1`

Baseline audited commit: `21b8153`
Last validated SketchMath code milestone: `4002b67` (golden parameter edit, semantic-hole properties, full-revolve axis properties, and complete resumed regression evidence in `golden_mounting_plate_v1.md` and `status.md`)

## Mission

SketchMath is a browser-based, AI-assisted parametric design tool for useful mechanical parts. It evolves the existing MVP incrementally; it is not a rewrite.

The canonical architecture is:

`React workspace -> typed API -> persistent SketchMath model/session layer -> deterministic geometry/constraint engine -> narrow CAD kernel adapter`

Manual and AI actions must operate on the same canonical SketchMath model through the same typed, previewable, undoable operations. FreeCAD is an execution and export kernel, not the source of truth.

## Product Boundary

The full-product milestone supports realistic design of a bounded class of mechanical parts through parametric sketches, multiple sketches, common solid features, editable history, model-aware AI assistance, reliable save/load, and STEP/STL export.

Explicit non-goals for this development line are assemblies, FEA/CFD, CAM, PCB/BIM, photoreal rendering, advanced surface modeling, specialist sheet metal, enterprise PLM, and mobile-first CAD.

## Non-Negotiable Invariants

1. SketchMath owns the canonical parametric model and stable identifiers.
2. All geometry/model mutations use versioned typed operations.
3. Preview and commit remain distinct for risky, destructive, or ambiguous changes.
4. The backend is authoritative for committed state, revisions, and undo/redo.
5. The language model proposes operations; deterministic systems validate and execute them.
6. FreeCAD internals and fragile kernel indices must not leak into public model contracts.
7. Invalid states and dependency failures are structured, visible, and recoverable where possible.
8. Normal mode uses product language; raw IDs and internals remain Advanced/debug concerns.
9. Long-running solve, rebuild, kernel, AI, and export work must not block request handlers.
10. Every accepted slice has traceable requirements, tests/evals, evidence, and a commit.

## Canonical Layers

### SM-ARCH-001 — Parametric document model

The SketchMath document model will own documents, bodies, sketches, entities, constraints, dimensions, profiles, reference geometry, features, dependencies, units, provenance, revisions, and user-facing names separate from immutable IDs.

### SM-ARCH-002 — Deterministic operation engine

Toolbar, pointer, keyboard, property editor, and AI actions resolve to the same validated operation semantics.

### SM-ARCH-003 — Constraint and geometry solver

The solver will progress from the current closed-form subset to mathematically defensible DOF reporting and expandable nonlinear constraints. Unknown or partial DOF must be explicit; exact values must never be fabricated.

### SM-ARCH-004 — CAD kernel boundary

FreeCAD performs controlled kernel operations behind timeouts, path validation, numeric limits, structured failures, and reproducible artifact validation.

### SM-ARCH-005 — Model-aware AI assistant

AI receives compact structured model context and produces proposed typed operations or multi-step plans. It cannot mutate hidden model state.

## Stabilization Requirements — Gate A

| ID | Requirement | Acceptance |
| --- | --- | --- |
| SM-GA-001 | Runtime command types, versions, schemas, frontend types, docs, and eval contracts agree. | Contract tests compare declared and implemented command sets; circle/topology commands are declared. |
| SM-GA-002 | Documentation describes the implemented modeling envelope without stale unsupported-circle claims. | Documentation review and checked assertions pass. |
| SM-GA-003 | One explicit feature-gate contract controls frontend visibility and backend availability. | Unset/off/on behavior is tested on both sides. |
| SM-GA-004 | SketchMath production build has no actionable SketchMath warning. | TypeScript and production build pass without SketchMath source warnings. |
| SM-GA-005 | The validated baseline is reproducible and intentionally landed without unrelated-history contamination. | Remote commit/branch, commit set, validation evidence, and rollback are recorded. |
| SM-GA-006 | The regression baseline remains green. | Python, semantic eval, frontend unit, browser acceptance, TypeScript, build, Compose, and standards gates pass. |

Major geometry expansion is prohibited until Gate A is recorded as passed.

## Parametric Sketch Requirements — Gate B

### Geometry and editing

- `SM-SK-001`: point, construction point, line, polyline, rectangle, center rectangle, circle, center/three-point arc, slot, polygon, and reference/construction geometry.
- `SM-SK-002`: select, multiselect, box select, move/endpoint drag, trim, extend, split, delete, duplicate, offset, mirror, pattern, and construction conversion where supported safely.

### Constraints and dimensions

- `SM-SK-003`: coincident, horizontal, vertical, parallel, perpendicular, tangent, equal, concentric, collinear, midpoint, symmetric, fixed, distance, horizontal/vertical distance, angle, radius, and diameter.
- `SM-SK-004`: dimensional edits solve and update geometry rather than relabeling it.
- `SM-SOL-001`: report under-, fully-, over-, inconsistent-, and redundant-constraint states where mathematically supported.
- `SM-SOL-002`: report defensible remaining DOF with explicit partial/unknown cases.
- `SM-SOL-003`: return structured conflicts and prevent invalid commits unless a recoverable invalid state is explicitly modeled.

Gate B requires a browser sequence covering mixed geometry, constraints, dimensions, live solver state, remaining-DOF drag, full constraint, dimensional edit/re-solve, undo/redo, and identical reload recovery with no browser errors.

## Topology Requirements

- `SM-TOP-001`: deterministic planar regions for disjoint loops, nested loops, holes, islands, shared edges, branches, and intersections within the supported envelope.
- `SM-TOP-002`: stable region IDs, loop orientation, point-in-region selection, and explicit diagnostics.
- `SM-TOP-003`: adversarial coverage for touching/overlapping loops, nested circles, multiple holes, coincident edges, near vertices, self-intersections, T-junctions, and disconnected profiles.

Phase 2 status: passed for the documented v0.9 regular-line, circle, and finite-arc envelope at `b29d504`, with per-session mutation hardening at `326e813`. This does not complete feature history, downstream solid references, or the full release gate.

## Feature Modeling Requirements

- `SM-FEAT-001`: a versioned feature history with stable IDs, parameters, dependencies, editable properties, deterministic rebuild order, and structured failures.
- `SM-FEAT-002`: extrusion supports new body, add, cut, symmetric, and supported one-/two-sided modes.
- `SM-FEAT-003`: revolve supports add/cut and explicit axes.
- `SM-FEAT-004`: simple, counterbore, countersink, through, and blind hole semantics where the kernel boundary can validate them.
- `SM-FEAT-005`: fillet, chamfer, linear/circular pattern, feature mirror, and shell when stable.
- `SM-REF-001`: downstream references use semantic source/signature/recovery data rather than permanent raw kernel indices.
- `SM-REF-002`: upstream edits either preserve references correctly or fail explicitly and repairably.

Phase 3 status: `SM-FEAT-001` passes for the default-off v1 extrusion/hole/full-revolve/terminal-fillet-or-chamfer envelope. `SM-FEAT-002/003/004` remain bounded as recorded in traceability; the supported full-revolve UI now includes stable-ID construction-axis replacement with undo/redo/reload while retaining its truthful 360-degree-only limit. `SM-FEAT-005` includes kernel-backed convex outer-vertical-edge fillet and equal-distance chamfer with semantic endpoint reconciliation, editable parameters, asynchronous STEP, live browser evidence, and a terminal fillet after the golden plate's bounded additive-extrusion/simple-hole graph. Other intermediate graphs, pattern/mirror, and shell remain open. `SM-REF-001/002` pass for the documented generated-reference envelope, while arbitrary viewport picking and general kernel-topology reconciliation remain open.

## Workspace and Document Requirements

- `SM-WS-001`: multi-sketch documents support principal planes and safe planar-face attachments, visibility, reference geometry, origins, axes, and cross-feature dependencies.
- `SM-WS-002`: a model tree and property editor expose user-facing names and typed editable properties.
- `SM-VIEW-001`: CAD-like orbit, pan, zoom, fit, standard views, projection mode, hover, object/face/edge selection, highlighting, origin/grid controls, and predictable mouse behavior.
- `SM-DOC-001`: new/save/load/autosave, dirty state, deterministic versioned serialization, migrations, crash recovery, and persistent history where feasible.
- `SM-DOC-002`: revision/locking/conflict semantics prevent silent last-write-wins corruption across workers or stale clients.

## Artifact, Units, and AI Requirements

- `SM-ART-001`: STEP and STL artifacts are tied to model revision and include metadata, regeneration, safe filenames, cleanup policy, and download UX.
- `SM-UNIT-001`: centralized units and tolerances support mm, cm, m, and inch with deterministic internal representation and clean display formatting.
- `SM-AI-001`: natural language resolves model context into proposed typed operations, deterministic validation, preview, and commit.
- `SM-AI-002`: multi-step plans remain inspectable and every committed step is undoable.
- `SM-AI-003`: AI explanations use product names, distinguish deterministic findings from heuristics, and provide recovery options.
- `SM-AI-004`: semantic evaluation measures operation/target/parameter correctness, clarification rate, invalid operations, final geometry, undoability, and deterministic validation—not prose similarity alone.

## Quality, Operations, and Security

- `SM-QA-001`: every substantial capability has proportionate unit, contract, geometry, solver, topology, serialization, frontend, semantic, browser, and CAD artifact evidence.
- `SM-QA-002`: golden parts validate bounds, volume, topology/holes, and manifold/solid properties where supported.
- `SM-QA-003`: adversarial tests cover malformed commands, numeric extremes, impossible geometry, stale writes, concurrency, reference deletion, failed rebuild/export, and repeated undo/redo.
- `SM-OPS-001`: command, revision, solve, rebuild, topology, kernel, export, AI proposal, validation, duration, and error category are observable without exposing secrets.
- `SM-OPS-002`: expensive operations are asynchronous and have status/streaming, timeout, cancellation/recovery, and explicit failure.
- `SM-SEC-001`: session IDs, paths, filenames, numbers, commands, exports, and kernel execution are validated and bounded.

## Acceptance Scenarios

The normative full-product scenarios are:

1. AI-created mounting plate with four edge-offset holes, raised boss, through-hole, fillets, parametric width edit, manual hole edit, undo/redo, reload, STEP/STL export, and geometric validation.
2. Manual creation of a multi-sketch parametric part through model tree/property editing, upstream edits, save/reload, and STEP/STL export.
3. AI edits to an existing manual model that preserve parametric intent and can be undone.

Detailed scenario traceability and current evidence live in `docs/sketchmath/traceability.md`.

Acceptance scenario 1 now passes for the manual/canonical golden workflow documented by `golden_mounting_plate_v1.md`: exact eight-feature 80 × 50 geometry, edge-offset holes, analytic circular boss, cumulative through-hole, semantic fillets, browser-driven width/diameter intent edits, undo/redo/reload, and revision-bound post-edit native STEP validation. AI construction remains open, so this is not the full-product release verdict.

## Phase Gates

1. Phase 0: Gate A stable, documented, remotely reproducible baseline.
2. Phase 1: Gate B parametric sketcher.
3. Phase 2: general planar topology. Passed for the documented v0.9 envelope.
4. Phase 3: feature-based modeling.
5. Phase 4: stable topological references.
6. Phase 5: multi-sketch CAD workspace and viewport.
7. Phase 6: versioned/concurrent document architecture and artifact lifecycle.
8. Phase 7: model-aware AI copilot.
9. Phase 8: design intelligence.
10. Phase 9: adversarial, performance, UX, deployment, and recovery hardening.

The final release verdict requires all stated gates plus an independent adversarial review whose explicit goal is to disprove completion.
