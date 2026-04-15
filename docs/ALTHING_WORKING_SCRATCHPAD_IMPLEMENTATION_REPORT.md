# Althing WorkingScratchpad Implementation Report

Date: 2026-04-15

## Outcome summary
Implemented a first working version of bounded private runtime working memory in Althing, wired into live execution and final synthesis, with leak guardrails and debug-only inspection.

## Files changed
### Althing runtime
- `/mnt/data/althing/router/working_scratchpad.py` (new)
- `/mnt/data/althing/router/main.py`
- `/mnt/data/althing/router/quality.py`
- `/mnt/data/althing/tests/test_router_working_scratchpad.py` (new)

### Friday root (Mimir repo-cognition integration)
- `/mnt/data/friday/scripts/mimir_context.sh` (new)
- `/mnt/data/friday/Makefile`

### Friday docs/artifacts
- `docs/ALTHING_WORKING_SCRATCHPAD_DESIGN.md`
- `docs/ALTHING_WORKING_SCRATCHPAD_RUNTIME_FLOW.md`
- `docs/ALTHING_MIMIR_ROOT_DECISION.md`
- `docs/ALTHING_WORKING_MEMORY_VS_MIMIR_BOUNDARY.md`
- `docs/ALTHING_WORKING_SCRATCHPAD_IMPLEMENTATION_REPORT.md`
- `artifacts/althing_workingscratchpad_design_summary.json`

## WorkingScratchpad design implemented
- Added typed schema with bounded lists and bounded summary size.
- Added initialization from user input/constraints/required outputs/context messages.
- Added structured updates for lane outputs, tool findings, and uncertainties.
- Added debug snapshot export (`debug_text`) for explicit debug inspection.

## Runtime flow changes
- Scratchpad created at turn start in `_execute` and attached to `ExecutionState`.
- `_record_step` now writes compact lane-step notes into scratchpad.
- Workflow synthesis prompts include scratchpad summary.
- Direct route now uses explicit synthesis pass (`synthesize_final`) over draft output + scratchpad context.
- Final output passes sanitization + leak detection; leak triggers one rewrite pass.

## Synthesis and non-leakage behavior
- Added scratchpad leak stripping in sanitizer:
  - remove `<WORKING_SCRATCHPAD>...</WORKING_SCRATCHPAD>` blocks
  - remove scratchpad field lines
- Added scratchpad leak issue markers:
  - `scratchpad_marker_leak`
  - `scratchpad_field_leak`
  - `internal_contract_leak`
- Added guardrail rewrite when leak markers persist in final quality markers.

## Debug behavior
- Scratchpad is hidden in normal responses.
- Debug snapshot is surfaced only under `evaluation_trace=true` via `outputs.intermediate` step `debug_working_scratchpad_snapshot`.

## Mimir root decision and implementation
Decision: use Mimir at Friday root as repo-cognition substrate, separate from runtime memory.

Implemented minimal root wiring:
- `scripts/mimir_context.sh` with `status/index/query/bundle` commands.
- Make targets for standard invocation:
  - `mimir-status`, `mimir-index`, `mimir-query`, `mimir-bundle`.

## Validation performed
### Runtime/unit tests
Executed:
- `PYTHONPATH=/mnt/data/althing pytest -q /mnt/data/althing/tests/test_router_working_scratchpad.py /mnt/data/althing/tests/test_router_phase2_policy.py /mnt/data/althing/tests/test_router_friday_handoff_contract.py /mnt/data/althing/tests/test_router_control_exposure_calibration.py`
- Result: `40 passed`.

### Syntax check
Executed:
- `python3 -m py_compile /mnt/data/althing/router/main.py /mnt/data/althing/router/quality.py /mnt/data/althing/router/working_scratchpad.py /mnt/data/althing/tests/test_router_working_scratchpad.py`
- Result: pass.

### Root Mimir integration check
Executed:
- `bash scripts/mimir_context.sh status` from `/mnt/data/friday`
- Result: Mimir runtime info + indexed workspace status returned successfully.

## Representative leakage reduction smoke (Althing-style)
Scenario (test-driven): reasoning-heavy recommendation prompt where first synthesis emits visible scratch note text.
- First synthesis output: `Working scratchpad summary: ...`
- Guardrail pass triggers rewrite synthesis.
- Final output: user-facing recommendation only, no scratch markers.

Implemented in test:
- `test_execute_guardrail_rewrites_scratchpad_leak`.

## Remaining limitations
- Scratchpad is per-turn only; no cross-turn persistence by design.
- Bridge-mode session memory behavior remains unchanged (still caller-message dependent).
- Guardrail rewrite is single-pass; if a model repeatedly leaks, degradation is marked but content may still require stricter policy fallback.

## Recommended next step
Add a bounded “synthesis contract checker” for final outputs that can hard-fallback to executive rewrite templates when leakage or non-answer markers remain after rewrite, while keeping scratchpad private.
