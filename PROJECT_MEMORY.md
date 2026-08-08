# FRIDAY Project Memory (Codex Read/Write)

## How to use this file
- This is the canonical running memory for the repo.
- Every patch set must append a short entry under "Change Log".
- Keep it factual: what changed, where, why, how to test, and any new flags.

---

## 2026-08-08 - SketchMath Center Rectangle Tool

### What Changed
- Added a Center rectangle canvas/workflow tool with center-plus-corner click placement and center-origin drag placement; Shift-drag produces a centered square.
- Center rectangles commit through the existing typed rectangle batch and persist the same four point IDs, four linked edge IDs, constraints, and profile shape as corner rectangles.
- Added unit coverage for exact symmetric coordinates and a live browser workflow proving symmetry, CAD readiness, and identical reload recovery.
- Replaced a layout-sensitive mixed-geometry pointer assertion with deterministic SVG view-box mouse events after the full serial browser gate exposed the flake.

### Why
- Gate B calls for center rectangles, but a second rectangle entity or UI-only geometry path would split dimension, profile, history, and extrusion behavior.
- Reusing the canonical rectangle bundle makes center construction an interaction method rather than a competing data model.

### New Env Flags
- None. The tool remains behind the existing default-off SketchMath feature gate.

### How To Test
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/App.test.tsx src/components/sketchmath/SketchMathWorkspace.test.tsx src/components/sketchmath/commandBuilders.test.ts src/components/sketchmath/arcGeometry.test.ts` — 62 passed.
- `cd frontend && npx tsc --noEmit && npm run build && npx playwright test e2e/sketchmath.spec.ts` — TypeScript/build and 13 browser workflows passed.
- The unchanged backend gate remains at 145 Python tests, 50 semantic cases, generated schema/Compose checks, and 13 standards tests.

### Remaining Phase 1 Work
- Add polyline and slot/polygon primitives, then the safe trim/extend/split/offset/pattern editing envelope and broader nonlinear/arc solver equations.

---

## 2026-08-08 - SketchMath Canonical Construction Geometry

### What Changed
- Added canonical construction/reference points through a `construction` flag on stable `point_2d` entities and activated the existing `construction_line_2d` entity through typed creation and conversion.
- Added v0.7 `set_construction` to convert selected points/lines in preview or commit mode while retaining IDs, endpoint links, constraints, history, and reload persistence.
- Protected committed profile boundaries from silent invalidation by rejecting conversion of their source lines.
- Added dashed construction-line and hollow/dashed construction-point styling plus Make construction / Make regular workspace controls.

### Why
- Remaining Gate B tools need centerlines and reference geometry that constraints can address without a parallel UI-only representation.
- Stable-ID type conversion preserves the existing command/history/session architecture and keeps construction lines excluded from profile detection.

### New Env Flags
- None. Construction geometry remains behind the existing default-off SketchMath feature gate.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath*.py tests/test_frontend_nginx_config.py tests/test_runtime_dependencies.py` — 145 passed.
- `PYTHONPATH=. python3 -m sketchmath.evals.run_sketchmath_evals` — 50 passed.
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/App.test.tsx src/components/sketchmath/SketchMathWorkspace.test.tsx src/components/sketchmath/commandBuilders.test.ts src/components/sketchmath/arcGeometry.test.ts` — 61 passed.
- `cd frontend && npx tsc --noEmit && npm run build && npx playwright test e2e/sketchmath.spec.ts` — TypeScript/build and 12 browser workflows passed.
- Generated schemas, Compose config, and 13 repository standards tests passed.

### Remaining Phase 1 Work
- Add polyline/center rectangle and slot/polygon primitives, then the safe trim/extend/split/offset/pattern editing envelope and broader nonlinear/arc solver equations.

---

## 2026-08-08 - SketchMath Gate B Constraint Families and Mixed-Geometry Acceptance

### What Changed
- Added typed v0.6 fixed, midpoint, collinear, symmetric, concentric, and tangent constraints across canonical models, generated schemas, executor persistence/dependencies, API, semantic evals, and the workspace.
- Added deterministic closed-form application and constrained-drag preservation for linked point/line/circle geometry. Repeated-identity selections and degenerate references fail structurally without partial commits.
- Extended exact linear solver analysis for fixed points, midpoint equations, and circle-to-circle concentricity. Collinear, symmetric, tangent, arc-concentric, and all arc geometry remain explicitly partial.
- Added a live mixed line/circle browser scenario covering observable remaining DOF, drag, full constraint, radius/diameter edit, unified solve, undo/redo, reload identity, and browser error capture.

### Why
- Gate B requires the standard sketch constraint vocabulary and one product-level lifecycle proving that dimensions, constraints, solver status, history, and persistence agree.
- Finite-arc tangency is rejected with `unsupported_arc_tangency` instead of silently applying infinite/full-circle semantics.

### New Env Flags
- None. The slice remains behind the existing default-off SketchMath feature gate.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath*.py tests/test_frontend_nginx_config.py tests/test_runtime_dependencies.py` — 140 passed.
- `PYTHONPATH=. python3 -m sketchmath.evals.run_sketchmath_evals` — 49 passed.
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/App.test.tsx src/components/sketchmath/SketchMathWorkspace.test.tsx src/components/sketchmath/commandBuilders.test.ts src/components/sketchmath/arcGeometry.test.ts` — 59 passed.
- `cd frontend && npx tsc --noEmit && npm run build && npx playwright test e2e/sketchmath.spec.ts` — TypeScript/build and 11 browser workflows passed.
- `PYTHONPATH=. python3 -m sketchmath.schemas.generate --check`, `docker compose config -q`, and `python3 -m pytest -q tests/test_codex_standards.py` passed.

### Remaining Phase 1 Work
- Complete the remaining Gate B geometry/editing envelope and expand exact nonlinear/arc solver coverage. This slice does not make the full Gate B or product release-ready.

---

## 2026-08-08 - SketchMath Canonical Arc Geometry

### What Changed
- Added one canonical `arc_2d` entity with center/radius/start-angle/signed-sweep geometry, construction provenance, and optional stable source point IDs.
- Added v0.5 `define_arc` and `update_arc` commands for center and three-point construction, including structured rejection of degenerate input.
- Added center and 3-point arc tools, canonical SVG rendering, selection summaries, preview/commit/history persistence, entity upsert, and reload recovery.
- Kept solver truth honest: arcs are explicitly unmodeled and make live coverage `partial` until arc equations exist.

### Why
- Gate B requires center and three-point arcs, but adding them before a canonical representation and unified solver result would have created a parallel UI-only geometry path.
- Signed sweep plus derived endpoints prevents redundant-coordinate drift and preserves major/minor direction deterministically.

### New Env Flags
- None. Arc geometry is part of the existing default-off SketchMath product gate.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath*.py tests/test_frontend_nginx_config.py tests/test_runtime_dependencies.py` — 127 passed.
- `PYTHONPATH=. python3 -m sketchmath.evals.run_sketchmath_evals` — 47 passed.
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand --runTestsByPath src/App.test.tsx src/components/sketchmath/SketchMathWorkspace.test.tsx src/components/sketchmath/commandBuilders.test.ts src/components/sketchmath/arcGeometry.test.ts` — 57 passed.
- `cd frontend && npx tsc --noEmit && npm run build && npm run test:e2e -- sketchmath.spec.ts` — TypeScript/build and 10 browser workflows passed.

### Remaining Phase 1 Work
- Add the remaining Gate B constraint families and complete the mixed-geometry fully constrained acceptance sequence.

---

## 2026-08-08 - SketchMath Unified Solver Run Path

### What Changed
- Added the typed `SolverRunResult` and deterministic `SolverCoordinatePatch` contract plus a generated JSON schema.
- Routed both `analyze_constraints` and `solve_constraints` through one closed-form evaluation path.
- Solve now evaluates against a deep copy and applies only an accepted solved patch; under-constrained, inconsistent, redundant, and failed outcomes include the full run result in structured errors without committing partial geometry.
- Exposed backend, outcome, termination, feasibility, and residual availability under Advanced / Debug.

### Why
- A future nonlinear backend needs one safe proposal/result seam shared with live analysis.
- The SciPy benchmark proved that optimizer termination alone is insufficient; feasibility and residuals must be explicit and independent.

### New Env Flags
- None. The production backend remains `closed_form_v1`; SciPy remains benchmark-only.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath*.py tests/test_frontend_nginx_config.py tests/test_runtime_dependencies.py` — 118 passed with SciPy installed.
- `PYTHONPATH=. python3 -m sketchmath.schemas.generate --check`.
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand App.test.tsx SketchMathWorkspace.test.tsx commandBuilders.test.ts` — 53 passed.
- `cd frontend && npx tsc --noEmit && npm run build && npm run test:e2e -- sketchmath.spec.ts` — TypeScript/build and 9 browser workflows passed.

### Remaining Phase 1 Work
- Add canonical arcs using the unified solver contract, then implement the remaining Gate B constraints and mixed-geometry acceptance sequence.

---

## 2026-08-08 - SketchMath SciPy Nonlinear Solver Benchmark

### What Changed
- Added an optional, production-isolated benchmark for `scipy.optimize.least_squares` with analytic and finite-difference Jacobian paths.
- Covered triangle distances, parallel-plus-length, near-tangent circles, inconsistent distances, and a zero-length analytic seed.
- Recorded residuals, termination details, evaluations, timings, environment, installed-license metadata hash, and the adoption decision in a tracked JSON artifact and report.

### Why
- Phase 1 requires evidence before selecting a nonlinear backend.
- The benchmark proves that optimizer termination cannot be used as constraint success and exposes a concrete analytic-Jacobian degeneracy that the adapter must handle.

### Decision
- SciPy is `promising_not_ready` and remains outside production requirements and execution.
- Nondegenerate cases classified correctly; analytic Jacobians matched numerical probes; the inconsistent case returned optimizer success with a large residual; the analytic zero-length seed also returned success while infeasible.

### New Env Flags
- None.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath_nonlinear_benchmark.py` — 3 passed with SciPy 1.15.3 installed.
- `PYTHONPATH=. python3 -m sketchmath.solver.nonlinear_benchmark --repetitions 25 --output evals/sketchmath_nonlinear_solver_benchmark.json`.

### Remaining Phase 1 Work
- Define one solver proposal/result interface with residual-based feasibility, seed/degeneracy policy, stable variables, timeouts, and rollback-safe canonical patches before integrating any generalized backend.

---

## 2026-08-08 - SketchMath Driving Axis and Circle Dimensions

### What Changed
- Added command contract version `0.4` operations for horizontal distance, vertical distance, radius, and diameter.
- Added typed constraint primitives, deterministic mutation/solve handling, unit normalization, deletion dependencies, history replay, API coverage, generated schemas, and semantic evals.
- Extended exact rank analysis from point-only geometry to circle center/radius variables and all four new linear dimension families.
- Added Normal-mode axis-distance buttons and driving radius/diameter editors. Reapplying an axis dimension or switching a circle between radius and diameter replaces the same-semantic constraint instead of stacking duplicates.

### Why
- Phase 1 requires dimensions to drive geometry and solver state, not act as display-only labels.
- These equation families are linear, so they can expand exact DOF reporting before adopting a nonlinear backend.

### New Env Flags
- None. The operations remain behind the existing default-off SketchMath product gate.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath*.py tests/test_frontend_nginx_config.py tests/test_runtime_dependencies.py` — 112 passed.
- `PYTHONPATH=. python3 sketchmath/evals/run_sketchmath_evals.py --check` — 45 passed.
- `PYTHONPATH=. python3 -m sketchmath.schemas.generate --check`.
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand App.test.tsx SketchMathWorkspace.test.tsx commandBuilders.test.ts` — 53 passed.
- `cd frontend && npx tsc --noEmit && npm run build && npm run test:e2e -- sketchmath.spec.ts` — TypeScript/build and 9 browser workflows passed.
- `docker compose config -q` and `python3 -m pytest -q tests/test_codex_standards.py --noconftest` — passed.

### Remaining Phase 1 Work
- Benchmark the permissive nonlinear solver candidate, unify solve/analysis, add canonical arcs, then implement the remaining Gate B constraints and acceptance scenario.

---

## 2026-08-08 - SketchMath Live Solver State

### What Changed
- Wired the preview-only `analyze_constraints` result into the actual SketchMath workspace after committed session changes.
- Replaced the generic constraint badge with honest Normal-mode states: Under-constrained, Fully constrained, Over-constrained, Conflicting, and Partially analyzed.
- Kept equation counts, remaining DOF, raw IDs, and diagnostics under Advanced / Debug.
- Removed the misleading generic `Solved` outcome; the analysis response is authoritative after solve commands.
- Added frontend fixtures for exact, redundant, inconsistent, and partial states plus a live backend/browser assertion for under-constrained and partial systems.

