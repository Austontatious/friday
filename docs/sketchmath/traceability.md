# SketchMath Requirement Traceability

This is the canonical requirement-to-evidence ledger for SketchMath. Update it with each coherent slice. `Implemented` means code exists; `Passed` requires current observable evidence; `Deferred` is not completion.

## Gate A Ledger

| Requirement | Current state | Implementation / source | Tests and acceptance evidence | Commit |
| --- | --- | --- | --- | --- |
| SM-GA-001 contract agreement | Passed | `sketchmath/models/`, generated `sketchmath/schemas/`, executor handler discovery, closed frontend command union | 66 focused contract/executor/API tests; schema drift check; 42 semantic evals | `878374b` |
| SM-GA-002 documentation truth | Passed | `docs/sketchmath/command_catalog.md`, `docs/sketchmath/ui_workspace.md`, translator contract prompt | Circle/topology/constraint contradiction scan; focused translation tests | `578b867` |
| SM-GA-003 feature-gate agreement | Passed | `core/config.py`, `frontend/src/services/sketchmath.ts`, `.env.example`, Dockerfile, Compose, ADR 003 | Backend unset/off tests; frontend unset/off/on tests; Compose config | `0647568` |
| SM-GA-004 clean build | Passed | Removed unused `sessionMetadata`; explicit frontend build flag | `npx tsc --noEmit`; production build compiled without SketchMath source warnings | `0647568` |
| SM-GA-005 deliberate landing | Passed | `docs/sketchmath/landing_manifest.md` and dedicated remote branch | Verified `refs/heads/sketchmath-product-gate-a` without force-push or source-branch rewrite | Code baseline `54ff17e`; first published `1a4c853` |
| SM-GA-006 regression baseline | Passed on 2026-08-08 | Deliberate landing implementation | 99 Python, 42 semantic eval, 37 focused frontend, 9 Playwright, schema check, TypeScript, build, Compose, 13 standards | `54ff17e` |

## Verified Existing Capability Ledger

| Capability | State | Evidence surface |
| --- | --- | --- |
| Point/line/rectangle/circle/hole sketching | Passed | `tests/test_sketchmath_foundations.py`, `SketchMathWorkspace.test.tsx`, `frontend/e2e/sketchmath.spec.ts` |
| Distance/angle/parallel/perpendicular/equal constraints | Passed for current closed-form subset | executor/solver tests and browser acceptance |
| Driving horizontal/vertical distance and radius/diameter | Passed for Phase 1 linear subset | v0.4 schema/API/solver/frontend/eval tests and live Playwright assertions |
| Horizontal/vertical/coincident constrained drag | Passed | foundation tests and Playwright constrained-drag workflow |
| Simple closed-loop profile detection | Passed for current deterministic simple-cycle envelope | topology foundation tests and Playwright detected-profile workflow |
| Preview/commit/revert and persistent undo/redo | Passed | API/history tests and Playwright reload/history workflow |
| Rectangle/circle/line-profile extrusion | Passed | CAD adapter/API tests and Playwright workflows |
| Holed STEP export/download | Passed | CAD tests and rectangle-to-STEP browser workflow |
| 3D preview orbit mechanics | Passed mechanically | frontend unit and browser assertions; manual CAD-feel acceptance remains open |

## Known Contradictions at Program Start

| ID | Contradiction | State | Resolution target |
| --- | --- | --- | --- |
| C-001 | Runtime supports v0.2 circle/topology/constraint commands absent from `geometry_command.schema.json`. | Resolved | SM-GA-001 |
| C-002 | `selection_context.schema.json` omits circle entities, linked line endpoint IDs, profile source metadata/holes, and horizontal/vertical/coincident constraints. | Resolved | SM-GA-001 |
| C-003 | Command catalog/UI docs say standalone circles are unsupported while runtime and acceptance tests support them. | Resolved | SM-GA-002 |
| C-004 | Frontend treats an unset SketchMath flag as enabled; backend treats unset as disabled. | Resolved | SM-GA-003 |
| C-005 | Production build reports unused `sessionMetadata`. | Resolved | SM-GA-004 |
| C-006 | Local validated history is substantially ahead of the remote branch and includes unrelated FRIDAY commits. | Resolved by dedicated branch | SM-GA-005 |
| C-007 | Automated camera movement passes, but prior manual CAD-like pan/tilt concern was never explicitly closed. | Deferred | SM-VIEW-001 |
| C-008 | Filesystem persistence plus process-local cache requires one backend worker. | Deferred | SM-DOC-002 |

## Future Gate Summary

| Requirement family | State | Next proof |
| --- | --- | --- |
| SM-SK / SM-SOL parametric sketcher | Partial | Solver architecture ADR, defensible DOF subset, arcs, Gate B browser scenario |
| SM-TOP general topology | Deferred | Adversarial planar-region fixtures and deterministic region selection |
| SM-FEAT feature history | Deferred | Canonical document/feature model plus rebuild tests |
| SM-REF reference stability | Deferred | Upstream-edit survival/repair tests |
| SM-WS / SM-VIEW CAD workspace | Partial | Model tree/property editor, multi-sketch, manual/browser camera acceptance |
| SM-DOC document architecture | Partial | Versioned schema, migration, revisions, stale/concurrent-write tests |
| SM-ART artifacts | Partial | STL, revision association, lifecycle/cleanup, golden geometric properties |
| SM-AI model-aware copilot | Early translator only | Structured model context, typed multi-step proposals, state-based semantic benchmark |
| SM-QA / SM-OPS / SM-SEC hardening | Partial | Adversarial, performance, async jobs, instrumentation, kernel isolation |

## Phase 1 Evidence Ledger

| Requirement | Current state | Evidence | Limitation |
| --- | --- | --- | --- |
| SM-ARCH-001 canonical document boundary | Design accepted | ADR 004 | Document envelope and migration are not implemented. |
| SM-ARCH-003 solver boundary | Initial implementation | ADR 005; `SolverAnalysis`; `analyze_constraints` v0.3; SciPy benchmark report/artifact | Production mutation still uses the closed-form solver; SciPy is `promising_not_ready`. |
| SM-SOL-001 state reporting | Partial | Exact linear consistency/redundancy tests and semantic eval; live Normal labels plus Advanced-only diagnostics in unit and Playwright coverage | Nonlinear redundancy and minimal conflict sets are unknown. |
| SM-SOL-002 defensible DOF | Partial | Rank-based exact DOF for point/circle linear systems; explicit partial/unknown results; UI never promotes partial coverage to fully constrained | Arc, standalone-coordinate legacy geometry, and nonlinear DOF are not exact. |
| SM-SK-003 driving dimensions | Partial | v0.4 horizontal/vertical distance and radius/diameter commands update geometry and constraints through Normal UI | Remaining tangent/concentric/collinear/midpoint/symmetric families are open. |
| SM-UNIT-001 centralized tolerances | Initial implementation | Versioned `NumericalTolerancePolicy` | Unit expansion and display formatting remain open. |
| SM-OPS-002 async boundary | Design accepted | ADR 006 | Job runtime is not implemented; current export remains synchronous. |
