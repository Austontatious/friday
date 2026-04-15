# ALTHING Memory State Audit

Date: 2026-04-14
Scope audited:
- Primary: `/mnt/data/friday` runtime paths that serve Althing and Direct Friday chat.
- Adjacent dependency: `/mnt/data/althing/router` runtime path used by Friday Althing bridge.

This is a state audit of implemented behavior, not a redesign.

## Runtime entrypoints and control flow

1. Friday backend exposes both direct and Althing-bridge chat routes.
   - `POST /api/chat` calls `run_chat(...)` in Friday core runtime: `backend/api/chat.py:25-47`.
   - `POST /api/althing/chat` proxies to Althing upstream: `backend/api/althing_chat.py:158-216`.
   - Router registration includes both endpoints: `backend/main.py:30-33`.

2. Frontend defaults to Althing mode and sends only current prompt by default.
   - Default mode resolves to `"althing"`: `frontend/src/services/api.ts:8-13`.
   - Request body is `{ prompt, mode }` (no transcript payload): `frontend/src/services/api.ts:85-90`.
   - UI send path passes only current input: `frontend/src/App.tsx:44`.

3. Android client also sends only current prompt + session/device headers.
   - Network contract: `X-Friday-Device`, `X-Friday-Session`: `android/.../FridayApi.kt:12-17`.
   - Payload is `ChatRequestDto(prompt=..., mode=...)`: `android/.../FridayRepository.kt:24-29`.
   - Local chat history is device-local Room-backed storage: `android/.../ChatHistoryRepository.kt:16-19`, `:37-57`.

4. Friday Althing bridge payload behavior.
   - Bridge can forward `payload.messages` if provided; otherwise builds a single user message with current prompt: `backend/api/althing_chat.py:67-83`.
   - System prompt is prepended when missing: `backend/api/althing_chat.py:88-90`.
   - Bridge forwards to Althing `/chat/completions`: `backend/api/althing_chat.py:198-216`.

5. Althing router runtime.
   - Chat-compat endpoint maps chat messages into `RouteRequest.context.messages` and executes route: `/mnt/data/althing/router/main.py:3180-3205`.
   - Route execution creates per-request `ExecutionState` and returns `RouteOutputs(final, intermediate)`: `/mnt/data/althing/router/main.py:2346-2357`, `:2580-2586`; schema in `/mnt/data/althing/router/schema.py:225-237`.

## Short-term working memory

### What exists now

1. Friday direct path has transient within-turn structured buffers.
   - `messages`, `runtime_events`, `procedure_meta`, `tool_results`, `refinement_meta`, `memory_meta` inside `run_chat`: `backend/core/chat_engine.py:1022-1050`, `:1177-1185`, `:1267-1270`, `:1363-1387`, `:1475-1512`.
   - Tool results are first captured as structured objects (`tool_results`) then appended into prompt as `tool` messages for synthesis/regeneration: `backend/core/chat_engine.py:1267-1291`, `:1330-1351`.

2. Althing router has transient request-local structured state.
   - `ExecutionState` fields include `intermediate`, `errors`, quality/degradation markers: `/mnt/data/althing/router/main.py:89-101`.
   - Per-step outputs are recorded via `_record_step(...)` into `state.intermediate`: `/mnt/data/althing/router/main.py:257-285`.

3. Bounded refinement is a de facto within-turn buffer in direct Friday (when enabled).
   - Critique/decision/revision state exists in-memory during request: `backend/core/refinement.py:283-289`, `:326-355`.
   - Can patch/regenerate/compare variants before final reply: `backend/core/refinement.py:351-377`.

### What does not exist

1. No dedicated hidden whiteboard object with explicit semantic fields (hypotheses, assumptions, evidence ledger, unresolved questions) is instantiated in Friday or Althing runtime.
2. Existing transient buffers are implementation-local orchestration objects, not a first-class private working-memory contract.

### Direct answers (Q1)