### Why
- A successful geometry mutation is not proof that a sketch is fully constrained.
- Gate B requires solver state to be visible in the real product while unsupported nonlinear systems remain explicitly partial.

### New Env Flags
- None. Live analysis remains behind the existing default-off SketchMath product gate.

### How To Test
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand SketchMathWorkspace.test.tsx` — 34 passed.
- `cd frontend && npx tsc --noEmit`.
- `cd frontend && npx playwright test e2e/sketchmath.spec.ts --grep "draws geometry"` — 1 passed against the live backend.
- Full regression commands and counts are recorded in `docs/sketchmath/status.md` after validation.

### Remaining Phase 1 Work
- Add driving horizontal/vertical distance and radius/diameter constraints, benchmark the nonlinear backend, unify solve paths, then add canonical arcs and the remaining Gate B constraints.

---

## 2026-08-08 - SketchMath Phase 1 Solver Analysis Foundation

### What Changed
- Added a centralized, versioned numerical tolerance policy.
- Added typed `SolverAnalysis` results and preview-only command version `0.3` `analyze_constraints`.
- Implemented rank-based exact DOF, consistency, and redundancy analysis for point-backed fixed/horizontal/vertical/coincident linear systems.
- Explicitly reports partial/unknown coverage for nonlinear constraints and unmodeled geometry instead of fabricating exact DOF.
- Recorded canonical document, solver/licensing, and async solve/rebuild boundaries in ADRs 004-006.

### Why
- Gate B needs mathematically defensible solver state before adding arcs or a generalized nonlinear backend.
- A solver-neutral contract prevents canonical model ownership from leaking into one library and makes licensing/rollback explicit.

### New Env Flags
- None. The analysis command is non-mutating and remains covered by the existing default-off SketchMath product gate.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath*.py tests/test_frontend_nginx_config.py tests/test_runtime_dependencies.py` — 106 passed.
- `PYTHONPATH=. python3 sketchmath/evals/run_sketchmath_evals.py --check` — 43 passed.
- `PYTHONPATH=. python3 -m sketchmath.schemas.generate --check`.
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand App.test.tsx SketchMathWorkspace.test.tsx commandBuilders.test.ts` — 46 passed.
- `cd frontend && npx tsc --noEmit && npm run build`.
- `cd frontend && npm run test:e2e -- sketchmath.spec.ts` — 9 passed.
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest` — 13 passed.
- `docker compose config -q`.

### Remaining Phase 1 Work
- Expose analysis in the workspace, expand exact coverage through validated nonlinear/Jacobian work, then add missing constraints and arcs in dependency order.

---

## 2026-08-08 - SketchMath Gate A Local Stabilization Candidate

### What Changed
- Established canonical full-product specification, traceability, living status, and phased execution-plan artifacts under `docs/sketchmath/` and `docs/tasks/`.
- Closed the runtime command contract over versions `0.1` and `0.2`, added a matching TypeScript command union, generated the three checked-in JSON schemas from Pydantic models, and return structured `invalid_command` errors for undeclared versions/types.
- Added semantic eval coverage for first-class circles, deterministic profile detection, and horizontal constraints; the suite now has 42 cases.
- Reconciled command/UI documentation with implemented circle, topology, endpoint, and constraint behavior.
- Aligned frontend and backend SketchMath feature gates to explicit default-off behavior and declared the build/runtime values in `.env.example`, Compose, and the frontend Dockerfile.
- Removed unused `sessionMetadata` state so the SketchMath production build has no source warning.

### Why
- Gate A requires one reproducible, documented contract before solver/topology/feature expansion.
- The prior frontend implicit-on/backend implicit-off behavior could advertise a workspace whose API was unavailable.
- Generated schemas and closed command unions prevent runtime behavior from drifting ahead of public contracts again.

### New Env Flags
- No new flag names.
- Canonical enablement now requires both `FRIDAY_SKETCHMATH_ENABLED=1` and `REACT_APP_SKETCHMATH_ENABLED=1`; both default to `0`.

### How To Test
- `python3 -m pytest -q tests/test_sketchmath*.py tests/test_frontend_nginx_config.py tests/test_runtime_dependencies.py` — 99 passed.
- `PYTHONPATH=. python3 sketchmath/evals/run_sketchmath_evals.py --check` — 42 passed.
- `PYTHONPATH=. python3 -m sketchmath.schemas.generate --check`.
- `cd frontend && CI=true npm test -- --watchAll=false --runInBand App.test.tsx SketchMathWorkspace.test.tsx` — 42 passed.
- `cd frontend && npx tsc --noEmit && npm run build && npm run test:e2e -- sketchmath.spec.ts` — TypeScript/build passed; 9 browser workflows passed.
- `docker compose config -q`.
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest` — 13 passed.

### Gate A Landing
- Reconstructed the product from `origin/phase0-stabilize` at `4ed99b3` onto dedicated branch `sketchmath-product-gate-a`, excluding unrelated local history.
- Revalidated the reconstructed code at `54ff17e` and published the branch at `1a4c853` without rewriting the source remote branch.
- Full provenance and conflict decisions are recorded in `docs/sketchmath/landing_manifest.md`.

---

## Current Target
Upgrade FRIDAY to Lexi-grade architecture patterns + modern multimodal capabilities:
- tiered memory
- identity binding
- async jobs
- capability flags
- multi-container services
- holographic monochrome avatar render (no background)

## Non-negotiables
- Text-only mode must always run.
- Everything else is optional and feature-flagged.
- No hardcoded paths. No duplicate trees.
- All long-running tasks async/streamed.

## Open Decisions
- Queue choice: Redis/RQ vs Celery vs lightweight in-proc (dev)
- TTS choice: XTTS vs Piper vs OpenVoice
- Vision choice: Qwen2-VL vs Florence vs other
- Gesture: MediaPipe (CPU) vs GPU model

## Capability Flags (planned)
- FRIDAY_LLM_ENABLED
- FRIDAY_STT_ENABLED
- FRIDAY_TTS_ENABLED
- FRIDAY_VISION_ENABLED
- FRIDAY_GESTURE_ENABLED
- FRIDAY_AVATAR_ENABLED
- FRIDAY_MEMORY_PERSIST_ENABLED
- FRIDAY_MEMORY_VECTOR_ENABLED
- FRIDAY_EMOTION_LITE_ENABLED
- FRIDAY_JOBS_ENABLED

## Change Log
### 2026-06-11 (Candidate B local gateway startup and alias cutover)
- What changed:
  - Updated `local_llm_gateway/config/models.yaml` so `friday-heavy-lite` points at the Candidate B q4 llama-server backend on `8174`, `friday-coder` points at the Candidate B q36 llama-server backend on `8176`, and `friday-heavy` remains the quality-mode q6 alias.
  - Added llama.cpp streaming support in `local_llm_gateway/gateway/adapters/llama_cpp.py` so gateway streaming works for the Candidate B llama-server aliases.
  - Moved `comfy-sd` in `Lex/docker-compose.yml` from GPU 0 to GPU 6 and restarted it healthy.
  - Added Candidate B orchestration and smoke helpers under `scripts/gateway/` plus runtime reports under `docs/gateway/runtime/`.
- Why:
  - Bring up the reserve-friendly Candidate B gateway stack, preserve GPU 7 as reserve, and validate the public gateway alias contract without wiring app clients yet.
- New env flags:
  - None.
- How to test:
  - `bash /mnt/data/models/scripts/gateway/start_local_gateway_candidate_b.sh`
  - `python3 /mnt/data/models/scripts/gateway/healthcheck_candidate_b.py`
  - `python3 /mnt/data/models/scripts/gateway/smoke_candidate_b_gateway.py`
  - `curl -sf http://127.0.0.1:8188/system_stats`

### 2026-06-11 (Local-first harness session contract)
- What changed:
  - Added `docs/local_first_harness_contract.md` to define the app-to-gateway session payload contract, supported mode values, and the thin adapter boundary.
  - Extended `local_llm_gateway/gateway/schemas.py` and `local_llm_gateway/gateway/router.py` so gateway responses echo bounded `app_session` metadata when callers provide it.
  - Added `tests/test_local_first_harness_contract.py` to verify alias identity and mode layering remain composable while app session metadata is preserved.
  - Added `docs/decisions/2026-06-11_local_first_harness_session_contract_adr.md` to record the contract decision.
- Why:
  - Make the local-first harness explicit for app callers without duplicating persona or backend-specific logic in each app.
- New env flags:
  - None.
- How to test:
  - `python3 -m pytest -q tests/test_local_first_harness_contract.py tests/test_alias_routing.py tests/test_json_mode.py`

### 2026-06-10 (Local LLM gateway for alias-to-backend contract routing)
- What changed:
  - Added a standalone `local_llm_gateway/` FastAPI service that exposes `/health`, `/profiles`, `/v1/models`, `/v1/chat/completions`, and `/admin/reload`.
  - Added YAML-driven backend/alias profiles under `local_llm_gateway/config/models.yaml` with shared-backend aliasing for `lexi`, `friday`, `chef`, `friday-coder`, and `friday-fast`.
  - Implemented alias-specific input policies, output cleanup, approximate context budgeting, strict-JSON repair, and stream normalization.
  - Added smoke tooling (`scripts/run_gateway.sh`, `scripts/smoke_gateway.py`) plus focused tests for routing, prompt shaping, streaming whitespace, JSON repair, and budget overflow.
  - Documented the boundary in `docs/decisions/2026-06-10_local_llm_gateway_adr.md`, plus implementation plan, migration notes, and a final report under `docs/`.
- Why:
  - Provide one stable local endpoint that can serve multiple public persona/application aliases without baking backend-specific prompts or transport quirks into the caller apps.
- New env flags:
  - None for the gateway core. The smoke script accepts `GATEWAY_URL` for convenience.
- How to test:
  - `python3 -m pytest -q tests/test_alias_routing.py tests/test_lexi_scaffold_filter.py tests/test_friday_structured_context.py tests/test_stream_normalization.py tests/test_json_mode.py tests/test_context_budget.py tests/test_template_rendering.py`
  - `python3 -m pytest -q tests/test_codex_standards.py --noconftest`
  - `python3 evals/runner.py --check`
  - `python3 scripts/smoke_gateway.py --gateway-url http://127.0.0.1:8130/v1`

### 2026-06-08 (Friday model modernization to Llama 3.3 Abliterated 70B)
- What changed:
  - Set Friday model defaults to the new primary path: `FRIDAY_MODEL_NAME=friday`.
  - `docker-compose.models.yml` primary `llm` service now serves `FRIDAY_MODEL_NAME` from `/mnt/data/models/llama-3.3-70b-abliterated-gptq-int8` with `--tensor-parallel-size 4` and `--max-model-len 32768`.
  - Turned default coder auto-routing off (`FRIDAY_CODER_ENABLED=0`, `FRIDAY_CODER_AUTO_ROUTE=0`), while preserving explicit coder route behavior for coding profiles/flags.
  - Increased default context target to 32k across `backend/core/llm.py` and model startup docs/scripts.
  - Updated compose/runtime scripts to skip coder discovery unless `FRIDAY_CODER_ENABLED=1`:
    - `scripts/friday_up.sh`
    - `scripts/check_friday_stack.sh`
  - Updated defaults in `.env.example` / `.env.models.example`, smoke script, and capability test expectations.
- Why:
  - Route all Friday traffic through the new local primary model by default while keeping the dedicated coding specialist as an explicit/fallback mode.
- New env flags:
  - `FRIDAY_CODER_ENABLED` (default `0`)
  - `FRIDAY_CODER_AUTO_ROUTE` (default `0`)
  - `FRIDAY_LLM_CONTEXT_WINDOW` (default `32768`)
  - `FRIDAY_MODEL_NAME` (default `friday`)
- How to test:
  - `python3 -m pytest -q tests/test_operational_hardening.py tests/test_chat_repo_context.py`
  - `LLM_BASE_URL=http://127.0.0.1:8008 FRIDAY_MODEL_NAME=friday bash scripts/smoke_llm.sh`
  - `bash scripts/check_friday_stack.sh`

### 2026-06-08 (Friday modernization routing cleanup)
- What changed:
  - Finished cleanup of routing/tests so `agent_profile: "coding"` is no longer treated as an implicit coder trigger.
  - `chat_engine` now emits a dedicated `selected_model` in `/api/chat` metadata and preserves explicit `use_coder_model: true` as the only request-level coder activation signal.
  - Prompt-builder context accounting now exposes route/lane/task metadata through `build_messages_with_accounting`.
  - Auto file search path from retrieval prompts now records an explicit `auto_file_search` runtime event.
  - `build_althing_bridge_system_prompt` now matches updated layered prompt-return signature.
