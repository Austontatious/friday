# ALTHING Memory Gap Analysis

Date: 2026-04-14

## What users might think Althing has

1. A persistent conversational memory in Althing mode because session/device headers are present.
2. A hidden internal whiteboard that tracks intermediate reasoning and tool evidence.
3. Muninn-backed durable memory automatically active for all Althing requests.
4. A single unified memory behavior between Direct Friday and Althing mode.

## What it actually has

1. Default Friday UI Althing mode forwards only current prompt unless client manually supplies `messages`.
   - Evidence: `frontend/src/services/api.ts:85-90`, `frontend/src/App.tsx:44`, `backend/api/althing_chat.py:67-83`.

2. Direct Friday mode (not bridge mode) has transcript continuity + provider-backed memory rehydrate/stage.
   - Evidence: `backend/core/chat_engine.py:1020`, `:1056-1069`, `:1476-1481`.

3. Althing router has request-local orchestration state (`ExecutionState`) and route logs, not a dedicated whiteboard memory subsystem.
   - Evidence: `/mnt/data/althing/router/main.py:89-101`, `:2346-2357`, `:2613-2701`.

4. Muninn is wired in Friday direct memory provider path, not in Althing router runtime.
   - Evidence: `backend/memory/muninn_provider.py:42-59`, `:60-85`; no Muninn references in `/mnt/data/althing/router` runtime path.

## Missing for desired private whiteboard behavior

1. No explicit private scratchpad contract.
   - Missing: typed hidden object for assumptions, candidate plans, evidence, unresolved checks, synthesis rationale.

2. No deterministic scratch lifecycle.
   - Missing: explicit write/read/update phases across plan/tool/synthesis within a turn.

3. No hard privacy boundary for intermediate internals.
   - Current: Althing `RouteResponse` includes `outputs.intermediate` on `/v1/route`; direct Friday exposes `meta.runtime_events`.
   - Evidence: `/mnt/data/althing/router/schema.py:234-237`, `/mnt/data/althing/router/main.py:2580-2586`; `backend/core/chat_engine.py:1543`.

4. No default cross-turn memory in the active Althing bridge flow.
   - This amplifies whiteboard weakness because each request often starts from only one prompt.

## Architectural gaps vs prompt/policy gaps

### Architectural gaps (primary)

1. Split runtime behavior:
   - Direct mode has memory pipeline; bridged Althing mode bypasses it.
2. No first-class whiteboard object in either runtime.
3. Althing session continuity depends on caller-supplied message history rather than server-owned memory retrieval.
4. Durable memory writes are narrow heuristic extraction from user text, not generalized task-memory learning.

### Prompt/policy issues (secondary)

1. Interaction policy/refinement exist but are not substitutes for a whiteboard.
   - They shape output style/quality but do not provide hidden structured intermediate state.
2. Procedure overlay can improve task targeting when enabled, but defaults are disabled and it is still retrieval/policy, not intrinsic scratch memory.

## Gap severity summary

| Gap | Severity | Why |
|---|---|---|
| Missing private within-turn whiteboard abstraction | High | Core requested behavior absent |
| Default Althing mode lacks server-side recent-turn memory | High | Active user path starts from near-stateless context |
| Durable memory not wired in Althing router runtime | Medium-High | Limits cross-session continuity in routed mode |
| Intermediate-state exposure surfaces (`intermediate`, `runtime_events`) | Medium | Potential leakage/overexposure of internal orchestration details |
| Legacy local memory subsystems mostly flag-off | Medium | Present but not active by default |