- True hidden within-turn working-memory object: `partial`.
  - Structured transient state exists (`tool_results`, `ExecutionState.intermediate`), but no explicit private whiteboard abstraction.
- Intermediate reasoning in structured hidden state vs continuation text:
  - Mostly continuation text + orchestration state; no explicit reasoning graph/scratch schema.
- Tool-result staging:
  - `yes` in direct Friday (`tool_results` list before synthesis), `no` in Althing router path (no tool engine there).
- Bounded refinement as working buffer:
  - `yes, partial`, only when refinement is enabled (`FRIDAY_REFINEMENT_ENABLED`); default is off in `.env.example`: `.env.example:56`.

## Conversational short-term memory

### What exists now

1. Direct Friday mode persists recent turns per user/workspace in `MemoryStore` and reloads them each request.
   - Load recent turns: `backend/core/chat_engine.py:1020`.
   - Append user/tool/assistant turns: `backend/core/chat_engine.py:1265`, `:1289-1291`, `:1423`.
   - History limit from `FRIDAY_CONTEXT_TURNS` (default 20): `backend/core/chat_engine.py:176-181`.

2. Prompt assembly includes those recent turns.
   - `memory_bundle["recent_turns"]` appended into message sequence: `backend/core/prompt_builder.py:577-583`.

3. Prompt budget trimming governs conversational carryover.
   - Drops stale history first, then overlays/memory, then excerpt shrinking/fallback: `backend/core/chat_engine.py:528-555`, `:557-587`.

### Althing-mode reality (Friday UI default)

1. Friday Althing bridge does not call `run_chat`, so it does not use Friday memory load/append path.
   - Bridge endpoint is independent proxy path: `backend/api/althing_chat.py:158-216`.

2. Since default clients send only current prompt, session memory is effectively absent in this mode unless caller explicitly supplies `messages`.
   - Frontend: `frontend/src/services/api.ts:85-90`, `frontend/src/App.tsx:44`.
   - Android: `android/.../FridayRepository.kt:24-29`.
   - Bridge fallback to single user message when no messages provided: `backend/api/althing_chat.py:81-83`.

### Lane-specific behavior

- Recent context is not lane-specific memory; it is common transcript history in direct mode.
- Reasoning/coding/retrieval flows apply different token/output budgets and trimming pressure by route/lane profile, not different memory stores.
  - Lane routing-to-budget mapping: `backend/core/chat_engine.py:306-313`.
  - Output budget differences by route: `backend/core/chat_engine.py:461-470`.

### Direct answers (Q2)

- Preserved across messages:
  - Direct Friday: recent transcript turns (`yes`).
  - Althing bridge default UI: practically no cross-turn context (`no/partial`, depends on client-supplied `messages`).
- Representation: raw transcript turns + optional injected memory/procedure overlays in system prompt (direct mode).
- Pruning/budgeting: deterministic trim actions in `_fit_messages_to_token_budget`.

## Long-term / persistent memory

### What is wired today

1. Friday direct path uses provider-based durable memory rehydrate + stage.
   - Provider selection defaults to `muninn` with fallback provider wrapper: `backend/memory/factory.py:23-25`, `:167-186`.
   - Rehydrate call in request path: `backend/core/chat_engine.py:1054-1063`.
   - System memory injection block rendered from returned cards: `backend/core/chat_engine.py:1066-1069`, `backend/memory/provider.py:444-491`.
   - Stage extracted per-turn candidates: `backend/core/chat_engine.py:1476-1481`.

2. Muninn provider contract is explicitly implemented.
   - Rehydrate: `/v0/memory/rehydrate`: `backend/memory/muninn_provider.py:42-59`.
   - Stage candidates: `/v0/memory/stage_candidates`: `backend/memory/muninn_provider.py:60-85`.
   - Confirm/list pending endpoints: `backend/memory/muninn_provider.py:86-127`; HTTP routes `backend/api/memory_provider.py:54-186`.