- Why:
  - Keep Friday traffic on the primary local 70B model by default and make specialist routing explicit and auditable.
- New env flags:
  - No new flags introduced in this cleanup pass.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_prompt_builder.py tests/test_coder_fallback.py tests/test_chat_budgeting.py tests/test_chat_repo_context.py`

### 2026-04-19 (Read-only whole-workspace access for Friday/Althing path prompts)
- What changed:
  - `backend/tools/builtins.py`: expanded read-only path resolution to support configured extra roots, case-insensitive absolute path resolution under those roots, directory inspection via new `inspect_repo_path`, and directory-aware `file_search`.
  - `backend/core/chat_engine.py`: absolute path hints now trigger deterministic repo/workspace context injection, and auto repo context uses `inspect_repo_path` so directory prompts can succeed without write access.
  - `backend/api/althing_chat.py`: Althing-mode UI requests that reference local paths or repo files now fall back to direct Friday read-only inspection instead of proxying unchanged into Althing lanes that lack file tools.
  - Runtime mounts: `docker-compose.app.yml`, `docker-compose.dev.yml`, and `/mnt/data/althing/docker-compose.yml` now mount `/mnt/data` read-only into the relevant backend/router containers.
  - Tests: expanded `tests/test_tool_engine_file_search.py`, `tests/test_chat_repo_context.py`, and `tests/test_althing_bridge_api.py`.
- Why:
  - The remaining live failure was not just routing. Friday backend had no host workspace mount, so prompts like `/mnt/data/Friday` or `/mnt/data/Althing` were invisible at runtime even after direct Friday repo-file fixes. This patch makes the routed system read-only over the wider workspace while keeping writes disabled.
- New env flags:
  - `FRIDAY_FILE_SEARCH_EXTRA_ROOTS`
- How to test:
  - `python3 -m pytest -q tests/test_tool_engine_file_search.py tests/test_chat_repo_context.py tests/test_althing_bridge_api.py`
  - Rebuild/restart:
    - `docker compose up -d --build friday-backend`
    - `docker compose -f /mnt/data/althing/docker-compose.yml up -d router`
  - Live smoke:
    - `curl -sS -X POST http://127.0.0.1:9001/api/althing/chat -H 'Content-Type: application/json' -H 'X-Friday-Device: smoke-bridge-path' --data '{\"prompt\":\"see if you can access /mnt/data/Friday and /mnt/data/Althing\"}'`

### 2026-04-19 (Coder auto-route + repo file context for direct Friday)
- What changed:
  - `backend/core/chat_engine.py`: direct Friday now auto-routes `code_execution` prompts to the coder transport when `FRIDAY_CODER_AUTO_ROUTE=1`, extracts explicit repo-path hints from prompts, and injects deterministic repo context via `read_repo_file`/`file_search` when file-dependent prompts would otherwise fail without local access.
  - `backend/tools/builtins.py`: added read-only `read_repo_file` for bounded repo-local file reads.
  - `backend/tools/engine.py`: treats `read_repo_file` as a read-only file tool allowed under the existing `FRIDAY_FILE_SEARCH_ALLOW_WHEN_TOOLS_DISABLED` gate.
  - `Dockerfile`: backend image now copies the repo working tree into `/app` so live repo-local file reads see the actual Friday tree instead of a Python-only subset.
  - Tests: added `tests/test_chat_repo_context.py` and expanded `tests/test_tool_engine_file_search.py`.
- Why:
  - Friday’s coder transport was healthy, but direct Friday still depended on explicit request flags for coder routing and had no reliable repo-local file access path for coding prompts. This patch makes code prompts reach the coder automatically and gives explicit file-path prompts a deterministic repo context path.
- New env flags:
  - `FRIDAY_CODER_AUTO_ROUTE`
  - `FRIDAY_AUTO_REPO_FILE_LIMIT`
  - `FRIDAY_AUTO_REPO_FILE_MAX_LINES`
  - `FRIDAY_READ_REPO_FILE_MAX_LINES`
- How to test:
  - `python3 -m pytest -q tests/test_chat_repo_context.py tests/test_tool_engine_file_search.py`
  - Live smoke:
    - `curl -sS -X POST http://127.0.0.1:9001/api/chat -H 'Content-Type: application/json' -H 'X-Friday-Device: smoke-coder' --data '{\"prompt\":\"Implement a Python helper that validates a config dict.\",\"user_id\":\"smoke\",\"workspace_id\":\"default\"}'`
    - `curl -sS -X POST http://127.0.0.1:9001/api/chat -H 'Content-Type: application/json' -H 'X-Friday-Device: smoke-repo-file' --data '{\"prompt\":\"Inspect README.md and tell me the first section title.\",\"user_id\":\"smoke\",\"workspace_id\":\"default\"}'`

### 2026-04-14 (Remediation pass v1: runtime, routing, file/tool, prompt contract)
- Runtime/token budgeting hardening:
  - `backend/core/llm.py`: added `max_tokens_override`, context-window introspection, and `LLMContextLimitError` detection for upstream context-limit failures.
  - `backend/core/chat_engine.py`: added message/token budget fitting before every LLM dispatch (history trimming + completion cap), runtime budget telemetry events, and truthful `context_budget_exceeded` (400) mapping for context-limit failures.
- Routing discipline:
  - `backend/core/prompt_builder.py`: added explicit intent-to-route inference (`repair_or_debug`, `planning`, `doc_analysis`, `retrieval_or_file`, etc.), route-aware task-overlay mapping, and route propagation into prompt accounting.
  - `/api/chat` responses now expose conceptual route in `meta.route` (separate from `meta.llm_route` transport route).
- File/tool capability exposure:
  - `backend/tools/builtins.py`: added read-only `file_search` tool with attachment-path-first behavior and explicit no-file note.
  - `backend/tools/engine.py`: allow `file_search` when `FRIDAY_TOOLS_ENABLED=0` (guarded by `FRIDAY_FILE_SEARCH_ALLOW_WHEN_TOOLS_DISABLED`), while keeping mutating tools blocked.
  - `backend/core/chat_engine.py`: added auto file-search recovery for retrieval/file intents when no tool call is produced.
- Prompt/output contract hardening:
  - `prompts/system/layers/runtime_context_30b_v1.jinja` and `runtime_context_7b_v1.jinja`: added route/contract guardrails for strict format adherence, retrieval-first behavior, uncertainty handling, and semantic-preserving rewrites.
  - `backend/core/interaction_policy.py` + `backend/core/response_shaper.py`: detect strict-format/code-output requests and suppress post-shaping mutations that were breaking formats (`Want details?`, auto-bulletization, truncation).
- Eval path isolation:
  - `evals/runner/schema.py`, `evals/runner/config*.yaml`, `evals/runner/run_corpus.py`: added `per_task_identity` and per-task `X-Friday-Device` isolation to avoid cross-task context bloat in eval runs.
- Tests added/updated:
  - `tests/test_chat_budgeting.py`
  - `tests/test_tool_engine_file_search.py`
  - `tests/test_prompt_builder.py` (route inference assertions)
  - `tests/test_interaction_policy.py` (strict-format/code-output policy assertions)
  - `tests/test_response_shaper.py` (strict-format/code-output shaping assertions)
- Why:
  - remove preventable runtime 502s from context/token overrun, make route intent visible and discriminative, ensure file-dependent tasks actually exercise retrieval behavior, and reduce output-shape regressions on constrained prompts.
- New env flags:
  - `FRIDAY_LLM_CONTEXT_WINDOW`
  - `FRIDAY_LLM_CONTEXT_SAFETY_MARGIN_TOKENS`
  - `FRIDAY_LLM_MIN_COMPLETION_TOKENS`
  - `FRIDAY_FILE_SEARCH_ALLOW_WHEN_TOOLS_DISABLED`
  - `FRIDAY_AUTO_FILE_SEARCH_LIMIT`
  - `FRIDAY_FILE_SEARCH_FALLBACK_SCAN`
  - `FRIDAY_FILE_SEARCH_FALLBACK_ROOTS`
  - `FRIDAY_FILE_SEARCH_MAX_FILES`
  - `FRIDAY_FILE_SEARCH_MAX_BYTES_PER_FILE`
- How to test:
  - `python3 -m pytest -q tests/test_prompt_builder.py tests/test_interaction_policy.py tests/test_response_shaper.py tests/test_chat_budgeting.py tests/test_tool_engine_file_search.py`
  - `python3 -m pytest -q tests/test_chat_recovery.py tests/test_coder_fallback.py tests/test_eval_runner.py`
  - `python3 -m pytest -q tests/test_codex_standards.py --noconftest`
  - targeted route/tool rerun: `evals/runs/remediation_targeted_v1c/run_results.jsonl`
  - runtime-smoke rerun: `evals/runs/remediation_runtime_smoke_v1/run_results.jsonl`

### 2026-04-14 (OpenAI analysis phase: run artifact diagnosis loop)
- Added analysis package under `evals/analysis/`:
  - `evals/analysis/analyze_run.py`
  - `evals/analysis/schema.py`
  - `evals/analysis/prompts.py`
  - `evals/analysis/openai_client.py`
  - `evals/analysis/heuristics.py`
  - `evals/analysis/README.md`
  - `evals/analysis/config.example.yaml`
- Added lightweight analysis tests:
  - `tests/test_eval_analysis.py` (schema validation, heuristic tagging, analysis-record id generation, resume key logic)
- Analysis outputs now written under `evals/analysis_runs/<analysis_run_id>/`:
  - `analysis_manifest.json`
  - `analysis_input.jsonl`
  - `analysis_results.jsonl`
  - `analysis_summary.json`
  - `analysis_report.md`
  - optional `priority_slices.jsonl`
- Why:
  - convert runner evidence into structured diagnostic outputs with a clear split between deterministic local triage and optional OpenAI-based failure/fix-layer classification.
- New env flags:
  - `OPENAI_API_KEY` required only when OpenAI analysis is enabled (`--no-openai`/`--heuristic-only` bypasses it).
- How to test:
  - `python3 -m py_compile evals/analysis/schema.py evals/analysis/prompts.py evals/analysis/openai_client.py evals/analysis/heuristics.py evals/analysis/analyze_run.py tests/test_eval_analysis.py`
  - `python3 -m pytest -q tests/test_eval_analysis.py`
  - `python3 evals/analysis/analyze_run.py --run-id gold_full_v1 --config evals/analysis/config.example.yaml --outdir evals/analysis_runs --dry-run`
  - `python3 evals/analysis/analyze_run.py --run-id gold_full_v1 --config evals/analysis/config.example.yaml --outdir evals/analysis_runs --analysis-run-id gold_full_v1_analysis_heuristic_v2 --heuristic-only`
  - `python3 evals/analysis/analyze_run.py --run-id gold_full_v1 --config evals/analysis/config.example.yaml --outdir evals/analysis_runs --analysis-run-id gold_full_v1_analysis_smoke_v1 --limit 3`
  - `python3 evals/analysis/analyze_run.py --run-id gold_full_v1 --config evals/analysis/config.example.yaml --outdir evals/analysis_runs --analysis-run-id gold_full_v1_analysis_smoke_v1 --limit 3 --resume`

### 2026-04-14 (Corpus runner v1: recorder-only execution bridge)
- Added runner package under `evals/runner/`:
  - `evals/runner/run_corpus.py`
  - `evals/runner/schema.py`
  - `evals/runner/client.py`
  - `evals/runner/normalize.py`
  - `evals/runner/README.md`
  - `evals/runner/config.example.yaml`
- Added lightweight tests for runner behavior:
  - `tests/test_eval_runner.py` (normalization, stable ID selection, resume-key logic, schema validation)
- Runner output artifacts now produced per run under `evals/runs/<run_id>/`:
  - `run_manifest.json`
  - `run_results.jsonl`
  - `run_summary.json`
  - `run_report.md`
  - optional `failures.jsonl`
- Why:
  - establish a clean offline bridge from corpus tasks to reproducible Friday execution evidence without grading logic or OpenAI-side analysis loops.
- New env flags:
  - none required; runner identity uses request headers (`X-Friday-Device`) and config file values.
