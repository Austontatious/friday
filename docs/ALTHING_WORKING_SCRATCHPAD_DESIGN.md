# Althing WorkingScratchpad Design

Date: 2026-04-15

## Scope
This pass implements a first-class, bounded, private within-turn `WorkingScratchpad` in live Althing execution (`/mnt/data/althing/router/main.py`) and does not redesign long-term memory.

## Design goals
- Private within-turn working state.
- Structured fields, not free-form chain-of-thought dumps.
- Bounded storage and bounded synthesis payload.
- Reusable across route/lane orchestration in one request.
- Debug-inspectable only on explicit debug path (`evaluation_trace`).

## Implemented schema
Implemented in `/mnt/data/althing/router/working_scratchpad.py`.

Fields:
- `task_type`
- `user_goal`
- `route_intent`
- `subquestions[]`
- `must_include[]`
- `must_avoid[]`
- `tool_findings[]`
- `candidate_answer_shape`
- `uncertainties[]`
- `synthesis_notes[]`
- `final_answer_contract`

Bounded controls:
- `_max_items=8`
- `_max_item_chars=220`
- `_max_summary_chars=1800`

## Lifecycle
1. Initialize at request start in `_execute` using request prompt, required outputs, constraints, and context messages.
2. Populate route intent/task type after policy decision.
3. Update continuously from lane/tool/intermediate steps via `_record_step` integration.
4. Consume in synthesis prompts (workflow and direct path).
5. Keep private from normal response output.
6. Expose debug snapshot only when `RouteRequest.evaluation_trace=true`.

## Integration points
- `ExecutionState` now carries `scratchpad`: `/mnt/data/althing/router/main.py`.
- `_record_step` writes step outcomes into scratchpad notes/uncertainties.
- Workflow synthesis prompts now include bounded scratchpad summary.
- Direct lane path now performs explicit final synthesis step using scratchpad (`synthesize_final`).
- Final output passes scratchpad-leak guard and sanitization before response return.

## Privacy and leakage policy
- Scratchpad is not included in `outputs.final`.
- Output sanitizer strips scratchpad tags/field lines.
- Output issue detector flags scratchpad markers/field leaks/internal contract leaks.
- Leak guard triggers a rewrite synthesis pass when leak markers survive into final-quality markers.

## Debug visibility
- Debug snapshot added to `outputs.intermediate` only when `evaluation_trace=true` with step `debug_working_scratchpad_snapshot` and lane `router_internal`.
- Default user path remains private.

## Non-goals in this pass
- No cross-turn scratchpad persistence.
- No Muninn durable-memory redesign.
- No replacement of existing direct-mode memory provider flow.