3. Write triggers are currently heuristic and user-text-centric.
   - Candidate extraction from user prompt only (`call me`, `prefer`, email/phone patterns): `backend/memory/provider.py:31-39`, `:539-614`.
   - Sensitive kinds require confirmation policy on candidate: `backend/memory/provider.py:29`, `:494-536`.

### Present but conditional / inactive by default

1. Legacy local memory stores (facts/summaries/consolidation) exist but are env-gated and default-off.
   - Flags default off in `.env.example`: `.env.example:87-91`.
   - Service gates for facts/summaries/consolidation: `backend/memory/service.py:33-40`, `:171-176`.
   - Thread persistence gate default-off: `backend/memory/memory.py:27`, `.env.example:87`.

2. Procedure overlay and reflection lifecycle persistence are also env-gated and default-off.
   - Flags default off: `.env.example:48`, `:55`.
   - Runtime overlay/retrieval/stage path: `backend/procedures/service.py:29-72`, `:75-143`.

### Althing runtime integration status

- Althing router has no Muninn integration in runtime request path (no Muninn/memory API calls in `/mnt/data/althing/router`).
- Therefore Muninn is not wired into Althing router execution itself.

### Direct answers (Q3)

- Durable memory systems wired into active request path: `yes` for direct Friday, `no` for bridged Althing runtime.
- Muninn consulted in Althing mode:
  - Bridged UI path: not by Friday bridge itself; only if caller uses direct Friday route instead.
  - Althing router path: `no`.
- Durable writes today: staged candidate writes from heuristic extraction + optional procedure reflection staging (env-gated).

## Retrieval/logging/ledger mechanisms acting as pseudo-memory

These mechanisms persist or reuse information but are not intrinsic working memory.

1. Runtime/event logs.
   - Friday audit logs: `backend/audit/logger.py:20-40`.
   - Friday Mimir trace JSONL (env-gated): `backend/telemetry/mimir_trace.py:17-19`, `:43-63`; emit call in chat runtime `backend/core/chat_engine.py:216-223`.
   - Althing router events/shadow logs via JSONL loggers: `/mnt/data/althing/router/main.py:57-58`, `:2613-2701`, `:2764-2882`; logger implementation `/mnt/data/althing/router/logging.py:10-29`.

2. Refinement/handoff trace artifacts (durable files, not runtime memory store).
   - Refinement trace emitter: `backend/core/refinement.py:192-199`, `:420-447`.
   - Handoff trace emitter: `backend/handoff/service.py:95-103`.

3. Tool/file retrieval outputs used as context.
   - `file_search` returns matched file snippets; auto-injected as tool results for regeneration: `backend/tools/builtins.py:195-205`, `backend/core/chat_engine.py:714-724`, `:1293-1325`.

4. Optimizer/eval ledgers are durable artifacts but not request-time memory.
   - Example ledger writer: `evals/optimizer/trial_ledger.py:64-97`.
   - No runtime references from backend/core to optimizer ledger paths (search found none).

5. Althing shadow policy cache is runtime cache, not user/session memory.
   - In-process deque keyed by profile id: `/mnt/data/althing/router/main.py:1068-1074`.
   - Updated with timeout/error/empty stats: `/mnt/data/althing/router/main.py:1552-1565`.

## What is wired vs what is merely present

| Capability | Present in repo | Wired in `POST /api/chat` (direct) | Wired in `POST /api/althing/chat` default UI flow |
|---|---|---|---|
| Recent-turn transcript memory | Yes | Yes | No (unless caller sends `messages`) |
| Muninn rehydrate for injected memory | Yes | Yes | No |
| Heuristic memory candidate staging | Yes | Yes | No |
| Memory confirm/pending APIs | Yes | Yes (manual follow-up) | Not naturally reached from bridge flow |
| Legacy facts/summaries/consolidation stores | Yes | Conditional, default off | No |
| Procedure overlay retrieval/persistence | Yes | Conditional, default off | No |
| Refinement loop | Yes | Conditional, default off | No |
| Althing `ExecutionState.intermediate` step buffer | Yes (Althing repo) | N/A | Yes (inside Althing runtime) |
| Althing route-execution logs | Yes (Althing repo) | N/A | Yes |
| Optimizer/eval ledgers | Yes | No | No |