- How to test:
  - `python3 -m py_compile evals/runner/schema.py evals/runner/normalize.py evals/runner/client.py evals/runner/run_corpus.py`
  - `python3 -m pytest -q tests/test_eval_runner.py`
  - `python3 evals/runner/run_corpus.py --mode gold_only --config evals/runner/config.example.yaml --dry-run`
  - `python3 evals/runner/run_corpus.py --mode generated_only --config evals/runner/config.example.yaml --dry-run`
  - `python3 evals/runner/run_corpus.py --mode combined --config evals/runner/config.example.yaml --dry-run`
  - `python3 evals/runner/run_corpus.py --mode combined --config evals/runner/config.example.yaml --outdir evals/runs --run-id smoke_runner_v1 --limit 3`
  - `python3 evals/runner/run_corpus.py --mode combined --config evals/runner/config.example.yaml --outdir evals/runs --run-id smoke_runner_v1 --limit 3 --resume`

### 2026-04-14 (Eval gold set freeze + offline corpus generation)
- Added a stable 50-task gold control set for Friday evals:
  - `evals/gold/gold_tasks_v1.jsonl`
- Added offline corpus generation tooling driven by OpenAI Responses API:
  - `evals/corpus/schema.py` (pydantic schemas)
  - `evals/corpus/prompts.py` (structured generation prompts + JSON schema)
  - `evals/corpus/generate_corpus.py` (generation loop, validation, dedupe, report writer)
  - `evals/corpus/README.md` (usage and guardrails)
- Generated first corpus artifact set:
  - `evals/generated/corpus_v1.jsonl` (300 variants; 6 per gold task)
  - `evals/generated/corpus_generation_report.md` (counts, rejection reasons, route/category/difficulty distributions, sample variants)
- Why:
  - create a local-first, inspectable eval substrate for Friday routing/tooling/grounding/repair diagnostics without creating a live OpenAI↔Friday loop.
- New env flags:
  - none required beyond existing `OPENAI_API_KEY` for generation runtime.
- How to test:
  - `python3 -m py_compile evals/corpus/schema.py evals/corpus/prompts.py evals/corpus/generate_corpus.py`
  - `python3 evals/corpus/generate_corpus.py --gold-path evals/gold/gold_tasks_v1.jsonl --output-path evals/generated/corpus_v1.jsonl --report-path evals/generated/corpus_generation_report.md --variants-per-task 6`
  - `python3 - <<'PY' ... parse evals/generated/corpus_v1.jsonl and verify 300 unique variant_id/user_input rows ... PY`

### 2026-04-11 (Friday UI -> Althing bridge mode)
- Added explicit UI bridge route so existing Friday frontend can target Althing by default without a new UI:
  - `backend/api/althing_chat.py` (`POST /api/althing/chat`)
  - `backend/main.py` router wiring
  - `core/config.py` (`AlthingBridgeConfig`)
- Frontend now supports explicit entry modes with persisted selection:
  - `Althing` (default) -> `/api/althing/chat`
  - `Direct Friday` -> `/api/chat`
  - updated files: `frontend/src/services/api.ts`, `frontend/src/App.tsx`
- Added recursion guard at bridge boundary:
  - `/api/althing/chat` rejects `X-Althing-Handoff: 1` (and handoff-shaped payload markers) with `409 recursion_guard`
  - Althing execution handoff now sets `X-Althing-Handoff: 1` in Friday calls (`/mnt/data/althing/router/main.py`)
- Added tests:
  - `tests/test_althing_bridge_api.py`
- Added docs:
  - `docs/FRIDAY_UI_ALTHING_BRIDGE.md`
  - `README.md` and `RUNBOOK.md` bridge mode notes
- Bridge fallback behavior now degrades to direct Friday when the upstream router reports `no_routable_lane_available` / `state_unavailable`, while preserving the existing repo/file direct-fallback path.
- New env flags:
  - `FRIDAY_ALTHING_BRIDGE_ENABLED`
  - `FRIDAY_ALTHING_BASE_URL`
  - `FRIDAY_ALTHING_ROUTE_PATH`
  - `FRIDAY_ALTHING_TIMEOUT_MS`
  - `FRIDAY_ALTHING_MODEL_HINT`
  - `FRIDAY_UI_DEFAULT_MODE`
- Why:
  - align practical user entry path with architecture intent (`UI shell` + `Althing orchestrator`) while preserving direct Friday fallback mode.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_althing_bridge_api.py`
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_handoff_api.py`
  - `npm --prefix frontend run build`

### 2026-04-11 (Native typed Althing handoff boundary)
- Added first-class native handoff API surface:
  - `backend/api/handoff.py` (`POST /api/handoff`)
  - `backend/handoff/models.py` (typed request/response envelopes)
  - `backend/handoff/service.py` (bounded code-slice verification/revision harness + trace emission)
  - `backend/handoff/__init__.py`
  - `backend/main.py` router wiring
- Added typed config for handoff runtime controls in `core/config.py` via `HandoffConfig`.
- Hardened command execution in handoff verification:
  - normalized `python`/`python3` commands to the active interpreter (`sys.executable`)
  - explicit handling for missing/not-executable commands with structured verification failures (no uncaught server errors)
- Added endpoint tests:
  - `tests/test_handoff_api.py`
- Added operator docs:
  - `docs/FRIDAY_HANDOFF_ENDPOINT.md`
  - `README.md` and `RUNBOOK.md` updates for native handoff visibility/smoke path.
- New env flags:
  - `FRIDAY_HANDOFF_ENABLED`
  - `FRIDAY_HANDOFF_TRACE_ENABLED`
  - `FRIDAY_HANDOFF_TRACE_PATH`
  - `FRIDAY_HANDOFF_MAX_REVISION_BUDGET`
  - `FRIDAY_HANDOFF_MAX_CANDIDATE_CHARS`
  - `FRIDAY_HANDOFF_MAX_TIMEOUT_MS`
  - `FRIDAY_HANDOFF_ALLOW_COMMAND_EXECUTION`
  - `FRIDAY_HANDOFF_COMMAND_TIMEOUT_MS`
- Why:
  - replace prompt-wrapped handoff-over-chat with an explicit typed boundary that supports bounded execution verification and correlated telemetry.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_handoff_api.py`

### 2026-04-06 (Bounded refinement layer V1)
- Added a bounded self-distillation layer for runtime replies (critique → patch/regenerate, optional compare):
  - `backend/core/refinement.py`
  - `backend/core/chat_engine.py` (refinement integration + meta events)
  - `prompts/tasks/friday_refinement_*_v1.md`
- Added policy tests: `tests/test_refinement_policy.py`
- Added ADR + report:
  - `docs/decisions/ADR-0002-bounded-refinement-layer.md`
  - `docs/tasks/friday_refinement_v1_report.md`
- New env flags:
  - `FRIDAY_REFINEMENT_ENABLED`
  - `FRIDAY_REFINEMENT_MODE`
  - `FRIDAY_REFINEMENT_MAX_EXTRA_TURNS`
  - `FRIDAY_REFINEMENT_COMPARE_ENABLED`
  - `FRIDAY_REFINEMENT_TRACE_ENABLED`
  - `FRIDAY_REFINEMENT_TRACE_PATH`
  - `FRIDAY_REFINEMENT_MIN_SCORE_FOR_ACCEPT`
  - `FRIDAY_REFINEMENT_FAIL_OPEN`
- How to test:
  - `pytest tests/test_refinement_policy.py -q`
  - `python3 evals/runner.py --check`

### 2026-03-30 (Docs handoff + energy-save shutdown path)
- Updated operator docs to include explicit idle shutdown command:
  - `README.md`: added `docker compose down` under root wrapper usage.
  - `RUNBOOK.md`: added `docker compose down` under Docker startup path.
- Why:
  - keep Friday off when not actively used to save GPU/power budget while preserving one-command restart path.
- How to test:
  - `docker compose up -d`
  - `bash scripts/check_friday_stack.sh`
  - `docker compose down`

### 2026-03-30 (Runtime lock-down, volume ownership hardening, coder health/route safeguards)
- Locked the coder runtime contract to the known-good Lex lineage and V100 profile in docs:
  - documented exact image path assumptions (`local/vllm-openai:lexi` -> `local/vllm-openai:friday-v100`)
  - documented known-good serving params for current host (`TP=2`, `max_model_len=8192`, `max_num_seqs=2`, `gpu_memory_utilization=0.95`)
  - documented this as V100/SM70-specific and derived from Lex runtime lineage, not generic latest vLLM assumptions
- Fixed persistent `/data`/`/logs` ownership drift in compose startup:
  - added one-shot `friday-volume-init` service to `docker-compose.app.yml`
  - backend now depends on `friday-volume-init` completion before boot
  - root wrapper (`docker-compose.yaml`) now includes `friday-volume-init`
  - startup helper (`scripts/friday_up.sh`) now runs `friday-volume-init` in external-Muninn/no-deps path
- Added coder-specific health signal and fast stack health command:
  - backend `/readyz` now includes `services.coder` using OpenAI `/v1/models` probing
  - added startup soft warning when coder is enabled but unreachable
  - new `scripts/check_friday_stack.sh` validates compose state + backend/frontend/muninn + coder `/v1/models`
- Hardened coder fallback path:
  - remote LLM transport/JSON failures now normalize to `LLMRequestError`
  - coder route now catches unexpected exceptions and falls back to primary
  - added `FRIDAY_CODER_TIMEOUT_SECONDS` (default 30 via env templates, override for faster failover)
- Why:
  - preserve the currently working V100 stack as the explicit baseline, prevent recurring volume-permission incidents, and make coder-route health/degradation observable.
- New env flags:
  - `FRIDAY_APP_UID` (default `10001`)
  - `FRIDAY_APP_GID` (default `10001`)
  - `FRIDAY_CODER_TIMEOUT_SECONDS` (default `30`)
- How to test:
  - `docker compose config`
  - `docker compose up -d --build`
  - `bash scripts/check_friday_stack.sh`
  - `curl -fsS http://127.0.0.1:8010/v1/models`
  - `curl -sS http://127.0.0.1:9001/api/chat -H 'Content-Type: application/json' -H 'X-Friday-Device: bakeoff' -d '{"prompt":"Write Python hello world", "use_coder_model": true}'`

### 2026-03-30 (Lex-runtime aligned coder image path + V100-compatible startup profile)
- Revalidated coder path against Lex known-good runtime sources:
  - Lex compose image/build reference: `local/vllm-openai:lexi` from `Lex/docker/vllm/Dockerfile`
  - active healthy Lex host vLLM process shape reviewed (`/mnt/data/vllm-venv`, conservative parallelism/profile)
- Updated Friday coder service to a V100-compatible local image path with explicit local build extension:
  - `docker-compose.models.yml` `friday-coder` now uses `image: local/vllm-openai:friday-v100`
  - build source: `docker/friday-coder-vllm.Dockerfile` (`FROM local/vllm-openai:lexi` + `bitsandbytes` install)
  - keeps GPU pinning to host GPUs `2,3,4,5` and container CUDA ordinal map `0,1,2,3`
- Tuned coder startup for stable boot on current V100 host:
  - tensor parallel size `2`
  - `max_model_len=8192`
  - `max_num_seqs=2`
  - `gpu_memory_utilization=0.95`
- Why:
  - direct `vllm-openai:latest` path failed on this host (kernel/runtime incompatibilities for this model/hardware profile); Lex-aligned runtime plus conservative memory profile reached healthy OpenAI API serving.
- How to test:
  - `docker compose up -d --build friday-coder`
  - `curl -fsS http://127.0.0.1:8010/v1/models`
  - `curl -sS http://127.0.0.1:8010/v1/chat/completions ...`
  - `curl -sS http://127.0.0.1:9001/api/chat -d '{"use_coder_model":true,...}'`

### 2026-03-29 (Local Qwen3 coder vLLM compose service + root one-command startup)
- Added dedicated coding-model vLLM compose service:
  - `docker-compose.models.yml` new `friday-coder` service
  - serves `/mnt/data/models/Qwen/qwen3-coder-30b-a3b-instruct`
  - pinned to GPUs `2,3,4,5` via `NVIDIA_VISIBLE_DEVICES`/`CUDA_VISIBLE_DEVICES` and explicit `deploy.resources.reservations.devices.device_ids`
  - OpenAI-compatible endpoint on port `8010` with `/v1/models` healthcheck and `restart: unless-stopped`
- Added root-level compose wrapper for one-command startup:
  - `docker-compose.yaml` now extends split app/models services and includes `friday-coder`
  - enables `docker compose up -d` from repo root for app + coder topology
- Updated backend runtime wiring defaults in compose/env:
  - `docker-compose.app.yml` defaults coder route env for backend (`FRIDAY_CODER_ENABLED`, `FRIDAY_CODER_MODEL_NAME`, `FRIDAY_CODER_BASE_URL`)
  - `.env.example` / `.env.models.example` now include coder model path, GPU set, base URL, and host port defaults
  - `env_file` now treats `.env.runtime` as optional for direct root compose startup
