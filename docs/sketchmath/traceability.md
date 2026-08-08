# SketchMath Requirement Traceability

This is the canonical requirement-to-evidence ledger for SketchMath. Update it with each coherent slice. `Implemented` means code exists; `Passed` requires current observable evidence; `Deferred` is not completion.

## Gate A Ledger

| Requirement | Current state | Implementation / source | Tests and acceptance evidence | Commit |
| --- | --- | --- | --- | --- |
| SM-GA-001 contract agreement | In progress | `sketchmath/models/`, `sketchmath/schemas/`, `sketchmath/executor/command_router.py`, `frontend/src/services/sketchmath.ts` | Contract/schema tests and semantic eval check required | TBD |
| SM-GA-002 documentation truth | In progress | `docs/sketchmath/command_catalog.md`, `docs/sketchmath/ui_workspace.md` | Documentation contradiction scan | TBD |
| SM-GA-003 feature-gate agreement | In progress | `core/config.py`, `frontend/src/services/sketchmath.ts`, deployment examples | Backend and frontend unset/off/on tests | TBD |
| SM-GA-004 clean build | In progress | `frontend/src/components/sketchmath/SketchMathWorkspace.tsx` | `npx tsc --noEmit`; `npm run build` | TBD |
| SM-GA-005 deliberate landing | Blocked pending commit-set analysis | Git history and landing record in living status | Remote ref plus reproducible validation record | TBD |
| SM-GA-006 regression baseline | Passed at audited `21b8153` on 2026-08-08 | Existing implementation | 93 Python, 39 semantic eval, 30 frontend, 9 Playwright, TypeScript, build, Compose, 13 standards | `21b8153` checkout; latest SketchMath `8236828` |

## Verified Existing Capability Ledger

| Capability | State | Evidence surface |
| --- | --- | --- |
| Point/line/rectangle/circle/hole sketching | Passed | `tests/test_sketchmath_foundations.py`, `SketchMathWorkspace.test.tsx`, `frontend/e2e/sketchmath.spec.ts` |
| Distance/angle/parallel/perpendicular/equal constraints | Passed for current closed-form subset | executor/solver tests and browser acceptance |
| Horizontal/vertical/coincident constrained drag | Passed | foundation tests and Playwright constrained-drag workflow |
| Simple closed-loop profile detection | Passed for current deterministic simple-cycle envelope | topology foundation tests and Playwright detected-profile workflow |
| Preview/commit/revert and persistent undo/redo | Passed | API/history tests and Playwright reload/history workflow |
| Rectangle/circle/line-profile extrusion | Passed | CAD adapter/API tests and Playwright workflows |
| Holed STEP export/download | Passed | CAD tests and rectangle-to-STEP browser workflow |
| 3D preview orbit mechanics | Passed mechanically | frontend unit and browser assertions; manual CAD-feel acceptance remains open |

## Known Contradictions at Program Start

| ID | Contradiction | Resolution target |
| --- | --- | --- |
| C-001 | Runtime supports v0.2 circle/topology/constraint commands absent from `geometry_command.schema.json`. | SM-GA-001 |
| C-002 | `selection_context.schema.json` omits circle entities, linked line endpoint IDs, profile source metadata/holes, and horizontal/vertical/coincident constraints. | SM-GA-001 |
| C-003 | Command catalog/UI docs say standalone circles are unsupported while runtime and acceptance tests support them. | SM-GA-002 |
| C-004 | Frontend treats an unset SketchMath flag as enabled; backend treats unset as disabled. | SM-GA-003 |
| C-005 | Production build reports unused `sessionMetadata`. | SM-GA-004 |
| C-006 | Local validated history is substantially ahead of the remote branch and includes unrelated FRIDAY commits. | SM-GA-005 |
| C-007 | Automated camera movement passes, but prior manual CAD-like pan/tilt concern was never explicitly closed. | SM-VIEW-001 |
| C-008 | Filesystem persistence plus process-local cache requires one backend worker. | SM-DOC-002 |

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