## Whiteboard / private scratchpad readiness

1. Nearest substrate exists but is incomplete.
   - Althing `ExecutionState.intermediate` and Friday `tool_results`/refinement structures are closest existing scaffolds.

2. Missing pieces for true private whiteboard behavior.
   - No explicit whiteboard schema (goal/assumptions/evidence/open-questions/final-claim mapping).
   - No dedicated read/write lifecycle across internal reasoning stages.
   - No strict 'private-by-default' boundary for all intermediate content.

3. Visible leakage risk points.
   - Althing `/v1/route` returns `outputs.intermediate` directly: `/mnt/data/althing/router/schema.py:234-237`, `/mnt/data/althing/router/main.py:2580-2586`.
   - Direct Friday returns rich `meta.runtime_events` in API response: `backend/core/chat_engine.py:1543`.

## Safety and boundedness

1. Prompt bloat controls exist in direct path.
   - Memory/procedure blocks are dropped when needed, with deterministic trim actions: `backend/core/chat_engine.py:545-556`, `:575-587`.
   - Injected memory block is card/bullet/char/token bounded: `backend/memory/provider.py:448-451`, `:469-479`.

2. Isolation boundaries.
   - User identity/session/device resolution influences memory bucket selection: `backend/identity/identity.py:45-82`.
   - Workspace routing boundary: `backend/workspaces/routing.py:7-11`.

3. Cross-request contamination risk.
   - Althing shadow cache is profile-scoped, not session-scoped: `/mnt/data/althing/router/main.py:1068-1074`.
   - This affects routing policy behavior, though it does not store full user content.

## Direct answers (Q4-Q7)

1. Q4. Whiteboard/private scratchpad readiness:
   - Hidden planning substrate exists only as partial orchestration buffers (`ExecutionState.intermediate`, `tool_results`, refinement vars), not as a dedicated private whiteboard.
   - Nearest extension point is Althing `ExecutionState` plus existing synthesize workflow boundaries.
   - Visible leakage risk is currently medium due `/v1/route` intermediate output exposure and direct-mode `meta.runtime_events`.

2. Q5. Separation between memory types:
   - True memory: direct-mode transcript turns + provider rehydrate/stage paths.
   - Retrieval, not memory: `file_search` and prompt-time procedure retrieval.
   - Eval/log artifacts, not memory: Mimir traces, refinement/handoff traces, Althing route/shadow logs, optimizer ledgers.
   - Runtime cache, not user memory: Althing shadow history deques keyed by profile.

3. Q6. Safety and boundedness:
   - Prompt-bloat controls are implemented (history/overlay/system-memory dropping + excerpt shrinking + fallback narrow context).
   - Injection payloads are bounded by card/bullet/char/token caps.
   - Identity/workspace boundaries partition memory buckets in direct mode.

4. Q7. Practical next step:
   - Recommended single next move is documented in `docs/ALTHING_MEMORY_NEXT_STEP_RECOMMENDATION.md`.
   - Short form: add a bounded private `WorkingScratchpad` inside Althing execution and route final synthesis through it, without exposing scratch content.

## Evidence-backed conclusion

1. Althing (as used by default Friday UI mode) currently does not have true conversational memory continuity unless the client explicitly submits message history.
2. A true intrinsic private whiteboard object is not implemented in either Friday or Althing runtime.
3. Direct Friday route has partial memory capability: transcript continuity + provider-backed durable recall/write staging + structured tool/refinement buffers.
4. Althing runtime has structured within-request state (`ExecutionState`) but it is orchestration state, not a dedicated private working-memory substrate.
5. Major quality gap for desired whiteboard behavior is primarily lack of explicit hidden staging contract, secondarily lack of session-memory wiring in the default bridged Althing flow.