- Extended startup scripts:
  - `scripts/friday_up.sh` autodiscovers coder endpoint and writes `FRIDAY_CODER_BASE_URL` into `.env.runtime`
  - `scripts/friday_down.sh` clears `FRIDAY_CODER_BASE_URL` in regenerated runtime env
- Docs updated for operator flow:
  - `README.md`, `RUNBOOK.md` include root `docker compose up -d` path and coder endpoint details
- Why:
  - provide a stable, dedicated local coding endpoint for Friday without replacing the existing split compose architecture.
- How to test:
  - `docker compose config`
  - `docker compose up -d`
  - `curl -fsS http://127.0.0.1:8010/v1/models`
  - `curl -fsS http://127.0.0.1:9001/healthz`

### 2026-03-27 (Evidence leak closure + procedural stress prep)
- Closed remaining structured-evidence edge leaks in Friday writer boundary:
  - `backend/memory/evidence.py`
  - legacy freeform entries now fail explicitly (`evidence[i] must be an object`) instead of bubbling generic runtime errors
  - added strict metadata-size cap policy via `FRIDAY_MUNINN_EVIDENCE_META_MAX_BYTES` (default `8192` bytes), enforced pre-transport
  - added deterministic duplicate-evidence dedupe by canonical item signature
- Added focused coverage:
  - `tests/test_procedure_evidence.py`
  - new checks for explicit legacy-string rejection, metadata cap enforcement, dedupe, and provider reject-reason quality
- Updated procedural integration docs:
  - `docs/PROCEDURAL_OVERLAY.md` now documents explicit rejection, metadata cap policy, and dedupe behavior.
- Why:
  - remove remaining ambiguous edge-path failures and ensure evidence payload discipline holds under adversarial inputs before broader procedural stress runs.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_procedure_evidence.py tests/test_procedures.py -q`

### 2026-03-27 (Procedure lifecycle evidence hardening for Muninn writeback)
- Added canonical typed Muninn evidence builder/validator for procedure lifecycle paths:
  - `backend/memory/evidence.py`
  - strict allowed shape: `type` + optional `ref`/`excerpt`/`meta`
  - strict allowed `type`: `chat|log|diff|file|url|commit|test`
- Updated procedural reflection flow to emit structured evidence payloads instead of ad hoc string refs:
  - `backend/procedures/service.py`
  - `backend/procedures/reflection.py`
  - `backend/procedures/models.py` (`LifecycleDecision` now carries `structured_evidence`)
- Hardened Muninn provider lifecycle writeback path:
  - `backend/memory/muninn_provider.py`
  - `stage_procedure_lifecycle` now validates structured evidence locally and maps lifecycle candidates to `POST /v0/memory/procedures/reflect`
  - malformed evidence fails before transport and is returned as rejected candidate reasons
- Added tests:
  - `tests/test_procedure_evidence.py`
  - validates canonical shape, pre-transport rejection for malformed evidence, and valid reflect writeback payload construction
- Docs:
  - updated `docs/PROCEDURAL_OVERLAY.md` with structured evidence contract + builder path
- Why:
  - prevent evidence payload drift and remove ad hoc caller-side construction so Muninn receives canonical, validated evidence payloads.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_procedure_evidence.py tests/test_procedures.py -q`

### 2026-03-27 (Lexi vLLM verification + throughput baseline)
- Added repeatable Lexi verification and benchmark harness:
  - `tools/eval/verify_lexi_vllm.py`
  - verifies reachability, model discovery, minimal generation, optional Friday `/api/chat` E2E, and A/B/C throughput scenarios.
- Added results note:
  - `docs/tasks/lexi_vllm_verification_results_2026-03-27.md`
- Fixed LLM autodiscovery bug in startup script:
  - `scripts/friday_up.sh` now requires valid `/v1/models` for LLM host detection (no longer treats generic `/health` as sufficient).
  - prevents misclassifying Muninn on `:8000` as the LLM endpoint.
- Updated runtime env snapshot for current host topology:
  - `.env.runtime` `LLM_BASE_URL` set to `http://host.docker.internal:8008`.
- Why:
  - establish factual Lexi connectivity status, isolate config mismatches, and create a repeatable throughput baseline for future comparisons.
- How to test:
  - direct + throughput:
    - `python3 tools/eval/verify_lexi_vllm.py --base-url http://127.0.0.1:8008 --model Lexi --run-throughput`
  - include Friday path:
    - run backend with `FRIDAY_LLM_ENABLED=1`, `FRIDAY_MODEL_NAME=Lexi`, `LLM_BASE_URL=http://127.0.0.1:8008`, writable `FRIDAY_DATA_DIR`/`FRIDAY_LOG_DIR`
    - then: `python3 tools/eval/verify_lexi_vllm.py --base-url http://127.0.0.1:8008 --model Lexi --friday-base-url http://127.0.0.1:9001`

### 2026-03-27
- Added bounded Hermes-style procedural adaptation layer (feature-flagged):
  - new modules: `backend/procedures/models.py`, `backend/procedures/catalog.py`, `backend/procedures/retrieval.py`, `backend/procedures/reflection.py`, `backend/procedures/service.py`
  - chat wiring for retrieval/ranking/bounded prompt injection and gated lifecycle reflection: `backend/core/chat_engine.py`, `backend/core/prompt_builder.py`
- Extended memory provider contracts to support procedural retrieval + lifecycle staging without introducing a parallel memory backend:
  - `backend/memory/provider.py`
  - `backend/memory/muninn_provider.py`
  - `backend/memory/factory.py`
- Added env-gated Mimir telemetry runtime hooks:
  - `backend/telemetry/mimir_trace.py`
  - emits structured JSONL events (`task_started`, `retrieval_*`, `context_item_selected`, `decision_point`, `task_completed`)
- Added trace analysis helper:
  - `tools/analysis/mimir_trace_summary.py`
- Added docs:
  - recon note: `docs/tasks/hermes_mimir_phase0_recon.md`
  - overlay architecture + lifecycle + flags: `docs/PROCEDURAL_OVERLAY.md`
  - architecture/checkpoint + README updates for response metadata/env flags
- Added tests:
  - `tests/test_procedures.py` for ranking budgets, reflection gating, and runtime overlay injection.
- Why:
  - keep constitutional prompt/safety/orchestration fixed while allowing bounded procedural skill adaptation with explicit typed lifecycle operations and Muninn-backed durability.
  - generate inspectable, low-overhead telemetry for Mimir navigation/route analysis.
- New env flags:
  - `FRIDAY_PROCEDURES_ENABLED`
  - `FRIDAY_PROCEDURES_INCLUDE_SEEDED`
  - `FRIDAY_PROCEDURES_MAX_RETRIEVED`
  - `FRIDAY_PROCEDURES_MIN_CONFIDENCE`
  - `FRIDAY_PROCEDURES_MAX_INJECT`
  - `FRIDAY_PROCEDURES_MAX_INJECT_STEPS`
  - `FRIDAY_PROCEDURES_MAX_INJECT_PITFALLS`
  - `FRIDAY_PROCEDURES_REFLECTION_ENABLED`
  - `FRIDAY_MIMIR_TRACE_ENABLED`
  - `FRIDAY_MIMIR_TRACE_DIR`
  - `FRIDAY_MIMIR_TRACE_SESSION_ID`
  - `FRIDAY_MIMIR_TRACE_RUN_LABEL`
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_procedures.py tests/test_prompt_builder.py tests/test_chat_recovery.py tests/test_model_switching.py -q`
  - optional runtime trace:
    - `FRIDAY_PROCEDURES_ENABLED=1 FRIDAY_PROCEDURES_REFLECTION_ENABLED=1 FRIDAY_MIMIR_TRACE_ENABLED=1 python -m backend.main`
    - run `/api/chat` requests, then inspect `.mimir/trace/session-*.jsonl`
    - summarize with `python tools/analysis/mimir_trace_summary.py .mimir/trace/session-<id>.jsonl`

### 2026-02-20
- Added deterministic interaction policy + shaping stack for chat UX hardening:
  - new policy kernel: `backend/core/interaction_policy.py`
  - new deterministic shaper: `backend/core/response_shaper.py`
  - chat wiring + certainty/recovery metadata/events: `backend/core/chat_engine.py`
  - prompt policy injection (`<INTERACTION_POLICY>`): `backend/core/prompt_builder.py`
  - runtime event forwarding on async agent runs: `backend/agentic/service.py`
- Behavior updates:
  - v1 modes are `focused | neutral | warm` (rule-based inference)
  - `playful` remains hard-gated behind `FRIDAY_INTERACTION_PLAYFUL_ENABLED=1` and explicit request
  - deterministic response constraints: banter budget, one-question cap, one-screen default
  - confidence calibration now prefers high certainty on tool outputs and command/test-like success signals
  - blame-free fallback language for tool-failure loops
- Added tests:
  - `tests/test_interaction_policy.py`
  - `tests/test_response_shaper.py`
  - `tests/test_chat_recovery.py`
  - updates: `tests/test_prompt_builder.py`, `tests/test_coder_fallback.py`, `tests/test_agent_api.py`
- New env flags:
  - `FRIDAY_INTERACTION_DEFAULT_MODE`
  - `FRIDAY_INTERACTION_ONE_SCREEN_CHARS`
  - `FRIDAY_INTERACTION_PLAYFUL_ENABLED`
- Why: enforce UX discipline deterministically rather than relying on model compliance, while preserving existing coder-route fallback and async agent API contracts.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_interaction_policy.py tests/test_response_shaper.py tests/test_prompt_builder.py tests/test_coder_fallback.py tests/test_chat_recovery.py tests/test_agent_api.py -q`
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_model_switching.py -q`

### 2026-02-18
- Aligned vLLM model naming defaults to Lexi across runtime/config:
  - `backend/core/llm.py` now defaults `FRIDAY_MODEL_NAME` to `Lexi` (with blank-env fallback)
  - `docker-compose.yaml` backend env default now `FRIDAY_MODEL_NAME=Lexi`
  - `docker-compose.models.yml` now serves `${FRIDAY_MODEL_NAME:-Lexi}` instead of a hardcoded legacy name
- Added explicit Lexi model env examples:
  - `.env` includes `FRIDAY_MODEL_NAME=Lexi`
  - `.env.example` and `.env.models.example` include `FRIDAY_MODEL_NAME=Lexi`
- Updated operator docs (`README.md`, `RUNBOOK.md`, `docs/RUNBOOK.md`) to clarify:
  - compose LLM URL (`http://llm:8000`)
  - host-run backend to host vLLM URL (`http://127.0.0.1:8008`)
- Why: ensure FRIDAY requests the active vLLM model id (`Lexi`) by default and avoid model-name drift between backend and served vLLM name.
- How to test:
  - `curl -fsS http://127.0.0.1:8008/v1/models`
  - `FRIDAY_LLM_ENABLED=1 FRIDAY_MODEL_NAME=Lexi LLM_BASE_URL=http://127.0.0.1:8008 python -m backend.main`
  - `curl -sS http://127.0.0.1:9001/api/chat -H 'Content-Type: application/json' -H 'X-Friday-Device: lexi-check' -d '{"prompt":"status check"}'`
- Added OpenClaw-style agentic spine scaffolding:
  - new async run API: `POST /api/agent`, `POST /api/agent/wait`, `GET /api/agent/{run_id}`
  - run lifecycle events (`lifecycle`, `assistant`, `tool`, `error`) in `backend/agentic/events.py`
  - per-session + global lane queue control in `backend/agentic/queue.py`
  - run snapshot + wait semantics in `backend/agentic/wait.py`
  - run orchestration service in `backend/agentic/service.py`
- Wired backend entrypoint to include the new agent router in `backend/main.py`
- Added optional coding-specialist model route with fallback in chat runtime:
  - request-level trigger: `agent_profile:"coding"` or `use_coder_model:true`
  - env route: `FRIDAY_CODER_ENABLED`, `FRIDAY_CODER_MODEL_NAME`, `FRIDAY_CODER_BASE_URL`, `FRIDAY_CODER_API_KEY`
  - fallback behavior: if coder route fails, automatically use primary LLM route
- Updated docs:
  - `README.md`, `RUNBOOK.md`, `docs/RUNBOOK.md`
- Why: establish a durable asynchronous agent run contract now, while keeping `POST /api/chat` stable; preserve optional coder specialization without making it a hard dependency.
- How to test:
  - `pytest tests/test_agent_api.py tests/test_coder_fallback.py tests/test_model_switching.py tests/test_prompt_builder.py`
  - `curl -sS http://127.0.0.1:9001/api/agent -H 'Content-Type: application/json' -H 'X-Friday-Device: smoke-agent' -d '{"prompt":"hello","idempotency_key":"smoke-agent-1"}'`
  - `curl -sS http://127.0.0.1:9001/api/agent/wait -H 'Content-Type: application/json' -d '{"run_id":"<run_id>","timeout_ms":30000,"include_result":true}'`

