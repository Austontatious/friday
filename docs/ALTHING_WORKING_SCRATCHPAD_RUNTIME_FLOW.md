# Althing WorkingScratchpad Runtime Flow

Date: 2026-04-15

## Entry and setup
1. Request enters Althing route execution (`_execute`) through `/route` or chat-compat route.
2. `WorkingScratchpad.initialize(...)` is called immediately from request inputs.
3. `ExecutionState` stores the scratchpad for the full request lifetime.

## Policy and route intent
1. Router policy selects primary lane/workflow.
2. Scratchpad is updated with:
- `task_type` from policy family.
- `route_intent` from selected mode/lane/workflow.
- synthesis and guard notes from policy constraints.

## Lane execution updates
1. Every `_record_step(...)` call records:
- intermediate output (`outputs.intermediate`)
- lane quality markers
- scratchpad synthesis note + uncertainty updates
2. Existing lane behavior remains intact; scratchpad updates are compact metadata, not verbose prose dumps.

## Synthesis behavior
### Workflow routes
- Existing workflow synthesis prompts now use `_build_synthesis_prompt(...)` and include bounded scratchpad summary.

### Direct route
- Direct lane output becomes draft output.
- New explicit final synthesis step (`synthesize_final`) produces user-facing final content using:
  - original user request
  - bounded scratchpad summary
  - draft lane output

## Final output guardrails
1. Final text goes through `_sanitize_and_mark_output(...)`.
2. Sanitizer removes scratchpad tags/field-line artifacts.
3. Quality detection flags residual scratchpad leakage markers.
4. If leak markers remain, guardrail rewrite triggers one additional synthesis pass.
5. Final response returns only sanitized user-facing output.

## Debug path
- If `evaluation_trace=true`, intermediate output includes one debug-only snapshot step:
  - `step=debug_working_scratchpad_snapshot`
  - `lane=router_internal`
- This does not run in normal user mode.

## End-of-turn
- Scratchpad exists only in process memory for the request.
- It is not persisted as session memory and not forwarded to downstream durable-memory systems.
- Telemetry logs scratchpad aggregate stats only (counts/summary size), not full raw scratch text.