### 2026-02-16
- Hardened Muninn integration with explicit connect/read/overall timeout controls and retry/backoff in `backend/memory/muninn_client.py`
- Added provider fallback metadata so runtime responses reflect actual provider used (`muninn|legacy|none`) instead of configured provider only
- Added guardrails:
  - memory injection caps (`FRIDAY_MEMORY_MAX_INJECT_*`)
  - confirmation endpoint caps (`FRIDAY_MEMORY_CONFIRM_MAX_*`)
  - first-pass sensitive candidate marking (`email`/`phone` regex + confirm-required policy)
- Upgraded identity resolution priority to:
  - account header → session header/cookie → device header/cookie → `ent_local_user`
- Added compose service topology for `friday-backend` + `muninn` with non-blocking dependency and health checks
- Replaced outdated tests with provider/runtime-focused pytest coverage and added `pytest.ini` collection rules
- Updated docs for source-of-truth alignment:
  - `README.md`
  - `docs/RUNBOOK.md`
  - `docs/DECISIONS.md`
  - `ROADMAP.md`
- Why: remove docs/runtime drift, raise reliability/security baseline, and complete Muninn-first operational path without making memory a hard dependency
- How to test:
  - `pytest`
  - `bash scripts/smoke_memory.sh`

- Cut over chat memory integration to provider abstraction with env selection: `FRIDAY_MEMORY_PROVIDER=muninn|legacy|none` (default `muninn`)
- Added `backend/memory/provider.py`, `backend/memory/muninn_provider.py`, and `backend/memory/factory.py`
- Added Muninn HTTP wiring for:
  - `POST /v0/memory/rehydrate`
  - `POST /v0/memory/stage_candidates`
  - `POST /v0/memory/confirm_candidates`
  - `POST /v0/memory/list_pending`
- Updated chat pipeline to:
  - inject rendered `<SYSTEM_MEMORY>` cards pre-prompt
  - stage conservative post-response memory candidates
  - return memory metadata (`accepted_ids`, `pending_ids`, reasons) in `/api/chat`
- Added memory relay endpoints:
  - `POST /api/memory/confirm`
  - `POST /api/memory/pending`
- Added minimal frontend confirmation flow (Accept all / Reject all) when pending IDs are present
- Added smoke script scaffold: `scripts/smoke_memory.sh`
- Added repo coordination artifacts:
  - `.agents/skills/integration-cutover/SKILL.md`
  - `.agents/skills/web-ui-minimal-confirm/SKILL.md`
  - `.agents/skills/env-config-hygiene/SKILL.md`
  - `.agents/skills/smoke-testing/SKILL.md`
- Why: replace legacy in-process memory coupling with an external Muninn service while preserving rollback safety and non-blocking chat behavior
- New/changed env flags:
  - `FRIDAY_MEMORY_PROVIDER`
  - `MUNINN_BASE_URL`
  - `MUNINN_NAMESPACE`
  - `MUNINN_PROFILE`
  - `MUNINN_HTTP_TIMEOUT_SECONDS`
  - `FRIDAY_DEBUG_MEMORY`
- How to test:
  - `python -m backend.main` then `curl -s http://localhost:9001/healthz`
  - `curl -s http://localhost:9001/api/chat -H 'Content-Type: application/json' -H 'X-Friday-Device: test' -d '{\"prompt\":\"I prefer tea\"}'`
  - `bash scripts/smoke_memory.sh`

### 2026-01-29
- Added debug gating for tool error turns (default drop), vendor import guard script, and regression check helper
- Why: avoid tool-error feedback loops and add a lightweight pre-import tripwire
- Flags added/changed: FRIDAY_DEBUG_TOOL_ERRORS
- How to test: run the eval tripwire command from `docs/RUNBOOK.md`
- Known issues: regression check validates JSONL structure only (no model assertions)

- Wired end-to-end tool calls with strict parsing, schema validation, trust gating, and audit logging
- Added workspace-aware memory paths, routing helper, and audit log JSONL
- Added trust boundary classifier, debug memory APIs, and stub security contracts
- Why: harden tool execution and prepare for Moltbot-style routing without unsafe defaults
- Flags added/changed: FRIDAY_TRUST_MODE, FRIDAY_TRUST_SAFE_TOOLS, FRIDAY_DEBUG_APIS_ENABLED
- How to test: enable flags, run `python tools/eval/smoke_eval.py`, and call `/api/memory/*` with debug enabled
- Known issues: tool execution still requires explicit confirmation (default ON)

- Added tool schema/validation engine, built-in memory tools, and evaluation harness
- Added stub service endpoints + service contracts doc for STT/TTS/Vision/Avatar
- Why: make tools deterministic and testable while keeping future modalities inert
- Flags added/changed: FRIDAY_TOOLS_ENABLED, FRIDAY_TOOLS_REQUIRE_CONFIRM
- How to test: `python tools/eval/smoke_eval.py` (with backend running for API checks)
- Known issues: tool calls still require explicit approval to execute

- Added prompt assembly pipeline with capabilities + memory bundle + FRIDAY exec profile
- Updated chat loop to use memory bundle retrieval and LLM message generation
- Added prompt profile/model class envs for control loop tuning
- Why: make the core loop structured and model-aware
- Flags added/changed: FRIDAY_PROMPT_PROFILE, FRIDAY_MODEL_CLASS
- How to test: `curl -X POST http://localhost:9001/api/chat -H 'Content-Type: application/json' -d '{"prompt":"Hello"}'`
- Known issues: tool schema injection is stubbed until tools are wired

- Added consolidation loop scaffold (heuristic summary + fact extraction) with job tracking
- Added summary cadence flag for deterministic consolidation triggers
- Why: enable rolling summaries and fact extraction without blocking chat
- Flags added/changed: FRIDAY_MEMORY_SUMMARY_EVERY_N_TURNS
- How to test: enable facts/summaries/consolidation flags, send N turns, inspect summaries and facts files
- Known issues: consolidation is heuristic until LLM summarizer is wired

- Added Memory v2 data model: facts store, summaries store, retrieval bundle, and memory service
- Added env flags for facts/summaries/consolidation and retrieval limits
- Why: enable structured, queryable memory beyond raw conversation logs
- Flags added/changed: FRIDAY_MEMORY_FACTS_ENABLED, FRIDAY_MEMORY_SUMMARIES_ENABLED, FRIDAY_MEMORY_CONSOLIDATION_ENABLED, FRIDAY_MEMORY_MAX_FACTS, FRIDAY_MEMORY_FACTS_RETRIEVAL_LIMIT, FRIDAY_MEMORY_SUMMARY_RETRIEVAL_LIMIT
- How to test: import `backend.memory.service.memory_service` and call `remember_fact`/`retrieve` in a REPL
- Known issues: facts/summaries retrieval is heuristic until consolidation is wired

- Added emotion-lite metadata capture (record-only) on user messages when enabled
- Why: capture coarse sentiment/arousal/confusion/urgency without changing behavior
- Flags added/changed: none (uses existing FRIDAY_EMOTION_LITE_ENABLED)
- How to test: set `FRIDAY_EMOTION_LITE_ENABLED=1` and post to `/api/chat`, then inspect JSONL when memory persistence is enabled
- Known issues: heuristic-only (no model)

- Added `/api/capabilities` endpoint and shared health-check helpers
- Expanded backend compose env to pass capability flags + service URLs into the container
- Why: allow frontend gating and make enabled/available reporting consistent with env config
- Flags added/changed: none (existing flags now propagated into container)
- How to test: `curl http://localhost:9001/api/capabilities`
- Known issues: gesture/vector availability are reported as false (stubbed)

- Added in-proc jobs store with `/api/jobs` create/status/result endpoints
- /readyz now reports jobs backend status (memory or redis)
- Why: establish async job pattern before multimodal work
- Flags added/changed: none
- How to test: `curl -X POST http://localhost:9001/api/jobs -H 'Content-Type: application/json' -d '{}'`
- Known issues: jobs are queued-only (no worker yet)

- Upgraded memory to tiered store (T0 in-memory + optional T1 JSONL persistence) with vector stub
- /readyz now verifies persistence directory is writable when memory persistence is enabled
- Why: keep Phase 1 memory reliable while adding persistence behind FRIDAY_MEMORY_PERSIST_ENABLED
- Flags added/changed: none
- How to test: set `FRIDAY_MEMORY_PERSIST_ENABLED=1`, start backend, then `curl http://localhost:9001/readyz`
- Known issues: vector tier is stubbed (no-op)

- Added identity middleware to assign stable `user_id` via header/cookie and attach `X-Friday-User` response header
- Updated `/api/chat` to carry request `user_id` and return a friendly LLM-disabled response (HTTP 200)
- Why: establish stable identity buckets and keep text-only chat usable while LLM is disabled
- Flags added/changed: none
- How to test: start backend, then `curl -i -X POST http://localhost:9001/api/chat -H 'Content-Type: application/json' -d '{"prompt":"Hello"}'`
- Known issues: none

- Replaced `.env` with Phase 0 defaults (LLM disabled) and archived `.env` -> `.env.legacy`
- Rewired model profiles to service names `llm`, `stt`, `tts`, `vision`, `avatar` in `docker-compose.models.yml`
- Updated `.env.models.example` to minimal opt-in toggles
- Updated `/readyz` service keys to match URL env names (LLM_BASE_URL, STT_BASE_URL, etc.)
- Why: keep Phase 0 runnable while wiring optional models behind profiles
- Flags added/changed: FRIDAY_LLM_ENABLED default set to 0 in `.env.example`
- How to test: `docker compose -f docker-compose.yaml -f docker-compose.models.yml config > /tmp/compose.merged.yml`
- Known issues: none (models remain opt-in)

- Normalized service health probes to use `/v1/models` when base URLs end in `/v1`

- Added model compose wiring files: `docker-compose.models.yml`, `.env.models.example`
- Updated `/readyz` to report per-service status and honor *_ENABLED flags
- Updated chat error mapping to return `llm_unhealthy` when a configured LLM is unreachable
- Why: wire optional model services behind profiles without auto-start
- Flags added/changed: FRIDAY_CODER_ENABLED, FRIDAY_VISION_ENABLED, FRIDAY_OMNI_ENABLED, FRIDAY_STT_ENABLED, FRIDAY_TTS_ENABLED
- How to test: `docker compose -f docker-compose.yaml -f docker-compose.models.yml config > /tmp/compose.merged.yml`
- Known issues: none (models remain opt-in)

- Added `tools/pull_models.sh` model fetcher (HF + GitHub) with manifest output
- Why: standardize model pulls and repos for Phase 1 multimodal stack
- Flags added/changed: none
- How to test: `HF_TOKEN=... ./tools/pull_models.sh`
- Known issues: script exits if HF_TOKEN is not set

- Phase 0 stabilization: added canonical backend spine under `backend/` (entrypoint, chat, health, memory, tools)
- Deprecated legacy routes/entrypoints and removed duplicate `/process` handlers in active paths
- Fixed `start.sh`, `process_manager.py`, `Dockerfile`, `docker-compose.yaml` for a single runnable backend
- Updated frontend API wiring to `/api/chat` with flat `{text}` response
- Moved legacy memory/tools/routes/root modules to `legacy/` to enforce single systems
- Why: make docker compose run and establish a single, correct execution path
- Flags added/changed: FRIDAY_MEMORY_PERSIST_ENABLED defaulted to 0 in `.env.example`
- How to test: `docker compose up --build`, then `curl http://localhost:9001/healthz` and `curl -X POST http://localhost:9001/api/chat -H 'Content-Type: application/json' -d '{"prompt":"Hello"}'`
- Known issues: LLM requires `FRIDAY_MODEL_PATH` or `LLM_BASE_URL` to return non-error text

- Added operating contract and architecture docs: `AGENTS.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md`, `docs/MIGRATION_PLAN.md`
- Added initial project memory ledger and documented planned capability flags
- Why: establish repo rules + target architecture + migration plan before code stabilization
- Flags added/changed: none (documented planned flags only)
- How to test: N/A (docs-only change)
- Known issues: N/A

### 2026-03-27 (Procedural boundary guard kickoff)
- Started Friday procedural-adaptation refactor hardening with a boundary guard in `backend/procedures/retrieval.py`.
- Added `FRIDAY_PROCEDURES_BOUNDARY_GUARD` (default ON) to suppress procedure candidates that claim ownership of non-Friday domains (durable memory lifecycle, repo topology, cross-project atlas).
- Added regression test `test_rank_and_select_enforces_cross_project_boundary_guard` in `tests/test_procedures.py`.
- Updated `docs/PROCEDURAL_OVERLAY.md` hard-bounds section with the new guard flag.
- Why:
  - keep procedural adaptation bounded to Friday orchestration scope while cross-project architecture is delegated to Bifrost and durable memory remains Muninn-owned.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_procedures.py -q`

### 2026-03-27 (Phase 1 operational hardening)
- Hardened orchestration observability and bounded context assembly across `backend/core/chat_engine.py` and `backend/core/prompt_builder.py`.
- Added explicit prompt-accounting output (memory/procedure budget usage, deterministic ordering, truncation reasons) and exposed compact runtime metadata for procedure selection and reflection gating.
- Tightened procedural diagnostics in `backend/procedures/retrieval.py`, `backend/procedures/service.py`, and `backend/procedures/reflection.py` with typed gate reasons and reject-reason accounting.
- Improved provider boundary diagnostics in `backend/memory/muninn_provider.py` while preserving strict structured-evidence write paths.
- Made audit logging non-fatal by default in `backend/audit/logger.py` with `FRIDAY_AUDIT_STRICT` for opt-in strict failure behavior.
- Added LLM startup regression protection in `scripts/friday_up.sh` by preferring endpoints that actually expose the expected model id (default `Lexi`), and added `scripts/smoke_llm.sh` for explicit LLM-capability validation.
- Extended telemetry utility `tools/analysis/mimir_trace_summary.py` with operationally useful derived metrics and extended `tools/eval/verify_lexi_vllm.py` with optional streaming TTFT measurement.
- Updated docs and env template (`README.md`, `RUNBOOK.md`, `docs/ARCHITECTURE.md`, `ARCHITECTURE_CHECKPOINT.md`, `docs/PROCEDURAL_OVERLAY.md`, `.env.example`) to reflect current runtime reality.
- Added/updated focused tests: `tests/test_prompt_builder.py`, `tests/test_procedures.py`, `tests/test_operational_hardening.py`.
- Why:
  - align Friday runtime with current reality (bounded procedural overlay + Muninn + Mimir + Lexi/vLLM verified) and improve inspectability without prompt bloat or policy-boundary drift.
- Flags added/changed:
  - `FRIDAY_AUDIT_STRICT` (default `0`).
- How to test:
  - `pytest -q tests/test_prompt_builder.py tests/test_procedures.py tests/test_operational_hardening.py`
  - `pytest -q tests/test_model_switching.py tests/test_chat_recovery.py`
  - `python3 -m py_compile tools/eval/verify_lexi_vllm.py tools/analysis/mimir_trace_summary.py`
  - `bash scripts/smoke_llm.sh` (with vLLM running and `LLM_BASE_URL`/`FRIDAY_MODEL_NAME` set)

### 2026-03-27 (Mimir A/B navigation validation run in Friday)
- Added a lightweight A/B evaluation harness for navigation-sensitive Friday tasks:
  - `tools/analysis/mimir_ab_eval.py`
  - Baseline condition A uses `mimir query`.
  - Assisted condition B uses `mimir bundle`.
  - Runs 6 paired tasks from current operational-hardening/follow-on themes with alternating order to reduce ordering bias.
- Generated experiment artifacts:
  - run ledger: `docs/tasks/mimir_ab_2026-03-27/run_ledger.json`
  - analysis report: `docs/tasks/mimir_ab_2026-03-27/analysis_report.md`
  - final verdict: `docs/tasks/mimir_ab_2026-03-27/final_verdict.md`
  - per-run JSON outputs + trace files under `docs/tasks/mimir_ab_2026-03-27/runs/` and `docs/tasks/mimir_ab_2026-03-27/traces/`
- Why:
  - enforce controlled A/B comparison with route-efficiency metrics and hard per-task verdicts, rather than trace-presence checks.
- How to test / reproduce:
  - `python3 tools/analysis/mimir_ab_eval.py`

### 2026-03-27 (Tighter runtime A/B validation: Mimir in Friday)
- Added a resume-safe runtime A/B harness that uses the real Friday backend `/api/chat` path:
  - `tools/analysis/mimir_ab_runtime_eval.py`
  - condition A: `FRIDAY_PROCEDURES_ENABLED=0`
  - condition B: `FRIDAY_PROCEDURES_ENABLED=1` + `FRIDAY_PROCEDURES_REFLECTION_ENABLED=1`
- Contamination controls used in harness:
  - `FRIDAY_MEMORY_PROVIDER=none` and `FRIDAY_MEMORY_FALLBACK_PROVIDER=none` to suppress persistence/writeback carryover
  - separate backend process per run, unique trace session id, unique workspace/device ids
  - alternating order AB/BA across tasks
  - pair completeness gating (only complete A+B pairs counted)
- Generated runtime experiment artifacts:
  - ledger: `docs/tasks/mimir_ab_runtime_2026-03-27/run_ledger.json`
  - per-task comparison: `docs/tasks/mimir_ab_runtime_2026-03-27/per_task_comparison.md`
  - final verdict: `docs/tasks/mimir_ab_runtime_2026-03-27/final_verdict.md`
  - per-run responses/logs/traces under `docs/tasks/mimir_ab_runtime_2026-03-27/runs/` and `docs/tasks/mimir_ab_runtime_2026-03-27/traces/`
- Result:
  - counted pairs: 4/4 complete
  - helped/neutral/hurt: 0/0/4
  - overall: `Not validated yet`
- Why:
  - under the real runtime path, Mimir-assisted runs increased retrieval/selection activity and prompt/context cost but did not improve task-progress alignment for the selected tasks.
- How to reproduce:
  - `python3 tools/analysis/mimir_ab_runtime_eval.py`

### 2026-03-28 (First-target alignment fix + tight runtime A/B re-test)
- Diagnosed prior runtime A/B losses directly from artifacts and found the same generic procedures were selected first across all 4 assisted tasks, causing weak first-target specialization:
  - diagnosis note: `docs/tasks/mimir_first_target_diagnosis_2026-03-27.md`
- Implemented narrow first-target alignment fixes:
  - `backend/procedures/catalog.py`
    - added task-specific seeded procedures with concrete file-target steps for prompt-budget, reflection lifecycle, telemetry, and capability reporting follow-ups.
  - `backend/procedures/retrieval.py`
    - added specific task-family inference (`prompt_budget`, `reflection`, `telemetry`, `capability_reporting`)
    - added actionability bias and generic-attractor penalties for specific intent families.
  - `tools/analysis/mimir_ab_runtime_eval.py`
    - added first-selected procedure target metrics and expected-procedure hit checks in per-task scoring.
  - `tests/test_procedures.py`
    - added targeted ranking test ensuring task-specific seeded procedure wins first selection per intent family.
- Re-ran the same tight runtime A/B structure in a fresh artifact set:
  - `docs/tasks/mimir_ab_runtime_2026-03-27_rerun/run_ledger.json`
  - `docs/tasks/mimir_ab_runtime_2026-03-27_rerun/per_task_comparison.md`
  - `docs/tasks/mimir_ab_runtime_2026-03-27_rerun/final_verdict.md`
  - full narrative report: `docs/tasks/mimir_first_target_alignment_rerun_report_2026-03-28.md`
- Re-test result:
  - before fix: helped/neutral/hurt = `0/0/4`
  - after fix: helped/neutral/hurt = `4/0/0`
  - note: one residual edge case remains where capability-reporting prompt first-selected a telemetry procedure before still landing on correct capability file target.
- How to test:
  - `PYTHONDONTWRITEBYTECODE=1 pytest -q tests/test_procedures.py -k seeded_selection_prefers_task_specific_first_target`
  - `python3 tools/analysis/mimir_ab_runtime_eval.py --out-dir docs/tasks/mimir_ab_runtime_2026-03-27_rerun`

### 2026-03-28 (Calibration harness hardening v3 + rerun)
- Hardened precision calibration harness to make metrics capture deterministic under output-budget pressure:
  - new harness: `tools/analysis/mimir_calibration_suite_v3.py`
  - compact strict JSON extraction contract (`fcf/fcs/fef/fes/sf`) with no prose keys
  - raised baseline generation budget for calibration runs (`FRIDAY_MAX_TOKENS` 220; retry 320)
  - explicit per-run capture flags: `parse_valid`, `truncation_detected`, `required_fields_present`
  - loud capture failure mode: run marked `capture_failed` when required fields are missing (excluded from counted pairs)
  - added v2-v3 capture/outcome comparison artifact generation.
- Re-ran the same 4 challenge classes (8 paired runs) with unchanged task fixture:
  - tasks fixture: `docs/tasks/mimir_calibration_tasks_v2.json`
  - results: `docs/tasks/mimir_calibration_v3_2026-03-28/mimir_calibration_results_v3.json`
  - scorecard: `docs/tasks/mimir_calibration_v3_2026-03-28/mimir_calibration_scorecard_v3.md`
  - diagnosis: `docs/tasks/mimir_calibration_v3_2026-03-28/mimir_calibration_diagnosis_v3.md`
  - comparison: `docs/tasks/mimir_calibration_v3_2026-03-28/mimir_calibration_v2_vs_v3.md`
- Capture quality moved from under-informative to complete:
  - v2 parse_valid_rate 0.0 -> v3 1.0
  - v2 required_fields_present_rate 0.0 -> v3 1.0
- Rerun aggregate changed materially:
  - v2 helped/neutral/hurt: `0/5/3`
  - v3 helped/neutral/hurt: `7/1/0`
- Interpretation:
  - prior precision failure was materially masked by capture-layer truncation/parsing loss.
  - with hardened capture, remaining precision drift is concentrated in cross-intent neighbor confusion and wrong-neighbor opens.

### 2026-04-12 (Native Android mobile client scaffold + MVP chat workflow)
- Added a conventional Android project at `android/` with Kotlin + Jetpack Compose + Material 3:
  - Gradle project + wrapper under `android/`
  - app module package `com.friday.mobile`
- Implemented MVP mobile chat UX:
  - transcript with user/assistant/system bubbles
  - anchored multiline composer + send button
  - in-flight send lock + loading indicator
  - auto-scroll to newest content
  - empty state on first launch
  - mode selector (`Althing` and `Direct Friday`)
  - connection chip (`Checking`/`Online`/`Offline`)
  - offline/error banner with retry and Tailscale hint
- Implemented networking/configuration surfaces:
  - default base URL: `http://100.125.116.103:18080/`
  - routes: `/api/althing/chat` and `/api/chat`
  - health probe: `/healthz`
  - persisted settings via DataStore (base URL + mode + stable device/session ids)
  - settings dialog for base URL edit/reset and connection test
- Added Android docs:
  - `android/README.md`
  - `docs/ANDROID_CLIENT.md`
- Build verification:
  - `cd /mnt/data/friday/android && JAVA_HOME=/mnt/data/friday/android/.jdk/jdk-17.0.14+7 PATH=/mnt/data/friday/android/.jdk/jdk-17.0.14+7/bin:$PATH ./gradlew --no-daemon assembleDebug`
  - APK output: `android/app/build/outputs/apk/debug/app-debug.apk`

### 2026-04-12 (Android Phase 2: Room persistence + continuity + responsiveness pass)
- Added structured local transcript persistence with Room in `android/app`:
  - entities: `conversations`, `messages`
  - DAO/database: `ConversationDao`, `MessageDao`, `FridayChatDatabase`
  - repository layer: `ChatHistoryRepository`
- Integrated persistence into chat runtime flow:
  - restore transcript automatically on launch
  - persist user/assistant turns with role, mode, status, and timestamps
  - maintain active conversation id and support clear-conversation action
- Improved perceived responsiveness:
  - assistant placeholder message with streaming status while request is in flight
  - typing-dot bubble for empty streaming assistant content
  - progressive assistant text rendering after response arrival (bounded chunk updates)
  - smoother auto-scroll keyed on latest message content growth
- UI updates:
  - top-bar clear conversation action with confirmation dialog
  - settings dialog now includes clear conversation action
  - message footer now shows timestamp and user-mode label
- Streaming status:
  - no clean existing backend streaming surface found for `/api/chat` or `/api/althing/chat` mobile path in this bounded pass
  - kept backend unchanged and used stable request/response + progressive render fallback
- Docs updated:
  - `android/README.md`
  - `docs/ANDROID_CLIENT.md`
- Build verification:
  - `cd /mnt/data/friday/android && JAVA_HOME=/mnt/data/friday/android/.jdk/jdk-17.0.14+7 PATH=/mnt/data/friday/android/.jdk/jdk-17.0.14+7/bin:$PATH ./gradlew --no-daemon assembleDebug`
  - output remains `android/app/build/outputs/apk/debug/app-debug.apk`

### 2026-04-13 (Prompt Layers Upgrade: tier-aware 30B/7B architecture + routed-mode alignment)
- Replaced monolithic runtime prompt assembly with explicit layered composition in `backend/core/prompt_builder.py`:
  - core identity
  - mode (`direct_friday` / `althing_routed`)
  - lane (`30b` / `7b`)
  - task overlay (general/coding/architecture/ops/summarization/planning/capability-report)
  - memory boundary
  - lane-specific runtime context template
  - optional interaction policy block
  - budgeted memory/procedural overlays
- Added lane-aware prompt caps:
  - `FRIDAY_SYSTEM_PROMPT_MAX_CHARS_30B`
  - `FRIDAY_SYSTEM_PROMPT_MAX_CHARS_7B`
- Added explicit lane class knobs:
  - `FRIDAY_CODER_MODEL_CLASS`
  - `FRIDAY_ALTHING_MODEL_CLASS`
- Added new prompt layer assets under `prompts/system/layers/` for core/mode/lane/task/runtime-context/memory-boundary.
- Althing bridge now prepends a Friday system prompt layer message (unless caller already provides a system message) via `build_althing_bridge_system_prompt`, and returns routed prompt metadata in response meta.
- Added documentation and report artifacts:
  - `docs/prompt_architecture.md`
  - `docs/prompt_layering_guidelines.md`
  - `PROMPT_LAYER_UPGRADE_REPORT.md`
- Added bounded validation artifacts:
  - dataset/case under `evals/datasets/` + `evals/cases/`
  - deterministic validator script `tools/prompt/validate_prompt_layers.py`
  - output artifact `artifacts/prompt_validation/prompt_layer_upgrade_validation.json`

Why:
- Enforce clear separation of identity/mode/lane/task responsibilities.
- Prevent generic-assistant fallback drift.
- Align Direct Friday and Althing-routed behavior through shared layer logic.
- Make 7B supplemental lanes shorter and more robust under lower instruction retention.

How to test:
- `python3 -m pytest -q`
- `python3 evals/runner.py --check`
- `python3 tools/prompt/validate_prompt_layers.py`
- `bash /mnt/data/.codex_ssot/v1/tools/agents_lint.sh`

### 2026-04-14 (Remediation v2: adaptive lane budgeting + full rerun deltas)
- Implemented adaptive per-lane token budgeting in `backend/core/chat_engine.py`:
  - lane/model-aware budget profiles (`general`, `reasoning`, `retrieval`, `coding`, with 7B scaling)
  - deterministic trim order (history -> procedural overlay -> system memory -> excerpt shrink -> output reduction -> narrow fallback)
  - task-aware output caps (strict format lower, code output higher)
  - richer runtime budget telemetry (`token_budget_applied` fields for lane/profile, token breakdown, trim actions, overflow prevention, fallback)
- Added adjacent output-shape hardening in `backend/core/response_shaper.py`:
  - avoid re-bulletizing already structured lists
  - avoid appending details prompts to structured list outputs
  - preserve code-fence structure
- Added failed/borderline rerun set support and delta tooling:
  - runner stable-id manifest filter: `evals/runner/run_corpus.py` (`--stable-ids-file`)
  - rerun manifest builder: `evals/remediation/build_failed_manifest.py`
  - analysis delta generator: `evals/remediation/analysis_delta.py`
- Produced remediation artifacts:
  - `evals/remediation/failed_or_borderline_from_combined_full_v1.jsonl`
  - `evals/remediation/failed_rerun_delta.json`
  - `evals/remediation/failed_rerun_delta_report.md`
  - `evals/remediation/combined_v1_to_v2_delta.json`
  - `evals/remediation/combined_v1_to_v2_delta_report.md`
  - `evals/remediation/remediation_pass_v2_adaptive_budgeting_report.md`
- Executed reruns and analyses:
  - failed/borderline rerun: `combined_failed_rerun_v2` + `combined_failed_rerun_v2_analysis_v1`
  - full rerun: `combined_full_v2` + `combined_full_v2_analysis_v1`
- Key measured deltas (v1 -> v2 full):
  - pass `49 -> 146`, fail `195 -> 58`
  - runtime failures `110 -> 0`
  - tool-selection failures `35 -> 4`
  - prompt-following failures increased (`37 -> 48`), now a primary remaining quality cluster.

## 2026-06-12 - Backend 8174 Restored for Local Model Bridge

### What Changed
- Restored the Candidate B qwen35 Q4 `llama-server` backend on port `8174`.
- Added `docs/local_gateway/BACKEND_8174_LIFECYCLE.md`.
- Added `docs/local_gateway/BACKEND_8174_RESTORE_REPORT.md`.
- Updated `docs/local_gateway/LOCAL_MODEL_BRIDGE_DOCTOR.md` with an `8174` troubleshooting section.

### Why
- The local model bridge doctor showed the gateway and Lexi container-to-gateway path were healthy, but backend `8174` was refusing connections.
- Critical aliases `lexi` and `friday-heavy-lite` depend on `8174`, so they failed while `friday-coder` on `8176` continued passing.

### New Env Flags
- None.

### How To Test
- `curl -fsS http://127.0.0.1:8174/v1/models`
- direct tiny completion against `http://127.0.0.1:8174/v1/chat/completions`
- `python3 /mnt/data/friday/scripts/local_model_bridge_doctor.py`

### Current Runtime Finding
- `8174` is restored as detached PID `1184035` using qwen35 Q4 on GPUs `0,1,2,3`.
- Full doctor result after restore: `passed: 19`, `failed: 0`, `skipped: 2`, `critical_failed: 0`.
- Remaining risk: `8174` is detached but not reboot-safe; recommended hardening is a dedicated systemd service.

## 2026-06-12 - Local Model Bridge Doctor

### What Changed
- Added `scripts/local_model_bridge_doctor.py`, a read-only diagnostic script for the local model bridge stack.
- Added `docs/local_gateway/LOCAL_MODEL_BRIDGE_DOCTOR.md` with usage, failure interpretation, and expected startup order.
- Added `docs/local_gateway/LOCAL_MODEL_BRIDGE_DOCTOR_IMPLEMENTATION_REPORT.md` with validation output and current runtime findings.
- The doctor writes its latest JSON result to `docs/local_gateway/local_model_bridge_doctor_latest.json`.

### Why
- Make local bridge failures attributable by boundary: host to gateway, gateway alias to backend, Lexi container to gateway, Lexi runtime contract, and ChefAI config contract.
- Prevent future repairs from treating Lexi or ChefAI as generically broken when the failing layer is a backend, alias, Docker path, or app contract.

### New Env Flags
- None.

### How To Test
- `python3 /mnt/data/friday/scripts/local_model_bridge_doctor.py --skip-completions`
- `python3 /mnt/data/friday/scripts/local_model_bridge_doctor.py`
- `python3 /mnt/data/friday/scripts/local_model_bridge_doctor.py --json-only --skip-completions`
- `cd /mnt/data/friday && python3 -m pytest tests/test_alias_routing.py -q`
- `cd /mnt/data/Lex && python3 -m pytest tests/test_runtime_preflight.py -q`

### Current Runtime Finding
- The gateway and Lexi container-to-gateway path are healthy.
- Backend `8174` is currently not accepting direct `/v1/models`, causing full doctor critical failures for `lexi` and `friday-heavy-lite`.
- Backend `8176` and gateway alias `friday-coder` are healthy.

## 2026-04-15 - Synthetic Optimizer Harness V1 (Bounded Policy Search)

### What Changed
- Added `evals/optimizer/` package implementing bounded synthetic recursive optimization harness:
  - reward/objective contract, split builder, candidate schema + mutation validation, proposal flow,
  - staged trial runner, promotion gate, trial ledger, promotion/rollback metadata, orchestrator CLI.
- Added optimizer docs:
  - `docs/FRIDAY_OPTIMIZATION_OBJECTIVE.md`
  - `docs/FRIDAY_OPTIMIZATION_SPLITS.md`
  - `docs/FRIDAY_MUTATION_SURFACES.md`
  - `docs/FRIDAY_PROMOTION_GATE.md`
  - `docs/FRIDAY_OPTIMIZER_LEDGER.md`
- Added optimizer tests:
  - `tests/test_optimizer_reward.py`
  - `tests/test_optimizer_splits.py`
  - `tests/test_optimizer_promotion.py`
  - `tests/test_optimizer_ledger.py`
- Generated persisted split artifacts and demo trial artifacts under `evals/optimizer/`.

### Why
- Formalize the existing eval/analysis/remediation workflow into a machine-usable bounded optimization loop.
- Make candidate promotion decisions explicit, auditable, and replayable.
- Add holdout/control non-regression discipline and protected metric gating.

### New Env Flags
- None required for artifact-backed optimizer trials.
- Existing env requirements still apply for live runner/analysis paths (e.g., endpoint availability, OpenAI key if OpenAI analysis enabled).

### How To Test
- `python3 -m py_compile evals/optimizer/*.py tests/test_optimizer_*.py`
- `python3 -m pytest -q tests/test_optimizer_reward.py tests/test_optimizer_splits.py tests/test_optimizer_promotion.py tests/test_optimizer_ledger.py`
- `python3 evals/optimizer/splits.py --analysis-results evals/analysis_runs/combined_full_v3_analysis_v1/analysis_results.jsonl --out evals/optimizer/data_splits_v1.json --seed 20260414`
- `python3 evals/optimizer/propose_candidates.py --mode model_assisted --failure-type routing_failure --target-slice routing_failure__debug_traceback --out evals/optimizer/runs/optimizer_harness_v1_demo/model_assisted_candidates.jsonl`
- `python3 evals/optimizer/optimize.py --mode batch --optimizer-run-id optimizer_harness_v1_batch --candidate-file evals/optimizer/runs/optimizer_harness_v1_demo/candidates_demo.jsonl --baseline-analysis evals/analysis_runs/combined_full_v2_analysis_v1/analysis_results.jsonl --candidate-analysis evals/analysis_runs/combined_full_v3_analysis_v1/analysis_results.jsonl --splits evals/optimizer/data_splits_v1.json --gate-config evals/optimizer/runs/optimizer_harness_v1_demo/gate_manual_review.json`

## 2026-04-15 - Althing WorkingScratchpad + Mimir Root Decision Pass

### What Changed
- Implemented bounded private Althing runtime `WorkingScratchpad` in adjacent Althing router runtime (`/mnt/data/althing/router/working_scratchpad.py`) and wired it into live request execution/synthesis (`/mnt/data/althing/router/main.py`).
- Added scratchpad leak sanitization/detection guardrails in `/mnt/data/althing/router/quality.py`.
- Added targeted tests proving lifecycle, private-by-default behavior, debug-only inspection path, and leak guard rewrite behavior (`/mnt/data/althing/tests/test_router_working_scratchpad.py`).
- Added Friday root Mimir cognition entrypoints:
  - `scripts/mimir_context.sh`
  - Make targets: `mimir-status`, `mimir-index`, `mimir-query`, `mimir-bundle`
- Added implementation/design/boundary docs:
  - `docs/ALTHING_WORKING_SCRATCHPAD_DESIGN.md`
  - `docs/ALTHING_WORKING_SCRATCHPAD_RUNTIME_FLOW.md`
  - `docs/ALTHING_MIMIR_ROOT_DECISION.md`
  - `docs/ALTHING_WORKING_MEMORY_VS_MIMIR_BOUNDARY.md`
  - `docs/ALTHING_WORKING_SCRATCHPAD_IMPLEMENTATION_REPORT.md`
- Added machine-readable summary artifact:
  - `artifacts/althing_workingscratchpad_design_summary.json`

### Why
- Improve Althing answer quality by adding structured within-turn private cognition and explicit final synthesis.
- Reduce visible scratchpad/self-narration leakage.
- Make Mimir usage at Friday root explicit and reproducible for developer/agent repository navigation.
- Keep strict separation between runtime working memory, durable memory, and repo cognition.

### New Env Flags
- None required for the scratchpad implementation.
- Existing optional Mimir telemetry flags remain unchanged (`FRIDAY_MIMIR_TRACE_*`).

### How To Test
- `PYTHONPATH=/mnt/data/althing pytest -q /mnt/data/althing/tests/test_router_working_scratchpad.py /mnt/data/althing/tests/test_router_phase2_policy.py /mnt/data/althing/tests/test_router_friday_handoff_contract.py /mnt/data/althing/tests/test_router_control_exposure_calibration.py`
- `python3 -m py_compile /mnt/data/althing/router/main.py /mnt/data/althing/router/quality.py /mnt/data/althing/router/working_scratchpad.py /mnt/data/althing/tests/test_router_working_scratchpad.py`
- `bash scripts/mimir_context.sh status`
